#!/usr/bin/env python3
"""
Phase 2 AI Integration Test Script
====================================
Tests the CrossModalVerificationEngine and PhishingAnalyzer directly —
no network calls, no Django required. Run from the project root.

Usage:
    cd /path/to/project
    source ai_engine/.venv/bin/activate   # or: pip install -r ai_engine/requirements.txt
    python scripts/test_phase2_ai.py

Exit codes:
    0 — all assertions passed
    1 — at least one assertion failed
"""
from __future__ import annotations

import sys
import time
import logging

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

PASS = "\033[92m✅ PASS\033[0m"
FAIL = "\033[91m❌ FAIL\033[0m"
failures: list[str] = []


def assert_test(name: str, condition: bool, detail: str = "") -> None:
    """Assert a condition and track failures."""
    if condition:
        logger.info(f"{PASS}  {name}")
    else:
        msg = f"{FAIL}  {name}" + (f" — {detail}" if detail else "")
        logger.error(msg)
        failures.append(name)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: generate a synthetic BGR video frame (random noise)
# ─────────────────────────────────────────────────────────────────────────────

def make_fake_frame(h: int = 480, w: int = 640) -> np.ndarray:
    """Return a random BGR uint8 frame (simulates a camera frame)."""
    return np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)


def make_silent_audio(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Return raw 16-bit PCM mono silent audio bytes."""
    n_samples = int(duration_sec * sample_rate)
    return np.zeros(n_samples, dtype=np.int16).tobytes()


def make_noise_audio(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Return raw 16-bit PCM mono noise audio bytes."""
    n_samples = int(duration_sec * sample_rate)
    return np.random.randint(-1000, 1000, n_samples, dtype=np.int16).tobytes()


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: AudioAnalyzer
# ─────────────────────────────────────────────────────────────────────────────

def test_audio_analyzer() -> None:
    logger.info("\n── AudioAnalyzer Tests ──")
    from ai_engine.deepfake.audio_analyzer import AudioAnalyzer

    analyzer = AudioAnalyzer()

    audio_bytes = make_noise_audio(duration_sec=2.0)

    mfcc = analyzer.extract_mfcc(audio_bytes)
    assert_test("MFCC shape rows == 40", mfcc.shape[0] == 40, str(mfcc.shape))
    assert_test("MFCC has time frames", mfcc.shape[1] > 0, str(mfcc.shape))
    assert_test("MFCC dtype is float32", str(mfcc.dtype) == "float32", str(mfcc.dtype))

    rms = analyzer.extract_rms_energy(audio_bytes)
    assert_test("RMS is 1-D array", rms.ndim == 1, str(rms.shape))
    assert_test("RMS dtype is float32", str(rms.dtype) == "float32", str(rms.dtype))

    silent_audio = make_silent_audio(duration_sec=2.0)
    report = analyzer.detect_anomaly(silent_audio)
    assert_test("Anomaly returns dict with correct keys",
                {"is_anomalous", "rms_mean", "silence_ratio", "signals"}.issubset(report),
                str(report.keys()))


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: VisualArtifactDetector
# ─────────────────────────────────────────────────────────────────────────────

def test_visual_detector() -> None:
    logger.info("\n── VisualArtifactDetector Tests ──")
    from ai_engine.deepfake.visual_detector import VisualArtifactDetector

    detector = VisualArtifactDetector()  # No weights — ImageNet backbone only

    # Score a single frame
    frame = make_fake_frame()
    scores = detector.score_batch([frame])
    assert_test("score_batch returns list", isinstance(scores, list), str(type(scores)))
    assert_test("score_batch length matches input", len(scores) == 1, str(len(scores)))
    assert_test("score_batch value in [0, 1]", 0.0 <= scores[0] <= 1.0, str(scores[0]))

    # Score a batch of 5 frames (crosses sub-batch boundary of 4)
    frames = [make_fake_frame() for _ in range(5)]
    scores5 = detector.score_batch(frames)
    assert_test("score_batch(5) returns 5 scores", len(scores5) == 5, str(len(scores5)))
    assert_test(
        "all scores in [0, 1]",
        all(0.0 <= s <= 1.0 for s in scores5),
        str(scores5),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: CrossModalVerificationEngine (full pipeline)
# ─────────────────────────────────────────────────────────────────────────────

def test_cross_modal_engine() -> None:
    logger.info("\n── CrossModalVerificationEngine Tests ──")
    from ai_engine.deepfake.cross_modal_engine import (
        CrossModalVerificationEngine,
        DeepfakeVerdict,
    )
    from ai_engine.identity.ecdsa_service import ECDSAService

    engine = CrossModalVerificationEngine()

    frames = [make_fake_frame() for _ in range(8)]
    audio  = make_noise_audio(duration_sec=2.0)

    t0 = time.perf_counter()
    verdict = engine.analyze(
        session_id="test-phase2-integration",
        frames=frames,
        audio_bytes=audio,
        fps=4.0,   # 8 frames @ 4 fps = 2 seconds
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Structural checks
    assert_test("verdict is DeepfakeVerdict", isinstance(verdict, DeepfakeVerdict), str(type(verdict)))
    assert_test("session_id preserved", verdict.session_id == "test-phase2-integration")
    assert_test("is_deepfake is bool", isinstance(verdict.is_deepfake, bool))
    assert_test("confidence in [0, 1]", 0.0 <= verdict.confidence <= 1.0, str(verdict.confidence))
    assert_test("frame_results count matches", len(verdict.frame_results) == 8, str(len(verdict.frame_results)))
    assert_test("processing_time_ms > 0", verdict.processing_time_ms > 0, str(verdict.processing_time_ms))

    # ECDSA signature checks
    assert_test("signed_verdict is non-empty hex", bool(verdict.signed_verdict), str(verdict.signed_verdict))
    assert_test("public_key_pem starts with PEM header",
                (verdict.public_key_pem or "").startswith("-----BEGIN PUBLIC KEY"),
                str(verdict.public_key_pem[:40] if verdict.public_key_pem else "None"))

    # We can't reconstruct the exact timestamp from outside, so verify key format
    is_valid_format = (
        len(verdict.signed_verdict) > 0 and
        all(c in "0123456789abcdef" for c in verdict.signed_verdict.lower())
    )
    assert_test("signed_verdict is valid hex string", is_valid_format, verdict.signed_verdict[:20])

    # ECDSA round-trip verification with a fresh payload
    ecdsa = ECDSAService()
    test_sig, test_pub = ecdsa.sign("test_payload_round_trip")
    is_verified = ECDSAService.verify(test_pub, "test_payload_round_trip", test_sig)
    assert_test("ECDSA sign → verify round-trip succeeds", is_verified)

    logger.info("  Engine ran in %d ms", int(elapsed_ms))
    engine.cleanup()


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: URL Forensics
# ─────────────────────────────────────────────────────────────────────────────

def test_url_forensics() -> None:
    logger.info("\n── URL Forensics Tests ──")
    from ai_engine.phishing.url_forensics import URLForensics

    forensics = URLForensics()

    # Known-safe URL
    result_safe = forensics.analyze("https://www.google.com/search?q=test")
    assert_test("Safe URL risk_score < 0.3", result_safe["risk_score"] < 0.3, str(result_safe["risk_score"]))

    # Highly suspicious URL
    result_sus = forensics.analyze("http://paypal-secure-verify.tk/login/account/update")
    assert_test("Phishing URL risk_score >= 0.5",
                result_sus["risk_score"] >= 0.5,
                str(result_sus["risk_score"]))
    assert_test("Phishing URL has signals", len(result_sus["signals"]) > 0, str(result_sus["signals"]))
    assert_test("Suspicious TLD detected",
                any("suspicious-tld" in s for s in result_sus["signals"]),
                str(result_sus["signals"]))
    assert_test("Brand impersonation detected",
                any("brand-impersonation" in s for s in result_sus["signals"]),
                str(result_sus["signals"]))


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Header Analyzer
# ─────────────────────────────────────────────────────────────────────────────

def test_header_analyzer() -> None:
    logger.info("\n── Header Analyzer Tests ──")
    from ai_engine.phishing.header_analyzer import analyze_headers

    # Suspicious headers
    suspicious = {
        "From": "PayPal <noreply@evil.com>",
        "Reply-To": "attacker@phish.com",
        "Received-SPF": "fail (domain of evil.com does not permit...)",
        "X-Mailer": "PHPMailer 6.2",
    }
    result = analyze_headers(suspicious)
    assert_test("Header analysis returns signals", len(result["signals"]) > 0, str(result["signals"]))
    assert_test("Reply-To mismatch detected",
                "reply-to-from-mismatch" in result["signals"],
                str(result["signals"]))
    assert_test("SPF fail detected",
                "spf-fail" in result["signals"],
                str(result["signals"]))
    assert_test("Missing DKIM detected",
                "missing-dkim" in result["signals"],
                str(result["signals"]))
    assert_test("Risk score > 0", result["risk_score"] > 0, str(result["risk_score"]))


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: ECDSA Verdict Signer
# ─────────────────────────────────────────────────────────────────────────────

def test_verdict_signer() -> None:
    logger.info("\n── Verdict Signer Tests ──")
    from ai_engine.phishing.verdict_signer import sign_verdict

    test_verdict = {
        "session_id": "test-sign-001",
        "is_phishing": True,
        "confidence": 0.87,
        "risk_level": "high",
        "signals": ["missing-dkim", "spf-fail"],
    }

    signed = sign_verdict(test_verdict)
    assert_test("signed_verdict key present", "signed_verdict" in signed)
    assert_test("public_key_pem key present", "public_key_pem" in signed)
    assert_test("signed_verdict non-empty", bool(signed["signed_verdict"]))
    assert_test("public_key_pem is PEM",
                signed["public_key_pem"].startswith("-----BEGIN PUBLIC KEY"),
                signed["public_key_pem"][:40])


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 60)
    logger.info("Phase 2 AI Integration Tests")
    logger.info("=" * 60)

    suites = [
        ("AudioAnalyzer",              test_audio_analyzer),
        ("VisualArtifactDetector",     test_visual_detector),
        ("CrossModalVerificationEngine", test_cross_modal_engine),
        ("URL Forensics",              test_url_forensics),
        ("Header Analyzer",            test_header_analyzer),
        ("Verdict Signer",             test_verdict_signer),
    ]

    for name, fn in suites:
        try:
            fn()
        except Exception as exc:
            logger.exception(f"Test suite '{name}' raised an exception: {exc}")
            failures.append(f"{name} (exception)")

    logger.info("\n" + "=" * 60)
    if failures:
        logger.error(f"❌  {len(failures)} test(s) FAILED: {failures}")
        sys.exit(1)
    else:
        logger.info("✅  All tests PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
