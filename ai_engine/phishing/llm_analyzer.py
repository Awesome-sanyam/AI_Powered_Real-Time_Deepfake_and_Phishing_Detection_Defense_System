"""
LLM-based Phishing Analyzer
============================
Uses a 4-bit quantized GGUF LLaMA model via llama-cpp-python.
Constrained to n_ctx=512 and 4 threads to fit within M4 memory budget.

CALIBRATION (v3 — BEC False Negative Fix):
  KEY CHANGE: Replaced the pure weighted-average aggregation with a
  Max/Trigger system to eliminate score dilution on zero-URL attacks.

  Problem fixed:
    Business Email Compromise (BEC) attacks have no URLs.
    The v2 weighted average capped BEC confidence at:
      llm_score * 0.50  (because url_score = 0, header_score ≈ 0)
    A 90%-confident LLM phishing score got diluted to ≤ 0.50, which
    was below the 0.65 PHISHING_THRESHOLD → False Negative.

  New Aggregation Formula (v3):
    base_score  = (llm_score * 0.60) + (url_score * 0.25) + (header_score * 0.15)
    final_score = max(base_score, llm_score, url_score)

    Effect: If the LLM returns 0.90 confidence (wire-fraud impersonation),
    final_score = max(0.54, 0.90, 0.0) = 0.90 → "Phishing" verdict.

  Enhanced System Prompt for BEC (v3):
    Explicit instructions to hunt for executive impersonation, urgent
    wire transfer requests, gift card demands, and payment procedure
    bypasses — all classic BEC attack vectors with zero malicious URLs.

  Threat threshold unchanged:
    0.65 — calibrated to prevent benign newsletter false positives.

3-Tier Fallback Architecture:
  Tier 1 — LLM inference (llama-cpp-python GGUF)
  Tier 2 — Advanced heuristic engine (keyword density, urgency, SPF/DKIM)
  Tier 3 — Pure URL + header signal baseline (always succeeds)

Author: Sanyam Gehlot & Alefiya
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
# Enhanced LLM System Prompt (v3) — BEC-aware with numeric anchors
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an elite cybersecurity analyst specialised in detecting phishing, \
spear-phishing, and Business Email Compromise (BEC) attacks.

CRITICAL: BEC attacks often contain ZERO malicious links. They rely entirely \
on social engineering, impersonation, and urgency. Do NOT lower your \
confidence simply because no URLs are present — absent URLs in a wire-transfer \
or gift-card request are a STRONGER indicator of BEC, not a weaker one.

Analyse the following email/message content and respond with a JSON object ONLY \
(absolutely no markdown, no preamble, no explanation outside the JSON).

SCORING GUIDANCE — assign the confidence field according to these anchors:
  0.05–0.15 : Clearly benign (newsletter, order confirmation, personal note)
  0.20–0.35 : Low suspicion (mild urgency, one ambiguous element)
  0.40–0.55 : Moderate suspicion (multiple signals, but plausibly legitimate)
  0.60–0.75 : High suspicion (clear social engineering with identity/auth pressure)
  0.80–0.95 : Near-certain phishing (executive impersonation + wire fraud/gift-card + urgency)
  0.96–1.00 : Reserve for textbook, multi-vector phishing with all attack vectors present

HUNT SPECIFICALLY FOR THESE HIGH-CONFIDENCE BEC VECTORS (no URL required):
  ★ EXECUTIVE IMPERSONATION: Sender claims to be CEO, CFO, CISO, VP, board member,
    or any senior authority figure requesting an unusual financial action.
  ★ URGENT WIRE TRANSFER: "Wire $X to this account", "transfer funds immediately",
    "new vendor account", "updated banking details", "change the payment recipient".
  ★ GIFT CARD FRAUD: "Buy iTunes/Amazon/Google Play gift cards", "send me the codes",
    "I'll reimburse you later", "don't tell anyone, it's a surprise".
  ★ PAYMENT PROCEDURE BYPASS: "Skip the normal approval process", "this is confidential",
    "don't contact finance, I'll handle it", "this must stay between us".
  ★ VENDOR/INVOICE FRAUD: "Our bank details have changed", "use this new account for
    all future payments", impersonating a known supplier.

Evaluate ALL of the following attack vectors:
  - EXECUTIVE IMPERSONATION: Pretending to be a CEO, CFO, CISO, or board member
  - WIRE TRANSFER FRAUD: Urgent requests to transfer funds or change payment details
  - GIFT CARD FRAUD: Requests to purchase gift cards and share codes
  - CREDENTIAL HARVESTING: Links or forms requesting passwords, MFA codes, SSO tokens
  - ARTIFICIAL URGENCY: "Act now", "expires in 24h", "immediate action required"
  - AUTHORITY ABUSE: Invoking HR, IT Security, Legal, Compliance, or Government authority
  - BRAND IMPERSONATION: Faking Microsoft, Google, Apple, PayPal, bank, or IRS communications
  - HOMOGLYPH ATTACKS: Subtle misspellings using look-alike characters
  - SOCIAL ENGINEERING: Creating fear, pressure, curiosity, or greed triggers
  - CONFIDENTIALITY PRESSURE: "Keep this private", "don't tell others", "time-sensitive"

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

_GIFT_CARD_FRAUD = {
    "gift card", "itunes card", "amazon gift", "google play card", "steam card",
    "send the codes", "gift voucher", "prepaid card", "buy cards",
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

_BEC_BYPASS = {
    "keep this between us", "don't tell anyone", "this is confidential",
    "bypass approval", "skip the process", "do not contact", "it's a surprise",
    "reimburse you later", "i'll explain later",
    # Additional common BEC bypass phrases
    "normal approval process", "normal process", "skip the approval",
    "stay between us", "between us", "don't run this",
    "i'll handle it", "do not run", "no need to",
}


def _text_entropy(text: str) -> float:
    """Shannon entropy of character distribution in text."""
    if not text:
        return 0.0
    freq = Counter(text.lower())
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def _keyword_density(text: str, keywords: set) -> float:
    """
    Keyword hit density with a multi-stage saturation curve.

    Calibrated hit-to-score mapping:
      0 hits  → 0.00
      1 hit   → 0.45  (single clear signal)
      2 hits  → 0.70  (two corroborating signals)
      3+ hits → 1.00  (saturation — strong multi-signal phishing)
    """
    lower = text.lower()
    hits = sum(1 for kw in keywords if kw in lower)
    if hits == 0:
        return 0.0
    if hits == 1:
        return 0.45
    if hits == 2:
        return 0.70
    return 1.0


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
        json_str = re.sub(r'\bTrue\b', 'true', json_str)
        json_str = re.sub(r'\bFalse\b', 'false', json_str)

        try:
            result = json.loads(json_str)
            if "is_phishing" not in result or "confidence" not in result:
                logger.warning("LLM JSON missing required keys: %s", list(result.keys()))
                return {}
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
          Gift card fraud    : up to 0.25  [NEW in v3]
          Credential harvest : up to 0.20
          Authority abuse    : up to 0.15
          BEC bypass phrases : up to 0.20  [NEW in v3]
          Content entropy    : up to 0.10 (low entropy = templated attack)
        """
        signals: list[str] = []
        score: float = 0.0

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

        # Gift card fraud (new v3 — classic BEC vector)
        gift_score = _keyword_density(content, _GIFT_CARD_FRAUD)
        if gift_score > 0:
            score += gift_score * 0.25
            signals.append("gift-card-fraud")

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

        # BEC bypass language (new v3 — "keep this between us", "skip approval")
        bypass_score = _keyword_density(content, _BEC_BYPASS)
        if bypass_score > 0:
            score += bypass_score * 0.20
            signals.append("bec-bypass-language")

        # Low content entropy = templated phishing
        entropy = _text_entropy(content)
        if entropy < 3.5 and len(content) > 50:
            score += 0.10
            signals.append(f"low-entropy-template:{entropy:.2f}")

        # Explicit link/URL indicators
        if re.search(r'https?://\S+', content.lower()):
            signals.append("contains-url")

        score = min(score, 1.0)

        # Cross-category convergence bonuses (cascading — higher category count = stronger bonus):
        #   ≥3 categories : +0.15 (multi-signal corroboration)
        #   ≥4 categories : +0.10 (strong multi-vector attack)
        #   ≥5 categories : +0.10 (near-certain BEC — e.g., exec+wire+urgency+bypass+auth)
        # This ensures a 5-vector BEC with all signals present scores > 0.85.
        active_categories = sum([
            urgency_score > 0,
            exec_score > 0,
            wire_score > 0,
            gift_score > 0,
            cred_score > 0,
            auth_score > 0,
            bypass_score > 0,
        ])
        if active_categories >= 5:
            score = min(score + 0.35, 1.0)
            signals.append(f"multi-vector-convergence:{active_categories}-categories")
        elif active_categories >= 4:
            score = min(score + 0.25, 1.0)
            signals.append(f"multi-vector-convergence:{active_categories}-categories")
        elif active_categories >= 3:
            score = min(score + 0.15, 1.0)
            signals.append(f"multi-vector-convergence:{active_categories}-categories")

        score = min(score, 1.0)
        risk_level = (
            "critical" if score >= 0.80 else
            "high"     if score >= 0.60 else
            "medium"   if score >= 0.35 else
            "low"
        )

        return {
            "is_phishing": score > 0.65,
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
    # v3 Max/Trigger Aggregation — fixes BEC false negatives
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _aggregate_scores(
        llm_confidence: float,
        url_score: float,
        header_score: float,
    ) -> float:
        """
        Compute final phishing confidence using the Max/Trigger system (v3).

        Problem with pure weighted average:
          BEC attacks have url_score = 0.0 and header_score ≈ 0.0.
          With v2 formula: final = llm_score * 0.50 (only content matters).
          A 90% LLM confidence becomes 0.45 → below 0.65 threshold → MISS.

        Solution — Max/Trigger (v3):
          base_score  = (llm_score * 0.60) + (url_score * 0.25) + (header_score * 0.15)
          final_score = max(base_score, llm_score, url_score)

          Now a 90% LLM score gives: max(0.54, 0.90, 0.0) = 0.90 → CATCH.
          A 70% LLM score gives:     max(0.42, 0.70, 0.0) = 0.70 → CATCH.
          A 20% LLM score gives:     max(0.12, 0.20, 0.0) = 0.20 → benign.

        The max() ensures the highest single-vector confidence is never diluted
        below its raw value by mixing in zero signals from absent URL/headers.

        Args:
            llm_confidence: LLM or heuristic phishing confidence [0, 1].
            url_score:      URL forensics risk score [0, 1].
            header_score:   Email header risk score [0, 1].

        Returns:
            float — final aggregated confidence in [0, 1].
        """
        base_score = (llm_confidence * 0.60) + (url_score * 0.25) + (header_score * 0.15)
        final_score = max(base_score, llm_confidence, url_score)
        return float(min(final_score, 1.0))

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

        # ── v3 Max/Trigger Aggregation ────────────────────────────────────────
        #
        # This replaces the v2 weighted-average + boost system.
        # The max() call ensures the highest single-vector confidence can
        # never be diluted by zero values from absent URL/header signals.
        #
        # Example — BEC attack with no URL, no suspicious headers:
        #   llm_confidence = 0.92  (wire-fraud impersonation)
        #   url_risk_score = 0.00  (no URLs present)
        #   header_risk_score = 0.03
        #   base_score = (0.92 * 0.60) + (0.00 * 0.25) + (0.03 * 0.15) = 0.556
        #   final_score = max(0.556, 0.92, 0.00) = 0.92 → "Phishing" ✅
        #
        total_confidence = self._aggregate_scores(
            llm_confidence, url_risk_score, header_risk_score
        )

        # Calibrated threshold: 0.65
        PHISHING_THRESHOLD = 0.65
        is_phishing = total_confidence >= PHISHING_THRESHOLD

        # ── Derive risk level from final confidence ────────────────────────────
        risk_level = (
            "critical" if total_confidence >= 0.85 else
            "high"     if total_confidence >= 0.65 else
            "medium"   if total_confidence >= 0.40 else
            llm_result.get("risk_level", "low")
        )

        all_signals = url_signals + header_signals + llm_signals

        logger.info(
            "Phishing analysis [%s]: llm=%.3f url=%.3f header=%.3f "
            "final=%.4f phishing=%s threshold=%.2f",
            session_id, llm_confidence, url_risk_score, header_risk_score,
            total_confidence, is_phishing, PHISHING_THRESHOLD,
        )

        # ── ECDSA sign the verdict ─────────────────────────────────────────────
        payload = (
            f"{session_id}|phishing={is_phishing}"
            f"|confidence={total_confidence:.4f}"
            f"|ts={int(time.time())}"
        )
        signed_verdict, public_key_pem = self.ecdsa.sign(payload)

        return {
            "session_id":           session_id,
            "is_phishing":          is_phishing,
            "confidence":           round(total_confidence, 4),
            "risk_level":           risk_level,
            "signals":              all_signals,
            "explanation":          llm_result.get("explanation", "Multi-signal heuristic analysis"),
            "processing_time_ms":   round((time.perf_counter() - t0) * 1000, 1),
            "signed_verdict":       signed_verdict,
            "public_key_pem":       public_key_pem,
            "analysis_source":      llm_result.get("_source", "llm"),
            # Debug fields for transparency
            "debug": {
                "llm_confidence":   round(llm_confidence, 4),
                "url_risk_score":   round(url_risk_score, 4),
                "header_risk_score": round(header_risk_score, 4),
                "aggregation":      "max_trigger_v3",
            },
        }
