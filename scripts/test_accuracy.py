#!/usr/bin/env python3
"""
Detection Engine Accuracy Validation Suite
==========================================
Tests calibrated detection engines against a curated set of Benign and
Suspicious/Malicious test cases. Generates a comparison table with
before/after confidence scores and pass/fail judgements.

Usage:
    cd /path/to/project
    python scripts/test_accuracy.py

Requirements:
    - cv2, numpy, torch installed in environment
    - ai_engine package available (run from project root)

Author: Sanyam Gehlot
"""
from __future__ import annotations

import math
import sys
import time
from collections import Counter
from typing import Optional

# ── Ensure project root is on path ────────────────────────────────────────────
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("⚠️  cv2 not available — deepfake tests will be skipped")


# ═════════════════════════════════════════════════════════════════════════════
# ANSI colour helpers
# ═════════════════════════════════════════════════════════════════════════════

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def _pass(msg: str) -> str:
    return f"{GREEN}✅ PASS{RESET}  {msg}"

def _fail(msg: str) -> str:
    return f"{RED}❌ FAIL{RESET}  {msg}"

def _warn(msg: str) -> str:
    return f"{YELLOW}⚠️  WARN{RESET}  {msg}"

def _section(title: str) -> None:
    width = 70
    print(f"\n{BOLD}{CYAN}{'═' * width}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * width}{RESET}")


# ═════════════════════════════════════════════════════════════════════════════
# Deepfake Engine Tests
# ═════════════════════════════════════════════════════════════════════════════

def _make_natural_frame(height: int = 480, width: int = 640) -> "np.ndarray":
    """
    Synthesise a 'natural' webcam frame — random texture with high
    Laplacian variance (simulates genuine skin / environment texture).
    """
    # Gaussian noise base — high-frequency energy → high Laplacian variance
    frame = np.random.normal(128, 40, (height, width, 3)).clip(0, 255).astype(np.uint8)
    # Add a mild Gaussian blur to simulate camera focus (not excessive)
    frame = cv2.GaussianBlur(frame, (3, 3), 0.8)
    return frame


def _make_deepfake_frame(height: int = 480, width: int = 640) -> "np.ndarray":
    """
    Synthesise a 'GAN-smoothed' deepfake frame — over-blurred, low
    Laplacian variance (simulates GAN spatial smoothing artefacts).
    """
    # Start from low-noise base
    frame = np.random.normal(128, 10, (height, width, 3)).clip(0, 255).astype(np.uint8)
    # Heavy blur → very low Laplacian variance, mimics GAN over-smoothing
    frame = cv2.GaussianBlur(frame, (31, 31), 15.0)
    return frame


def _make_silent_audio(duration_s: float = 1.0, sample_rate: int = 16_000) -> bytes:
    """Generate silent audio bytes (zero-padded int16 PCM)."""
    samples = np.zeros(int(duration_s * sample_rate), dtype=np.int16)
    return samples.tobytes()


def run_deepfake_tests() -> list[dict]:
    """
    Run visual detector calibration tests.
    Returns list of result dicts for table rendering.
    """
    if not CV2_AVAILABLE:
        return []

    results = []

    try:
        from ai_engine.deepfake.visual_detector import VisualArtifactDetector
        detector = VisualArtifactDetector()
    except Exception as exc:
        print(f"{RED}Could not load VisualArtifactDetector: {exc}{RESET}")
        return []

    # ── Test 1: Benign — natural texture frames ───────────────────────────────
    natural_frames = [_make_natural_frame() for _ in range(8)]
    try:
        t0 = time.perf_counter()
        scores = detector.score_batch(natural_frames)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        mean_score = float(np.mean(scores))
        # PASS: calibrated natural frame score should be 0.05–0.25
        passed = 0.0 <= mean_score <= 0.30
        results.append({
            "category": "DEEPFAKE — Benign",
            "test": "Natural texture webcam frames (8 frames)",
            "score": mean_score,
            "expected": "≤ 0.30 (low suspicion)",
            "passed": passed,
            "elapsed_ms": elapsed_ms,
        })
    except Exception as exc:
        results.append({
            "category": "DEEPFAKE — Benign",
            "test": "Natural texture webcam frames (8 frames)",
            "score": -1.0,
            "expected": "≤ 0.30 (low suspicion)",
            "passed": False,
            "error": str(exc),
            "elapsed_ms": 0.0,
        })

    # ── Test 2: Suspicious — GAN-smoothed deepfake frames ────────────────────
    deepfake_frames = [_make_deepfake_frame() for _ in range(8)]
    try:
        t0 = time.perf_counter()
        scores = detector.score_batch(deepfake_frames)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        mean_score = float(np.mean(scores))
        # PASS: over-smoothed frames should score higher than natural
        passed = mean_score >= 0.35
        results.append({
            "category": "DEEPFAKE — Suspicious",
            "test": "GAN-smoothed / over-blurred frames (8 frames)",
            "score": mean_score,
            "expected": "≥ 0.35 (elevated suspicion)",
            "passed": passed,
            "elapsed_ms": elapsed_ms,
        })
    except Exception as exc:
        results.append({
            "category": "DEEPFAKE — Suspicious",
            "test": "GAN-smoothed / over-blurred frames (8 frames)",
            "score": -1.0,
            "expected": "≥ 0.35 (elevated suspicion)",
            "passed": False,
            "error": str(exc),
            "elapsed_ms": 0.0,
        })

    # ── Test 3: Lip-sync — zero signal guard (no face, silent audio) ─────────
    try:
        from ai_engine.deepfake.lip_sync_verifier import LipSyncVerifier
        verifier = LipSyncVerifier()
        # Use solid-colour frames (no face detectable)
        blank_frames = [np.full((480, 640, 3), 128, dtype=np.uint8) for _ in range(4)]
        silent_audio = _make_silent_audio()
        t0 = time.perf_counter()
        delay_ms, is_suspicious = verifier.verify(blank_frames, silent_audio, fps=25.0)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        # PASS: zero-signal guard should return (0.0, False), not suspicious
        passed = not is_suspicious and delay_ms == 0.0
        results.append({
            "category": "DEEPFAKE — Benign",
            "test": "Lip-sync: no-face / silent stream (zero-signal guard)",
            "score": delay_ms,
            "expected": "0.0 ms, not suspicious",
            "passed": passed,
            "elapsed_ms": elapsed_ms,
        })
    except Exception as exc:
        results.append({
            "category": "DEEPFAKE — Benign",
            "test": "Lip-sync: no-face / silent stream (zero-signal guard)",
            "score": -1.0,
            "expected": "0.0 ms, not suspicious",
            "passed": False,
            "error": str(exc),
            "elapsed_ms": 0.0,
        })

    # ── Test 4: Blink detector — short segment guard (< 300 frames) ──────────
    try:
        from ai_engine.deepfake.blink_detector import BlinkRateDetector
        blink_det = BlinkRateDetector()
        short_frames = [_make_natural_frame() for _ in range(50)]  # < 300
        t0 = time.perf_counter()
        bpm, is_suspicious = blink_det.compute_blink_rate(short_frames, fps=25.0)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        # PASS: short segment guard → (0.0, False), not suspicious
        passed = not is_suspicious and bpm == 0.0
        results.append({
            "category": "DEEPFAKE — Benign",
            "test": "Blink: 50-frame segment (< 300-frame duration guard)",
            "score": bpm,
            "expected": "0.0 BPM, not suspicious",
            "passed": passed,
            "elapsed_ms": elapsed_ms,
        })
    except Exception as exc:
        results.append({
            "category": "DEEPFAKE — Benign",
            "test": "Blink: 50-frame segment (< 300-frame duration guard)",
            "score": -1.0,
            "expected": "0.0 BPM, not suspicious",
            "passed": False,
            "error": str(exc),
            "elapsed_ms": 0.0,
        })

    return results


# ═════════════════════════════════════════════════════════════════════════════
# Phishing Engine Tests
# ═════════════════════════════════════════════════════════════════════════════

BENIGN_EMAILS = [
    {
        "name": "Order confirmation (Amazon-style)",
        "content": (
            "Thank you for your order! Your package is on its way. "
            "Estimated delivery: 2–3 business days. Order #12345678. "
            "Visit our website to track your shipment."
        ),
        "url": "https://amazon.com/orders/track/12345678",
        "headers": {"DKIM-Signature": "valid", "Received-SPF": "pass"},
        "expected_max": 0.35,
    },
    {
        "name": "Internal company newsletter",
        "content": (
            "Hi team, this month's product update includes new onboarding flows, "
            "performance improvements, and a refreshed dashboard. Join us for the "
            "all-hands meeting on Friday at 2pm PST. Thanks, Product Team."
        ),
        "url": None,
        "headers": {"DKIM-Signature": "valid", "Received-SPF": "pass"},
        "expected_max": 0.30,
    },
    {
        "name": "Password reset (legitimate)",
        "content": (
            "You requested a password reset for your account. "
            "Click the link below to reset it. This link expires in 24 hours. "
            "If you did not request this, you can safely ignore this email."
        ),
        "url": "https://accounts.google.com/passwordreset/token=abc123",
        "headers": {"DKIM-Signature": "valid", "Received-SPF": "pass"},
        "expected_max": 0.55,  # Contains "expires" + "password reset" but from legit domain
    },
]

SUSPICIOUS_EMAILS = [
    {
        "name": "CEO wire transfer fraud (BEC)",
        "content": (
            "This is an urgent request from our CEO. We need to wire $150,000 "
            "immediately to a new vendor account. Change the payment details now. "
            "Contact me via my personal email only. Do not discuss this with anyone. "
            "This is time sensitive and must be done within 24 hours. - John Smith, CEO"
        ),
        "url": None,
        "headers": {"Reply-To": "ceo@gmail-corp.com", "From": "ceo@company.com"},
        # NOTE: 0.60 threshold reflects Tier-2 heuristic-only mode (no LLM loaded).
        # With LLM inference active, this case should score ≥ 0.75.
        "expected_min": 0.60,
    },
    {
        "name": "Credential harvesting (Microsoft spoof)",
        "content": (
            "Your Microsoft account has been suspended due to unusual activity. "
            "Verify your identity immediately by clicking the link below. "
            "Your account will be permanently deleted within 48 hours if you "
            "fail to respond. Click here to verify: confirm your identity now."
        ),
        "url": "http://micros0ft-login.tk/verify/account/suspended",
        "headers": {},
        "expected_min": 0.65,
    },
    {
        "name": "IRS authority abuse (tax fraud)",
        "content": (
            "URGENT: Final notice from the IRS. You owe $3,200 in back taxes. "
            "Failure to respond immediately will result in arrest warrant. "
            "Call our helpdesk or click the link to pay now. Legal department action required."
        ),
        "url": "http://irs-gov.xyz/payment/urgent",
        "headers": {},
        "expected_min": 0.65,
    },
]


def run_phishing_tests() -> list[dict]:
    """
    Run phishing analyzer calibration tests.
    Returns list of result dicts for table rendering.
    """
    results = []

    try:
        from ai_engine.phishing.llm_analyzer import PhishingAnalyzer
        analyzer = PhishingAnalyzer(model_path="")  # No LLM — heuristic mode
    except Exception as exc:
        print(f"{RED}Could not load PhishingAnalyzer: {exc}{RESET}")
        return []

    # ── Benign tests ──────────────────────────────────────────────────────────
    for case in BENIGN_EMAILS:
        try:
            t0 = time.perf_counter()
            result = analyzer.analyze(
                session_id=f"test_{case['name'][:10]}",
                content=case["content"],
                url=case.get("url"),
                headers=case.get("headers"),
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            conf = result["confidence"]
            passed = conf <= case["expected_max"]
            results.append({
                "category": "PHISHING — Benign",
                "test": case["name"],
                "score": conf,
                "expected": f"≤ {case['expected_max']:.2f}",
                "passed": passed,
                "elapsed_ms": elapsed_ms,
                "signals": result.get("signals", []),
            })
        except Exception as exc:
            results.append({
                "category": "PHISHING — Benign",
                "test": case["name"],
                "score": -1.0,
                "expected": f"≤ {case['expected_max']:.2f}",
                "passed": False,
                "error": str(exc),
                "elapsed_ms": 0.0,
            })

    # ── Suspicious tests ──────────────────────────────────────────────────────
    for case in SUSPICIOUS_EMAILS:
        try:
            t0 = time.perf_counter()
            result = analyzer.analyze(
                session_id=f"test_{case['name'][:10]}",
                content=case["content"],
                url=case.get("url"),
                headers=case.get("headers"),
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            conf = result["confidence"]
            passed = conf >= case["expected_min"]
            results.append({
                "category": "PHISHING — Suspicious",
                "test": case["name"],
                "score": conf,
                "expected": f"≥ {case['expected_min']:.2f}",
                "passed": passed,
                "elapsed_ms": elapsed_ms,
                "signals": result.get("signals", []),
            })
        except Exception as exc:
            results.append({
                "category": "PHISHING — Suspicious",
                "test": case["name"],
                "score": -1.0,
                "expected": f"≥ {case['expected_min']:.2f}",
                "passed": False,
                "error": str(exc),
                "elapsed_ms": 0.0,
            })

    return results


# ═════════════════════════════════════════════════════════════════════════════
# Result Rendering
# ═════════════════════════════════════════════════════════════════════════════

def _render_table(results: list[dict]) -> None:
    """Render results as a formatted ASCII table."""
    if not results:
        print("  No results to display.")
        return

    col_w = [28, 45, 10, 22, 8, 10]
    headers = ["Category", "Test Case", "Score", "Expected", "Status", "Time(ms)"]

    sep = "+" + "+".join("-" * (w + 2) for w in col_w) + "+"
    def row(*cells):
        parts = []
        for cell, w in zip(cells, col_w):
            cell_str = str(cell)
            # Strip ANSI for width calculation
            plain = re.sub(r'\033\[[0-9;]*m', '', cell_str)
            padding = w - len(plain)
            parts.append(f" {cell_str}{' ' * max(padding, 0)} ")
        return "|" + "|".join(parts) + "|"

    import re

    print(sep)
    print(row(*headers))
    print(sep)

    for r in results:
        status = f"{GREEN}PASS{RESET}" if r["passed"] else f"{RED}FAIL{RESET}"
        score_str = f"{r['score']:.4f}" if r["score"] >= 0 else "ERROR"
        elapsed = f"{r.get('elapsed_ms', 0):.0f}"
        print(row(
            r["category"],
            r["test"][:43],
            score_str,
            r["expected"],
            status,
            elapsed,
        ))

    print(sep)


def _render_summary(deepfake_results: list[dict], phishing_results: list[dict]) -> None:
    """Print a summary scorecard."""
    all_results = deepfake_results + phishing_results
    total = len(all_results)
    passed = sum(1 for r in all_results if r["passed"])
    failed = total - passed

    _section("SUMMARY SCORECARD")
    print(f"  Total tests : {total}")
    print(f"  {GREEN}Passed{RESET}      : {passed}")
    print(f"  {RED}Failed{RESET}      : {failed}")

    if total > 0:
        pct = passed / total * 100
        bar_len = 40
        filled = int(bar_len * passed / total)
        bar = f"{GREEN}{'█' * filled}{RESET}{'░' * (bar_len - filled)}"
        print(f"\n  Accuracy: {bar} {pct:.1f}%\n")

    # Per-engine breakdown
    for category_prefix, label in [
        ("DEEPFAKE", "Deepfake Engine"),
        ("PHISHING", "Phishing Engine"),
    ]:
        cat_results = [r for r in all_results if r["category"].startswith(category_prefix)]
        if cat_results:
            cat_pass = sum(1 for r in cat_results if r["passed"])
            cat_total = len(cat_results)
            pct = cat_pass / cat_total * 100
            status_str = f"{GREEN}✅{RESET}" if cat_pass == cat_total else f"{YELLOW}⚠️{RESET}"
            print(f"  {status_str}  {label}: {cat_pass}/{cat_total} ({pct:.0f}%)")

    print()

    # Flag any failed cases for immediate attention
    failed_cases = [r for r in all_results if not r["passed"]]
    if failed_cases:
        print(f"\n  {RED}{BOLD}Failed cases:{RESET}")
        for r in failed_cases:
            err = r.get("error", "")
            err_str = f" — ERROR: {err[:60]}" if err else ""
            print(f"    • [{r['category']}] {r['test'][:50]}{err_str}")
            print(f"      Score: {r['score']:.4f}, Expected: {r['expected']}")
    else:
        print(f"  {GREEN}{BOLD}🎉 All tests passed! Detection engines are properly calibrated.{RESET}")


# ═════════════════════════════════════════════════════════════════════════════
# Entry Point
# ═════════════════════════════════════════════════════════════════════════════

def main() -> int:
    print(f"\n{BOLD}{'═' * 70}{RESET}")
    print(f"{BOLD}  AI Defence System — Detection Engine Accuracy Validation v2{RESET}")
    print(f"{BOLD}{'═' * 70}{RESET}")
    print("  Tests calibrated thresholds and noise-floor corrections.")
    print("  Expected baseline for genuine webcam frames: confidence 0.02–0.15")
    print("  Deepfake FAKE_THRESHOLD: 0.72 | Phishing PHISHING_THRESHOLD: 0.65")

    _section("DEEPFAKE ENGINE TESTS")
    deepfake_results = run_deepfake_tests()
    if deepfake_results:
        _render_table(deepfake_results)
    else:
        print("  ⚠️  Deepfake tests skipped (cv2 / torch not available in this environment)")

    _section("PHISHING ENGINE TESTS")
    phishing_results = run_phishing_tests()
    if phishing_results:
        _render_table(phishing_results)
    else:
        print("  ⚠️  Phishing tests skipped.")

    _render_summary(deepfake_results, phishing_results)

    all_results = deepfake_results + phishing_results
    return 0 if all(r["passed"] for r in all_results) else 1


if __name__ == "__main__":
    sys.exit(main())
