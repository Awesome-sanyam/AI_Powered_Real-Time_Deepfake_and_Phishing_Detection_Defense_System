#!/usr/bin/env python3
"""
scripts/demo_dry_run.py
=======================
Emergency Showcase-Grade Dry Run Verification
----------------------------------------------
Verifies that both the Deepfake and Phishing AI engines produce decisive,
unambiguous threat verdicts (> 0.85 confidence) for tomorrow's final
hackathon showcase:

  1. Deepfake Engine:
     Pushes a synthetic GAN face frame (low Laplacian spatial frequency)
     through CrossModalVerificationEngine (now powered by EfficientNet-B0
     and confidence polarization).
     Expected: confidence > 0.85 (Meters slam to RED).

  2. Phishing Engine:
     Pushes a high-threat BEC (Business Email Compromise) wire-transfer
     payload through PhishingAnalyzer (powered by deterministic keyword
     multipliers and strict JSON intent analysis).
     Expected: confidence > 0.85 (Meters slam to RED).

Author: Sanyam Gehlot & Alefiya
"""
from __future__ import annotations

import os
import sys
import time
import cv2
import numpy as np

# Ensure project root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ANSI terminal colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def run_deepfake_dry_run() -> bool:
    """Test deepfake engine on a synthetic GAN face crop."""
    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{CYAN}  🎥 1. DEEPFAKE ENGINE: EFFICIENTNET-B0 & POLARIZATION TEST  {RESET}")
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════════════{RESET}")

    from ai_engine.deepfake.cross_modal_engine import CrossModalVerificationEngine
    import ai_engine.deepfake.visual_detector as vd

    # Generate synthetic GAN over-smooth face frame
    smooth_frame = np.full((480, 640, 3), 180, dtype=np.uint8)
    cv2.circle(smooth_frame, (320, 240), 120, (200, 200, 200), -1)

    # 1 second of silent 16kHz PCM audio
    dummy_audio = bytes(32000)

    engine = CrossModalVerificationEngine()

    # Simulate face region detection on deepfake frame
    orig_extract = vd.extract_face_crop
    vd.extract_face_crop = lambda f: (f, True)

    t0 = time.perf_counter()
    try:
        verdict = engine.analyze(
            session_id="showcase-demo-deepfake",
            frames=[smooth_frame] * 4,
            audio_bytes=dummy_audio,
            fps=25.0,
        )
    finally:
        vd.extract_face_crop = orig_extract

    elapsed = (time.perf_counter() - t0) * 1000

    print(f"  Confidence Score    : {BOLD}{verdict.confidence:.4f}{RESET} ({verdict.confidence * 100:.1f}%)")
    print(f"  Is Deepfake Threat  : {BOLD}{verdict.is_deepfake}{RESET}")
    print(f"  Visual Model Score  : {verdict.mean_visual_score:.4f}")
    print(f"  Polarization Active : {verdict.polarization_triggered}")
    print(f"  Override Triggered  : {verdict.visual_override_triggered}")
    print(f"  Processing Time     : {elapsed:.1f}ms")

    passed = verdict.confidence > 0.85 and verdict.is_deepfake is True
    if passed:
        print(f"\n  {BOLD}{GREEN}✅ PASS: Deepfake engine yielded decisive threat confidence > 0.85!{RESET}")
    else:
        print(f"\n  {BOLD}{RED}❌ FAIL: Deepfake engine confidence ({verdict.confidence:.2f}) is not > 0.85{RESET}")
    return passed


def run_phishing_dry_run() -> bool:
    """Test phishing engine on a blatant BEC wire-transfer payload."""
    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{CYAN}  🎣 2. PHISHING ENGINE: DETERMINISTIC KEYWORD TRIGGER TEST   {RESET}")
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════════════{RESET}")

    from ai_engine.phishing.llm_analyzer import PhishingAnalyzer

    # Blatant BEC (Business Email Compromise) wire transfer text payload
    bec_payload = (
        "URGENT: Executive Management Wire Transfer Request\n\n"
        "Hi Finance Team,\n"
        "This is an urgent request from the CEO. Please initiate an immediate wire transfer "
        "of $75,000 to our new supplier account before 4:00 PM today. "
        "Normal purchase approval procedures are suspended for this transaction due to confidentiality. "
        "Verify your identity and confirm completion immediately.\n\n"
        "Regards,\n"
        "Office of the Chief Executive Officer"
    )

    analyzer = PhishingAnalyzer()

    t0 = time.perf_counter()
    result = analyzer.analyze(
        session_id="showcase-demo-bec",
        content=bec_payload,
        url=None,
        headers=None,
    )
    elapsed = (time.perf_counter() - t0) * 1000

    print(f"  Confidence Score    : {BOLD}{result['confidence']:.4f}{RESET} ({result['confidence'] * 100:.1f}%)")
    print(f"  Is Phishing Threat  : {BOLD}{result['is_phishing']}{RESET}")
    print(f"  Risk Level          : {BOLD}{result['risk_level'].upper()}{RESET}")
    print(f"  Detected Signals    : {result['signals']}")
    print(f"  Analysis Source     : {result.get('analysis_source', 'heuristic')}")
    print(f"  Processing Time     : {elapsed:.1f}ms")

    passed = result["confidence"] > 0.85 and result["is_phishing"] is True
    if passed:
        print(f"\n  {BOLD}{GREEN}✅ PASS: Phishing engine yielded decisive threat confidence > 0.85!{RESET}")
    else:
        print(f"\n  {BOLD}{RED}❌ FAIL: Phishing engine confidence ({result['confidence']:.2f}) is not > 0.85{RESET}")
    return passed


def main() -> int:
    print(f"\n{BOLD}{YELLOW}══════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{YELLOW}    AI DEFENCE SYSTEM — EMERGENCY SHOWCASE CALIBRATION DRY RUN   {RESET}")
    print(f"{BOLD}{YELLOW}══════════════════════════════════════════════════════════════{RESET}")

    deepfake_passed = run_deepfake_dry_run()
    phishing_passed = run_phishing_dry_run()

    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{CYAN}                      DRY RUN SUMMARY                          {RESET}")
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════════════{RESET}")
    print(f"  Deepfake Engine  : {'✅ PASS (>0.85 Decisive Fake)' if deepfake_passed else '❌ FAIL'}")
    print(f"  Phishing Engine  : {'✅ PASS (>0.85 Decisive Threat)' if phishing_passed else '❌ FAIL'}")

    all_passed = deepfake_passed and phishing_passed
    if all_passed:
        print(f"\n{BOLD}{GREEN}🎉 SHOWCASE READY: Both engines will slam UI meters to decisive threat zones!{RESET}\n")
        return 0
    else:
        print(f"\n{BOLD}{RED}⚠️ SHOWCASE CALIBRATION INCOMPLETE: One or more engines failed.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
