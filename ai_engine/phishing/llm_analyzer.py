"""
LLM-based Phishing Analyzer
============================
Uses a 4-bit quantized GGUF LLaMA model via llama-cpp-python.
Constrained to n_ctx=512 and 4 threads to fit within M4 memory budget.

3-Tier Fallback Architecture:
  Tier 1 — LLM inference (llama-cpp-python GGUF)
  Tier 2 — Advanced heuristic engine (keyword density, urgency, SPF/DKIM)
  Tier 3 — Pure URL + header signal baseline (always succeeds)
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from collections import Counter
from typing import Optional

from ai_engine.identity.ecdsa_service import ECDSAService
from ai_engine.phishing.url_forensics import URLForensics
from ai_engine.phishing.header_analyzer import analyze_headers as _analyze_headers_full

logger = logging.getLogger(__name__)

# Lazy import — llama_cpp only loaded when this module is instantiated
try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False
    logger.warning("llama-cpp-python not installed — LLM analysis disabled, using heuristics")

# ─────────────────────────────────────────────────────────────────────────────
# Enhanced LLM System Prompt — spear-phishing and executive fraud aware
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an elite cybersecurity analyst specialised in detecting phishing, \
spear-phishing, and business email compromise (BEC) attacks.

Analyse the following email/message content and respond with a JSON object ONLY \
(absolutely no markdown, no preamble, no explanation outside the JSON).

Evaluate ALL of the following attack vectors:
  - EXECUTIVE IMPERSONATION: Pretending to be a CEO, CFO, CISO, or board member
  - WIRE TRANSFER FRAUD: Urgent requests to transfer funds or change payment details
  - CREDENTIAL HARVESTING: Links or forms requesting passwords, MFA codes, SSO tokens
  - ARTIFICIAL URGENCY: "Act now", "expires in 24h", "immediate action required"
  - AUTHORITY ABUSE: Invoking HR, IT Security, Legal, Compliance, or Government authority
  - BRAND IMPERSONATION: Faking Microsoft, Google, Apple, PayPal, bank, or IRS communications
  - HOMOGLYPH ATTACKS: Subtle misspellings using look-alike characters
  - SOCIAL ENGINEERING: Creating fear, pressure, curiosity, or greed triggers

Return exactly this JSON structure (no trailing commas):
{
  "is_phishing": true,
  "confidence": 0.0,
  "risk_level": "low",
  "signals": ["list of detected attack vectors"],
  "explanation": "one-sentence summary of primary attack vector"
}

risk_level must be one of: "low" | "medium" | "high" | "critical"\
"""

# ─────────────────────────────────────────────────────────────────────────────
# Heuristic keyword banks for Tier-2 fallback
# ─────────────────────────────────────────────────────────────────────────────

_URGENCY_TRIGGERS = {
    "immediately", "urgent", "urgently", "asap", "right away", "expire",
    "expires", "expiring", "suspended", "suspended account", "verify now",
    "action required", "immediate action", "respond immediately", "time sensitive",
    "account locked", "unusual activity", "security alert", "24 hours",
    "48 hours", "final notice", "last warning", "limited time",
}

_EXEC_IMPERSONATION = {
    "ceo", "cfo", "ciso", "president", "chairman", "board of directors",
    "managing director", "executive", "c-suite", "vp of finance",
}

_WIRE_TRANSFER = {
    "wire transfer", "bank transfer", "ach transfer", "swift", "routing number",
    "account number", "payment details", "change payment", "new bank account",
    "vendor payment", "invoice attached", "outstanding invoice",
}

_CREDENTIAL_HARVEST = {
    "click here to verify", "confirm your identity", "reset your password",
    "your account will be", "one-time password", "otp", "mfa", "2fa code",
    "security code", "login link", "sign in to continue", "access your account",
    "verify your email",
}

_AUTHORITY_ABUSE = {
    "irs", "fbi", "police", "tax authority", "government", "legal department",
    "compliance team", "it security", "helpdesk", "human resources", "hr team",
}


def _text_entropy(text: str) -> float:
    """Shannon entropy of character distribution in text."""
    if not text:
        return 0.0
    freq = Counter(text.lower())
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def _keyword_density(text: str, keywords: set) -> float:
    """Fraction of keyword matches found, capped at 1.0."""
    lower = text.lower()
    hits = sum(1 for kw in keywords if kw in lower)
    return min(hits / max(len(keywords), 1), 1.0)


class PhishingAnalyzer:
    def __init__(
        self,
        model_path: str = "",
        ecdsa_service: Optional[ECDSAService] = None,
    ) -> None:
        self.url_forensics = URLForensics()
        self.ecdsa = ecdsa_service or ECDSAService()
        self._llm = None

        if LLAMA_AVAILABLE and os.path.exists(model_path):
            logger.info(f"Loading GGUF model from {model_path}")
            try:
                self._llm = Llama(
                    model_path=model_path,
                    n_ctx=int(os.environ.get("LLM_N_CTX", 512)),
                    n_threads=int(os.environ.get("LLM_N_THREADS", 4)),
                    n_gpu_layers=-1,   # Offload all layers to MPS (Apple Metal)
                    verbose=False,
                )
                logger.info("✅ GGUF LLM loaded successfully")
            except Exception as exc:
                logger.warning(f"GGUF LLM load failed: {exc}; falling back to heuristics")
                self._llm = None
        else:
            logger.warning(
                f"GGUF model not found at '{model_path}' or llama-cpp unavailable; "
                "using Tier-2 heuristic analysis"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Tier 1: LLM Inference
    # ─────────────────────────────────────────────────────────────────────────

    def _run_llm(self, content: str) -> dict:
        """
        Run LLM inference with bulletproof JSON extraction.
        Returns {} on any failure — caller falls through to heuristics.
        """
        if self._llm is None:
            return {}

        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{SYSTEM_PROMPT}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"{content[:900]}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )

        try:
            output = self._llm(
                prompt,
                max_tokens=int(os.environ.get("LLM_MAX_TOKENS", 300)),
                temperature=0.05,   # Near-deterministic for security decisions
                stop=["<|eot_id|>"],
            )
            raw = output["choices"][0]["text"].strip()
        except Exception as exc:
            logger.error(f"LLM inference error: {exc}")
            return {}

        # Pass 1: Strip markdown code fences (```json ... ```)
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        # Pass 2: Extract outermost JSON object using re.DOTALL
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            logger.warning("No JSON object found in LLM response. Raw: %s", raw[:200])
            return {}

        json_str = match.group(0)

        # Pass 3: Fix common LLM JSON artifacts
        json_str = re.sub(r",\s*\}", "}", json_str)   # trailing commas before }
        json_str = re.sub(r",\s*\]", "]", json_str)   # trailing commas before ]
        # Fix unquoted booleans that might appear as True/False (Python style)
        json_str = re.sub(r'\bTrue\b', 'true', json_str)
        json_str = re.sub(r'\bFalse\b', 'false', json_str)

        try:
            result = json.loads(json_str)
            # Validate expected keys are present
            if "is_phishing" not in result or "confidence" not in result:
                logger.warning("LLM JSON missing required keys: %s", list(result.keys()))
                return {}
            # Clamp confidence to valid range
            result["confidence"] = float(max(0.0, min(1.0, result.get("confidence", 0.0))))
            return result
        except json.JSONDecodeError as jde:
            logger.warning(f"JSON decode failed after cleanup: {jde}. String: {json_str[:300]}")
            return {}

    # ─────────────────────────────────────────────────────────────────────────
    # Tier 2: Advanced Heuristic Fallback
    # ─────────────────────────────────────────────────────────────────────────

    def _heuristic_analyze(self, content: str) -> dict:
        """
        Advanced heuristic phishing detection — runs when LLM is unavailable
        or JSON parsing fails. Never raises exceptions.

        Scoring breakdown:
          Urgency triggers   : up to 0.30
          Executive imperson : up to 0.25
          Wire transfer kws  : up to 0.25
          Credential harvest : up to 0.20
          Authority abuse    : up to 0.15
          Content entropy    : up to 0.10 (low entropy = templated attack)
        """
        signals: list[str] = []
        score: float = 0.0
        lower = content.lower()

        # Urgency language
        urgency_score = _keyword_density(content, _URGENCY_TRIGGERS)
        if urgency_score > 0:
            score += urgency_score * 0.30
            signals.append(f"urgency-language:{urgency_score:.2f}")

        # Executive impersonation
        exec_score = _keyword_density(content, _EXEC_IMPERSONATION)
        if exec_score > 0:
            score += exec_score * 0.25
            signals.append("executive-impersonation")

        # Wire transfer fraud
        wire_score = _keyword_density(content, _WIRE_TRANSFER)
        if wire_score > 0:
            score += wire_score * 0.25
            signals.append("wire-transfer-request")

        # Credential harvesting
        cred_score = _keyword_density(content, _CREDENTIAL_HARVEST)
        if cred_score > 0:
            score += cred_score * 0.20
            signals.append("credential-harvesting")

        # Authority abuse
        auth_score = _keyword_density(content, _AUTHORITY_ABUSE)
        if auth_score > 0:
            score += auth_score * 0.15
            signals.append("authority-abuse")

        # Low content entropy = templated phishing (e.g., fill-in-the-blank attacks)
        entropy = _text_entropy(content)
        if entropy < 3.5 and len(content) > 50:
            score += 0.10
            signals.append(f"low-entropy-template:{entropy:.2f}")

        # Explicit link/URL indicators without protocol
        if re.search(r'https?://\S+', lower):
            signals.append("contains-url")

        score = min(score, 1.0)
        risk_level = (
            "critical" if score >= 0.80 else
            "high"     if score >= 0.60 else
            "medium"   if score >= 0.35 else
            "low"
        )

        return {
            "is_phishing": score > 0.50,
            "confidence": round(score, 4),
            "risk_level": risk_level,
            "signals": signals,
            "explanation": (
                f"Heuristic analysis: {len(signals)} signals detected "
                f"(risk={risk_level}, score={score:.2f})"
            ),
            "_source": "heuristic",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Primary analyze() — orchestrates all 3 tiers
    # ─────────────────────────────────────────────────────────────────────────

    def analyze(
        self,
        session_id: str,
        content: str,
        url: Optional[str] = None,
        headers: Optional[dict] = None,
    ) -> dict:
        t0 = time.perf_counter()

        # ── Tier 3 baseline: URL forensics (always runs) ──────────────────────
        url_signals: list[str] = []
        url_risk_score: float = 0.0
        if url:
            url_result = self.url_forensics.analyze(url)
            url_signals = url_result.get("signals", [])
            url_risk_score = url_result.get("risk_score", 0.0)

        # ── Tier 3 baseline: Header analysis (always runs) ────────────────────
        header_signals: list[str] = []
        header_risk_score: float = 0.0
        if headers:
            try:
                hdr_result = _analyze_headers_full(headers)
                header_signals = hdr_result.get("signals", [])
                header_risk_score = hdr_result.get("risk_score", 0.0)
            except Exception as exc:
                logger.warning("Header analysis failed (non-critical): %s", exc)

        # ── Tier 1: LLM inference ─────────────────────────────────────────────
        llm_result = self._run_llm(content)

        # ── Tier 2: Heuristic fallback if LLM failed/unavailable ─────────────
        if not llm_result:
            logger.info("LLM unavailable or failed — applying Tier-2 heuristic analysis")
            llm_result = self._heuristic_analyze(content)

        llm_confidence = llm_result.get("confidence", 0.0)
        llm_signals    = llm_result.get("signals", [])

        # ── Aggregate: URL 35%, Header 15%, LLM/Heuristic 50% ────────────────
        all_signals = url_signals + header_signals + llm_signals
        total_confidence = min(
            (url_risk_score    * 0.35)
            + (header_risk_score * 0.15)
            + (llm_confidence    * 0.50),
            1.0,
        )
        is_phishing = total_confidence > 0.50

        # ── Derive risk level from final confidence ────────────────────────────
        risk_level = (
            "critical" if total_confidence >= 0.85 else
            "high"     if total_confidence >= 0.65 else
            "medium"   if total_confidence >= 0.40 else
            llm_result.get("risk_level", "low")
        )

        # ── ECDSA sign the verdict ─────────────────────────────────────────────
        payload = (
            f"{session_id}|phishing={is_phishing}"
            f"|confidence={total_confidence:.4f}"
            f"|ts={int(time.time())}"
        )
        signed_verdict, public_key_pem = self.ecdsa.sign(payload)

        return {
            "session_id":       session_id,
            "is_phishing":      is_phishing,
            "confidence":       round(total_confidence, 4),
            "risk_level":       risk_level,
            "signals":          all_signals,
            "explanation":      llm_result.get("explanation", "Multi-signal heuristic analysis"),
            "processing_time_ms": round((time.perf_counter() - t0) * 1000, 1),
            "signed_verdict":   signed_verdict,
            "public_key_pem":   public_key_pem,
            "analysis_source":  llm_result.get("_source", "llm"),
        }
