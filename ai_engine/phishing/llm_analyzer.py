"""
LLM-based Phishing Analyzer
============================
Uses a 4-bit quantized GGUF LLaMA model via llama-cpp-python.
Constrained to n_ctx=512 and 4 threads to fit within M4 memory budget.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional

from ai_engine.identity.ecdsa_service import ECDSAService
from ai_engine.phishing.url_forensics import URLForensics

logger = logging.getLogger(__name__)

# Lazy import — llama_cpp only loaded when this module is instantiated
try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False
    logger.warning("llama-cpp-python not installed — LLM analysis disabled")

SYSTEM_PROMPT = """You are a cybersecurity expert specialising in phishing detection.
Analyse the following content and respond with a JSON object ONLY (no markdown) with these exact fields:
{
  "is_phishing": true/false,
  "confidence": 0.0-1.0,
  "signals": ["list", "of", "detected", "signals"],
  "risk_level": "low|medium|high|critical",
  "explanation": "brief explanation"
}"""


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
            self._llm = Llama(
                model_path=model_path,
                n_ctx=int(os.environ.get("LLM_N_CTX", 512)),
                n_threads=int(os.environ.get("LLM_N_THREADS", 4)),
                n_gpu_layers=-1,   # Offload all layers to MPS (Apple Metal)
                verbose=False,
            )
            logger.info("✅ GGUF LLM loaded")
        else:
            logger.warning(f"GGUF model not found at {model_path}; using heuristics only")

    def _run_llm(self, content: str) -> dict:
        """Run LLM inference and parse JSON verdict."""
        if self._llm is None:
            return {}
        prompt = f"[INST] <<SYS>>\n{SYSTEM_PROMPT}\n<</SYS>>\n\n{content[:800]} [/INST]"
        try:
            output = self._llm(
                prompt,
                max_tokens=int(os.environ.get("LLM_MAX_TOKENS", 256)),
                temperature=0.1,
                stop=["</s>", "[INST]"],
            )
            raw = output["choices"][0]["text"].strip()
            # Extract JSON from response
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as exc:
            logger.error(f"LLM inference error: {exc}")
        return {}

    def analyze(
        self,
        session_id: str,
        content: str,
        url: Optional[str] = None,
        headers: Optional[dict] = None,
    ) -> dict:
        t0 = time.perf_counter()

        # 1. URL forensics (fast heuristics)
        url_signals = []
        url_risk_score = 0.0
        if url:
            url_result = self.url_forensics.analyze(url)
            url_signals = url_result.get("signals", [])
            url_risk_score = url_result.get("risk_score", 0.0)

        # 2. Header analysis
        header_signals = []
        if headers:
            header_signals = self._analyze_headers(headers)

        # 3. LLM intent analysis
        llm_result = self._run_llm(content)
        llm_confidence = llm_result.get("confidence", 0.0)
        llm_signals = llm_result.get("signals", [])

        # 4. Aggregate
        all_signals = url_signals + header_signals + llm_signals
        total_confidence = min(
            (url_risk_score * 0.35) + (len(header_signals) * 0.1) + (llm_confidence * 0.55),
            1.0,
        )
        is_phishing = total_confidence > 0.5

        # 5. Sign verdict
        payload = f"{session_id}|phishing={is_phishing}|confidence={total_confidence:.4f}|ts={int(time.time())}"
        signed_verdict, public_key_pem = self.ecdsa.sign(payload)

        return {
            "session_id": session_id,
            "is_phishing": is_phishing,
            "confidence": round(total_confidence, 4),
            "risk_level": llm_result.get("risk_level", "unknown"),
            "signals": all_signals,
            "explanation": llm_result.get("explanation", "Heuristic analysis only"),
            "processing_time_ms": round((time.perf_counter() - t0) * 1000, 1),
            "signed_verdict": signed_verdict,
            "public_key_pem": public_key_pem,
        }

    @staticmethod
    def _analyze_headers(headers: dict) -> list[str]:
        signals = []
        from_addr = headers.get("From", "")
        reply_to = headers.get("Reply-To", "")
        if reply_to and reply_to != from_addr:
            signals.append("reply-to-from-mismatch")
        if not headers.get("DKIM-Signature"):
            signals.append("missing-dkim")
        spf = headers.get("Received-SPF", "")
        if "fail" in spf.lower():
            signals.append("spf-fail")
        return signals
