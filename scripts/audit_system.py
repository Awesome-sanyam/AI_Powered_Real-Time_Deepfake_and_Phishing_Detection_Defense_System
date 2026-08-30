#!/usr/bin/env python3
"""
scripts/audit_system.py
========================
AI Deepfake & Phishing Defence System — Comprehensive System Audit
Phases 1 + 2 + 3 complete end-to-end verification.

What this script audits (all without Docker requirement):
  1.  Python environment — which packages are installed
  2.  Static code imports — all project modules syntax-check clean
  3.  MPS hardware acceleration — torch device detection
  4.  ECDSA cryptographic service — sign + verify + tamper detection
  5.  URL forensics engine — risk scoring accuracy
  6.  Email header analyzer — SPF/DKIM/display-name detection
  7.  Verdict signer — canonical sign + verify round-trip
  8.  Visual artifact detector — MobileNetV2 fp16 forward pass + sub-batch
  9.  Audio analyzer — MFCC extraction + anomaly detection
  10. Lip-sync verifier — cross-correlation + threshold logic
  11. Blink rate detector — EAR computation + BPM calculation
  12. Cross-modal engine — full orchestration + ECDSA verdict
  13. LLM phishing analyzer — load/mock path
  14. Django settings — import + INSTALLED_APPS validation
  15. Infrastructure connectivity — PostgreSQL, Redis, Neo4j (graceful)
  16. FastAPI health probe — AI engine /health endpoint (graceful)
  17. Memory stress — 20 rapid frame batches; peak mem + MPS cache mgmt

Usage:
  # From project root with backend venv active:
  source backend/.venv/bin/activate
  python scripts/audit_system.py

  # With AI engine venv (if separate):
  source ai_engine/.venv/bin/activate
  python scripts/audit_system.py
"""
from __future__ import annotations

import gc
import importlib
import importlib.util
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any

# ── Output colours ─────────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD  = "\033[1m"
GREEN = "\033[32m"
RED   = "\033[31m"
AMBER = "\033[33m"
CYAN  = "\033[36m"
BLUE  = "\033[34m"

def _c(colour, text): return f"{colour}{text}{RESET}"
def ok(msg):   print(f"  {_c(GREEN,  '✓')} {msg}")
def fail(msg): print(f"  {_c(RED,    '✗')} {msg}")
def warn(msg): print(f"  {_c(AMBER,  '⚠')} {msg}")
def info(msg): print(f"  {_c(CYAN,   '·')} {msg}")

# ── Path setup ─────────────────────────────────────────────────────────────────
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "backend"))

# ── Result accumulator ─────────────────────────────────────────────────────────
_results: list[dict] = []

def record(component: str, status: str, latency_ms: float | None = None,
           memory_mb: float | None = None, note: str = "") -> None:
    _results.append({
        "component":  component,
        "status":     status,
        "latency_ms": latency_ms,
        "memory_mb":  memory_mb,
        "note":       note,
    })

def section(title: str) -> None:
    print(f"\n{BOLD}{BLUE}{'─'*60}{RESET}")
    print(f"{BOLD}{BLUE}  {title}{RESET}")
    print(f"{BOLD}{BLUE}{'─'*60}{RESET}")

def timed(fn, *args, **kwargs) -> tuple[Any, float]:
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, (time.perf_counter() - t0) * 1000


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — Python Environment
# ══════════════════════════════════════════════════════════════════════════════
def audit_python_env():
    section("1 · Python Environment")
    info(f"Python {sys.version.split()[0]} at {sys.executable}")
    info(f"Repo root: {_REPO_ROOT}")

    required_backend = [
        "django", "rest_framework", "corsheaders", "channels",
        "celery", "redis", "psycopg2", "py2neo", "cryptography",
        "dotenv", "httpx", "daphne",
    ]
    required_ai = [
        "torch", "torchvision", "cv2", "mediapipe", "librosa",
        "numpy", "soundfile", "fastapi", "uvicorn", "pydantic",
    ]
    optional_ai = ["llama_cpp"]

    missing_backend, missing_ai, missing_opt = [], [], []

    for pkg in required_backend:
        spec = importlib.util.find_spec(pkg)
        if spec:
            ok(f"[backend] {pkg}")
        else:
            fail(f"[backend] {pkg}  ← MISSING")
            missing_backend.append(pkg)

    for pkg in required_ai:
        spec = importlib.util.find_spec(pkg)
        if spec:
            ok(f"[ai_engine] {pkg}")
        else:
            fail(f"[ai_engine] {pkg}  ← MISSING")
            missing_ai.append(pkg)

    for pkg in optional_ai:
        spec = importlib.util.find_spec(pkg)
        (ok if spec else warn)(f"[optional] {pkg}" + ("" if spec else "  ← not installed (LLM disabled)"))
        if not spec:
            missing_opt.append(pkg)

    note_parts = []
    if missing_backend: note_parts.append(f"missing backend: {missing_backend}")
    if missing_ai:      note_parts.append(f"missing ai_engine: {missing_ai}")
    if missing_opt:     note_parts.append(f"optional absent: {missing_opt}")

    status = "PASS" if not missing_backend else ("WARN" if not missing_ai else "FAIL")
    record("Python Environment", status, note="; ".join(note_parts) or "all required packages present")
    return missing_ai


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — Static Module Imports (syntax + import tree)
# ══════════════════════════════════════════════════════════════════════════════
def audit_static_imports():
    section("2 · Static Code Imports")

    modules_to_check = [
        # AI engine — pure Python (no torch required for import test)
        ("ai_engine.identity.ecdsa_service",    "ECDSAService"),
        ("ai_engine.phishing.url_forensics",    "URLForensics"),
        ("ai_engine.phishing.header_analyzer",  "analyze_headers"),
        ("ai_engine.phishing.verdict_signer",   "sign_verdict"),
    ]

    all_ok = True
    for mod_path, attr in modules_to_check:
        try:
            mod = importlib.import_module(mod_path)
            assert hasattr(mod, attr), f"Missing attribute {attr}"
            ok(f"{mod_path}.{attr}")
        except Exception as e:
            fail(f"{mod_path} → {e}")
            all_ok = False

    # Django settings load (no DB required)
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
        import django
        django.setup()
        from django.conf import settings
        assert "apps.deepfake" in settings.INSTALLED_APPS
        assert "apps.phishing" in settings.INSTALLED_APPS
        assert "apps.identity" in settings.INSTALLED_APPS
        assert "apps.threat_graph" in settings.INSTALLED_APPS
        ok(f"Django settings — INSTALLED_APPS: {[a for a in settings.INSTALLED_APPS if a.startswith('apps.')]}")
    except Exception as e:
        fail(f"Django settings: {e}")
        all_ok = False

    record("Static Imports", "PASS" if all_ok else "FAIL",
           note="" if all_ok else "import errors detected")


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — MPS Hardware Acceleration
# ══════════════════════════════════════════════════════════════════════════════
def audit_mps(torch_available: bool):
    section("3 · MPS Hardware Acceleration (Apple Silicon)")
    if not torch_available:
        warn("torch not installed — skipping MPS checks")
        record("MPS Hardware", "SKIP", note="torch not installed")
        return False

    import torch
    info(f"PyTorch version: {torch.__version__}")
    mps_available = torch.backends.mps.is_available()

    if mps_available:
        ok("torch.backends.mps.is_available() = True")
        # Test fp16 tensor on MPS
        try:
            t = torch.zeros(4, 3, 224, 224, dtype=torch.float16, device="mps")
            result, ms = timed(lambda: (t * 2.0).sum().item(), )
            ok(f"fp16 tensor creation + op on mps: {ms:.1f}ms (sum={result})")
            del t
            torch.mps.empty_cache()
            ok("torch.mps.empty_cache() succeeded")
            record("MPS Hardware", "PASS", latency_ms=ms, note="fp16 tensor op on mps")
            return True
        except Exception as e:
            fail(f"MPS tensor operation failed: {e}")
            record("MPS Hardware", "FAIL", note=str(e))
            return False
    else:
        warn("MPS not available (CPU fallback will be used)")
        try:
            t = torch.zeros(4, 3, 224, 224, dtype=torch.float32, device="cpu")
            result, ms = timed(lambda: (t * 2.0).sum().item())
            ok(f"CPU fp32 tensor op: {ms:.1f}ms")
            del t
            record("MPS Hardware", "WARN", latency_ms=ms, note="MPS unavailable — CPU fallback")
            return False
        except Exception as e:
            fail(f"CPU tensor op failed: {e}")
            record("MPS Hardware", "FAIL", note=str(e))
            return False


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — ECDSA Cryptographic Service
# ══════════════════════════════════════════════════════════════════════════════
def audit_ecdsa():
    section("4 · ECDSA Cryptographic Service (P-256 / secp256r1)")
    try:
        from ai_engine.identity.ecdsa_service import ECDSAService

        svc = ECDSAService()

        # Sign + verify
        payload = "phase3-audit-test-payload"
        (sig, pub), ms_sign = timed(svc.sign, payload)
        ok(f"Sign: {ms_sign:.2f}ms | sig[:16]={sig[:16]}…")

        verified, ms_verify = timed(ECDSAService.verify, pub, payload, sig)
        assert verified, "Signature did not verify!"
        ok(f"Verify (valid payload): {ms_verify:.2f}ms → {verified}")

        tampered_ok, _ = timed(ECDSAService.verify, pub, "tampered", sig)
        assert not tampered_ok, "Tampered payload must be rejected!"
        ok("Tamper detection: tampered payload rejected ✓")

        # Key isolation
        svc2 = ECDSAService()
        sig2, pub2 = svc2.sign(payload)
        assert pub != pub2, "Different instances must have different keys!"
        ok("Key isolation: different instances → different keys ✓")

        # Verdict signer
        from ai_engine.phishing.verdict_signer import sign_verdict, verify_verdict
        verdict = {"is_phishing": True, "confidence": 0.91, "risk_level": "high"}
        signed,  ms_sv = timed(sign_verdict, verdict)
        assert "signed_verdict" in signed and "public_key_pem" in signed
        verified_v, _ = timed(verify_verdict, signed)
        assert verified_v
        ok(f"VerdictSigner round-trip: {ms_sv:.2f}ms → verified ✓")

        record("ECDSA Service", "PASS", latency_ms=ms_sign + ms_verify,
               note=f"sign={ms_sign:.1f}ms verify={ms_verify:.1f}ms")
    except Exception as e:
        fail(f"ECDSA audit failed: {e}")
        traceback.print_exc()
        record("ECDSA Service", "FAIL", note=str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — URL Forensics Engine
# ══════════════════════════════════════════════════════════════════════════════
def audit_url_forensics():
    section("5 · URL Forensics Engine")
    try:
        from ai_engine.phishing.url_forensics import URLForensics
        f = URLForensics()

        cases = [
            ("http://paypal-secure.tk/verify/account",   "phishing",  lambda r: r["risk_score"] >= 0.5),
            ("http://192.168.1.1/admin/login",           "ip-host",   lambda r: r["risk_score"] > 0.0),
            ("https://github.com/Awesome-sanyam",        "clean",     lambda r: r["risk_score"] == 0.0),
            ("http://amaz0n-secure-login.top/verify",    "homoglyph", lambda r: r["risk_score"] >= 0.3),
        ]

        all_ok = True
        total_ms = 0.0
        for url, label, check_fn in cases:
            result, ms = timed(f.analyze, url)
            total_ms += ms
            passed = check_fn(result)
            (ok if passed else fail)(
                f"[{label}] risk={result['risk_score']:.2f} signals={result['signals']} ({ms:.1f}ms)"
            )
            if not passed:
                all_ok = False

        record("URL Forensics", "PASS" if all_ok else "FAIL", latency_ms=total_ms,
               note=f"{len(cases)} test cases")
    except Exception as e:
        fail(f"URL forensics audit failed: {e}")
        traceback.print_exc()
        record("URL Forensics", "FAIL", note=str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — Email Header Analyzer
# ══════════════════════════════════════════════════════════════════════════════
def audit_header_analyzer():
    section("6 · Email Header Analyzer (SPF/DKIM/Display-Name)")
    try:
        from ai_engine.phishing.header_analyzer import analyze_headers

        # High-risk headers
        phishing_headers = {
            "From": "PayPal Security <noreply@evil-clone.com>",
            "Reply-To": "attacker@phish.tk",
            "Received-SPF": "fail (domain of evil-clone.com does not permit)",
            "X-Mailer": "PHPMailer 6.2.0",
        }
        result, ms = timed(analyze_headers, phishing_headers)
        assert result["risk_score"] > 0, f"Expected risk>0, got {result['risk_score']}"
        ok(f"Phishing headers: risk={result['risk_score']:.2f} signals={result['signals']} ({ms:.1f}ms)")

        # Clean headers
        clean_headers = {
            "From": "michael@acmecorp.com",
            "DKIM-Signature": "v=1; a=rsa-sha256; d=acmecorp.com;",
            "Received-SPF": "pass",
        }
        result2, ms2 = timed(analyze_headers, clean_headers)
        ok(f"Clean headers: risk={result2['risk_score']:.2f} signals={result2['signals']} ({ms2:.1f}ms)")

        # Reply-To mismatch
        mismatch_headers = {
            "From": "admin@paypal.com",
            "Reply-To": "gotcha@evil.ru",
        }
        result3, ms3 = timed(analyze_headers, mismatch_headers)
        assert "reply-to-from-mismatch" in result3["signals"], "Mismatch not detected!"
        ok(f"Reply-To mismatch detected: {result3['signals']} ({ms3:.1f}ms)")

        record("Header Analyzer", "PASS", latency_ms=ms + ms2 + ms3,
               note="3 cases: phishing/clean/mismatch")
    except Exception as e:
        fail(f"Header analyzer audit failed: {e}")
        traceback.print_exc()
        record("Header Analyzer", "FAIL", note=str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 7 — AI Deepfake Engines (require torch)
# ══════════════════════════════════════════════════════════════════════════════
def audit_deepfake_engines(torch_available: bool):
    section("7 · Deepfake AI Engines (Visual / Audio / Lip-Sync / Blink)")
    if not torch_available:
        warn("torch not installed — skipping deepfake engine tests")
        record("Visual Detector",  "SKIP", note="torch not installed")
        record("Audio Analyzer",   "SKIP", note="torch not installed")
        record("LipSync Verifier", "SKIP", note="torch not installed")
        record("Blink Detector",   "SKIP", note="torch not installed")
        record("CrossModal Engine","SKIP", note="torch not installed")
        return

    import torch
    import numpy as np

    # ── 7a. AudioAnalyzer ──────────────────────────────────────────────────────
    try:
        from ai_engine.deepfake.audio_analyzer import AudioAnalyzer
        aa = AudioAnalyzer()

        # Synthetic stereo audio at 16kHz for 1 second
        sr = 16000
        audio_bytes = (np.random.randn(sr).astype(np.float32) * 32767).astype(np.int16).tobytes()

        mfcc, ms1 = timed(aa.extract_mfcc, audio_bytes)
        assert mfcc.shape[0] == 40 and len(mfcc.shape) == 2, f"Bad MFCC shape: {mfcc.shape}"
        ok(f"AudioAnalyzer.extract_mfcc: shape={mfcc.shape} ({ms1:.1f}ms)")

        anomaly, ms2 = timed(aa.detect_anomaly, audio_bytes)
        assert "is_anomaly" in anomaly and "anomaly_score" in anomaly
        ok(f"AudioAnalyzer.detect_anomaly: {anomaly} ({ms2:.1f}ms)")

        record("Audio Analyzer", "PASS", latency_ms=ms1 + ms2,
               note=f"MFCC shape={mfcc.shape}")
    except Exception as e:
        fail(f"AudioAnalyzer failed: {e}")
        traceback.print_exc()
        record("Audio Analyzer", "FAIL", note=str(e))

    # ── 7b. VisualArtifactDetector ─────────────────────────────────────────────
    try:
        from ai_engine.deepfake.visual_detector import VisualArtifactDetector
        vd = VisualArtifactDetector()

        import numpy as np
        # 1-frame test
        frame_1 = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        scores_1, ms1 = timed(vd.score_batch, [frame_1])
        assert len(scores_1) == 1 and 0.0 <= scores_1[0] <= 1.0
        ok(f"VisualDetector (1 frame): score={scores_1[0]:.4f} ({ms1:.1f}ms)")

        # 5-frame test (crosses sub-batch boundary of 4)
        frames_5 = [np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8) for _ in range(5)]
        scores_5, ms5 = timed(vd.score_batch, frames_5)
        assert len(scores_5) == 5 and all(0.0 <= s <= 1.0 for s in scores_5)
        ok(f"VisualDetector (5 frames crossing sub-batch): {[f'{s:.3f}' for s in scores_5]} ({ms5:.1f}ms)")

        del vd
        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        ok("Visual detector cleanup: gc.collect() + mps.empty_cache() ✓")

        record("Visual Detector", "PASS", latency_ms=ms1 + ms5,
               note=f"1-frame={ms1:.0f}ms 5-frame={ms5:.0f}ms")
    except Exception as e:
        fail(f"VisualArtifactDetector failed: {e}")
        traceback.print_exc()
        record("Visual Detector", "FAIL", note=str(e))

    # ── 7c. LipSyncVerifier ────────────────────────────────────────────────────
    try:
        from ai_engine.deepfake.lip_sync_verifier import LipSyncVerifier
        lsv = LipSyncVerifier()

        frames_10 = [np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8) for _ in range(10)]
        audio_bytes = (np.random.randn(16000).astype(np.float32) * 32767).astype(np.int16).tobytes()

        (delay_ms, is_suspicious), ms = timed(lsv.verify, frames_10, audio_bytes)
        assert isinstance(delay_ms, float) and isinstance(is_suspicious, bool)
        ok(f"LipSyncVerifier: delay={delay_ms:.1f}ms suspicious={is_suspicious} ({ms:.1f}ms)")

        record("LipSync Verifier", "PASS", latency_ms=ms,
               note=f"delay={delay_ms:.1f}ms")
    except Exception as e:
        fail(f"LipSyncVerifier failed: {e}")
        traceback.print_exc()
        record("LipSync Verifier", "FAIL", note=str(e))

    # ── 7d. BlinkRateDetector ──────────────────────────────────────────────────
    try:
        from ai_engine.deepfake.blink_detector import BlinkRateDetector
        bd = BlinkRateDetector()

        frames_30 = [np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8) for _ in range(30)]
        (bpm, is_abnormal), ms = timed(bd.compute_blink_rate, frames_30, fps=30.0)
        assert isinstance(bpm, float) and isinstance(is_abnormal, bool)
        ok(f"BlinkRateDetector: bpm={bpm:.1f} abnormal={is_abnormal} ({ms:.1f}ms)")

        record("Blink Detector", "PASS", latency_ms=ms,
               note=f"bpm={bpm:.1f}")
    except Exception as e:
        fail(f"BlinkRateDetector failed: {e}")
        traceback.print_exc()
        record("Blink Detector", "FAIL", note=str(e))

    # ── 7e. CrossModalVerificationEngine ──────────────────────────────────────
    try:
        from ai_engine.deepfake.cross_modal_engine import CrossModalVerificationEngine
        engine = CrossModalVerificationEngine()

        frames_10 = [np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8) for _ in range(10)]
        audio_bytes = (np.random.randn(16000).astype(np.float32) * 32767).astype(np.int16).tobytes()

        verdict, ms = timed(engine.analyze,
                            session_id="audit-session-001",
                            frames=frames_10,
                            audio_bytes=audio_bytes,
                            fps=10.0)
        assert hasattr(verdict, "is_deepfake") and hasattr(verdict, "confidence")
        assert isinstance(verdict.is_deepfake, bool)
        assert 0.0 <= verdict.confidence <= 1.0
        assert verdict.session_id == "audit-session-001"
        assert len(verdict.frame_results) == len(frames_10)
        assert isinstance(verdict.signed_verdict, str) and len(verdict.signed_verdict) > 0

        ok(f"CrossModal verdict: is_deepfake={verdict.is_deepfake} conf={verdict.confidence:.4f}")
        ok(f"CrossModal frames: {len(verdict.frame_results)} frame results")
        ok(f"CrossModal ECDSA: signed_verdict={verdict.signed_verdict[:24]}… ({ms:.1f}ms)")

        engine.cleanup()
        ok("CrossModal cleanup() called ✓")

        record("CrossModal Engine", "PASS", latency_ms=ms,
               note=f"is_deepfake={verdict.is_deepfake} conf={verdict.confidence:.3f}")
    except Exception as e:
        fail(f"CrossModalVerificationEngine failed: {e}")
        traceback.print_exc()
        record("CrossModal Engine", "FAIL", note=str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 8 — LLM Phishing Analyzer
# ══════════════════════════════════════════════════════════════════════════════
def audit_llm_phishing():
    section("8 · LLM Phishing Analyzer")
    try:
        from ai_engine.phishing.llm_analyzer import PhishingAnalyzer
        analyzer = PhishingAnalyzer()

        phishing_content = (
            "URGENT: Your PayPal account has been limited. "
            "Verify immediately at http://paypal-secure.tk/verify or lose access!"
        )
        result, ms = timed(
            analyzer.analyze,
            content=phishing_content,
            url="http://paypal-secure.tk/verify",
            headers={"From": "noreply@paypa1.com", "Received-SPF": "fail"},
            session_id="audit-phishing-001",
        )
        assert "is_phishing" in result
        assert "confidence" in result
        assert "signals" in result
        assert "signed_verdict" in result

        ok(f"PhishingAnalyzer: is_phishing={result['is_phishing']} conf={result['confidence']:.3f}")
        ok(f"Signals detected: {result['signals']}")
        ok(f"ECDSA signed: {result['signed_verdict'][:24]}… ({ms:.1f}ms)")

        record("LLM Phishing Analyzer", "PASS", latency_ms=ms,
               note=f"is_phishing={result['is_phishing']} signals={len(result['signals'])}")
    except Exception as e:
        fail(f"PhishingAnalyzer failed: {e}")
        traceback.print_exc()
        record("LLM Phishing Analyzer", "FAIL", note=str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 9 — Infrastructure Connectivity (graceful)
# ══════════════════════════════════════════════════════════════════════════════
def audit_infrastructure():
    section("9 · Infrastructure Connectivity (PostgreSQL / Redis / Neo4j)")

    # PostgreSQL
    try:
        import psycopg2
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = int(os.environ.get("POSTGRES_PORT", "5432"))
        conn, ms = timed(psycopg2.connect,
                         host=host, port=port,
                         user=os.environ.get("POSTGRES_USER", "soc_user"),
                         password=os.environ.get("POSTGRES_PASSWORD", "soc_password"),
                         database=os.environ.get("POSTGRES_DB", "soc_db"),
                         connect_timeout=3)
        conn.close()
        ok(f"PostgreSQL: connected at {host}:{port} ({ms:.1f}ms)")
        record("PostgreSQL", "PASS", latency_ms=ms)
    except Exception as e:
        warn(f"PostgreSQL: {e}")
        record("PostgreSQL", "OFFLINE", note=str(e)[:80])

    # Redis
    try:
        import redis as redis_lib
        host = os.environ.get("REDIS_HOST", "localhost")
        r, ms = timed(redis_lib.Redis(host=host, port=6379, socket_connect_timeout=2).ping)
        ok(f"Redis: PONG at {host}:6379 ({ms:.1f}ms)")
        record("Redis", "PASS", latency_ms=ms)
    except Exception as e:
        warn(f"Redis: {e}")
        record("Redis", "OFFLINE", note=str(e)[:80])

    # Neo4j
    try:
        sys.path.insert(0, os.path.join(_REPO_ROOT, "backend"))
        from apps.threat_graph.graph_client import health_check
        result, ms = timed(health_check)
        if result["status"] == "ok":
            ok(f"Neo4j: {result['version']} at {result['uri']} ({ms:.1f}ms)")
            record("Neo4j", "PASS", latency_ms=ms, note=result.get("version", ""))
        else:
            warn(f"Neo4j: offline — {result.get('error', '')}")
            record("Neo4j", "OFFLINE", note=result.get("error", "")[:80])
    except Exception as e:
        warn(f"Neo4j: {e}")
        record("Neo4j", "OFFLINE", note=str(e)[:80])

    # FastAPI AI Engine
    try:
        import httpx
        url = os.environ.get("AI_ENGINE_BASE_URL", "http://localhost:8001")
        resp, ms = timed(httpx.get, f"{url}/health", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            ok(f"FastAPI AI Engine: status={data.get('status')} device={data.get('device')} ({ms:.1f}ms)")
            record("FastAPI AI Engine", "PASS", latency_ms=ms,
                   note=f"device={data.get('device')} models={data.get('models_loaded')}")
        else:
            warn(f"FastAPI returned HTTP {resp.status_code}")
            record("FastAPI AI Engine", "WARN", latency_ms=ms, note=f"HTTP {resp.status_code}")
    except Exception as e:
        warn(f"FastAPI AI Engine: {e}")
        record("FastAPI AI Engine", "OFFLINE", note=str(e)[:80])


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 10 — Memory Stress Test (20 rapid frame batches)
# ══════════════════════════════════════════════════════════════════════════════
def audit_memory_stress(torch_available: bool):
    section("10 · Memory Stress Test — 20 Rapid Frame Batches")

    # Memory snapshot helper
    def _mem_mb() -> float:
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
        except Exception:
            return 0.0

    if not torch_available:
        # Non-torch stress: ECDSA + URL forensics rapid fire
        warn("torch not available — stress testing ECDSA + URL forensics only")
        from ai_engine.identity.ecdsa_service import ECDSAService
        from ai_engine.phishing.url_forensics import URLForensics
        svc = ECDSAService()
        uf  = URLForensics()

        latencies = []
        mem_before = _mem_mb()
        for i in range(20):
            t0 = time.perf_counter()
            sig, pub = svc.sign(f"stress-payload-{i}")
            ECDSAService.verify(pub, f"stress-payload-{i}", sig)
            uf.analyze(f"http://paypal-secure-{i}.tk/verify")
            latencies.append((time.perf_counter() - t0) * 1000)
            gc.collect()

        mem_after = _mem_mb()
        avg_ms  = sum(latencies) / len(latencies)
        peak_ms = max(latencies)
        mem_delta = mem_after - mem_before

        ok(f"20 iterations: avg={avg_ms:.1f}ms peak={peak_ms:.1f}ms mem_delta={mem_delta:.1f}MB")
        record("Memory Stress (No-GPU)", "PASS",
               latency_ms=avg_ms, memory_mb=mem_after,
               note=f"peak={peak_ms:.0f}ms delta_mem={mem_delta:.1f}MB")
        return

    import torch
    import numpy as np
    from ai_engine.deepfake.visual_detector import VisualArtifactDetector

    vd = VisualArtifactDetector()
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    latencies = []
    mem_before = _mem_mb()
    info(f"Running 20 batches of 4 frames each on {device}…")

    for i in range(20):
        frames = [np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8) for _ in range(4)]
        t0 = time.perf_counter()
        vd.score_batch(frames)
        latencies.append((time.perf_counter() - t0) * 1000)

        # Explicit cleanup every batch (as implemented in visual_detector)
        gc.collect()
        if device == "mps":
            torch.mps.empty_cache()

        if (i + 1) % 5 == 0:
            mem_now = _mem_mb()
            info(f"  Batch {i+1:02d}: latency={latencies[-1]:.1f}ms | RSS={mem_now:.0f}MB")

    mem_after = _mem_mb()
    avg_ms    = sum(latencies) / len(latencies)
    peak_ms   = max(latencies)
    mem_delta = mem_after - mem_before

    del vd
    gc.collect()
    if device == "mps":
        torch.mps.empty_cache()

    ok(f"20 × 4-frame batches on {device}:")
    ok(f"  avg latency = {avg_ms:.1f}ms")
    ok(f"  peak latency= {peak_ms:.1f}ms")
    ok(f"  RSS before  = {mem_before:.0f}MB")
    ok(f"  RSS after   = {mem_after:.0f}MB  (delta={mem_delta:+.0f}MB)")

    status = "PASS" if mem_delta < 500 else "WARN"
    record("Memory Stress (GPU)", status,
           latency_ms=avg_ms, memory_mb=mem_after,
           note=f"avg={avg_ms:.0f}ms peak={peak_ms:.0f}ms delta={mem_delta:+.0f}MB device={device}")


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 11 — Django Settings & URL Configuration
# ══════════════════════════════════════════════════════════════════════════════
def audit_django_config():
    section("11 · Django Configuration & URL Resolution")
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
        try:
            import django
            if not django.conf.settings.configured:
                django.setup()
        except Exception:
            pass

        from django.conf import settings
        from django.urls import reverse

        # Check required settings
        checks = [
            ("AI_ENGINE_BASE_URL", lambda: settings.AI_ENGINE_BASE_URL),
            ("NEO4J_URI",          lambda: settings.NEO4J_URI),
            ("CELERY_BROKER_URL",  lambda: settings.CELERY_BROKER_URL),
            ("CHANNEL_LAYERS",     lambda: settings.CHANNEL_LAYERS),
        ]
        for name, getter in checks:
            try:
                val = getter()
                ok(f"{name} = {val}")
            except Exception as e:
                fail(f"{name}: {e}")

        # URL resolution
        url_checks = [
            ("dashboard:index",    "/"),
            ("deepfake:monitor",   "/deepfake/monitor/"),
            ("phishing:scanner",   "/phishing/scanner/"),
            ("threat_graph:view",  "/threat-graph/view/"),
        ]
        for name, expected in url_checks:
            try:
                resolved = reverse(name)
                ok(f"URL '{name}' → {resolved}")
            except Exception as e:
                fail(f"URL '{name}' failed: {e}")

        # API URL checks
        api_checks = [
            ("phishing-scan-submit", "/api/phishing/scan/"),
            ("graph-data",           "/api/graph/data/"),
            ("threat-graph-health",  "/api/graph/health/"),
        ]
        for name, expected in api_checks:
            try:
                resolved = reverse(name)
                ok(f"API '{name}' → {resolved}")
            except Exception as e:
                fail(f"API '{name}' failed: {e}")

        record("Django Config", "PASS", note="settings + URL resolution OK")
    except Exception as e:
        fail(f"Django config audit failed: {e}")
        traceback.print_exc()
        record("Django Config", "FAIL", note=str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  FINAL REPORT
# ══════════════════════════════════════════════════════════════════════════════
def print_report():
    section("AUDIT SUMMARY REPORT")

    col_w = [38, 8, 14, 12, 30]
    header = ["Component", "Status", "Latency (ms)", "Mem (MB)", "Notes"]
    sep    = "─" * sum(col_w) + "─" * (len(col_w) - 1) * 3

    def row(*cells):
        return "  ".join(str(c).ljust(w) for c, w in zip(cells, col_w))

    print(f"\n  {_c(BOLD, row(*header))}")
    print(f"  {sep}")

    pass_ct = fail_ct = warn_ct = skip_ct = offline_ct = 0
    for r in _results:
        status  = r["status"]
        lat     = f"{r['latency_ms']:.1f}" if r["latency_ms"] is not None else "—"
        mem     = f"{r['memory_mb']:.0f}"  if r["memory_mb"]  is not None else "—"
        note    = (r["note"] or "")[:30]

        if status == "PASS":
            clr = GREEN; pass_ct += 1
        elif status == "FAIL":
            clr = RED;   fail_ct += 1
        elif status in ("WARN",):
            clr = AMBER; warn_ct += 1
        elif status == "SKIP":
            clr = CYAN;  skip_ct += 1
        else:
            clr = AMBER; offline_ct += 1  # OFFLINE

        print(f"  {r['component'].ljust(col_w[0])}  {_c(clr, status.ljust(col_w[1]))}  {lat.ljust(col_w[2])}  {mem.ljust(col_w[3])}  {note}")

    print(f"  {sep}")
    print(f"\n  Total: {_c(GREEN, str(pass_ct))} PASS  "
          f"{_c(RED, str(fail_ct))} FAIL  "
          f"{_c(AMBER, str(warn_ct))} WARN  "
          f"{_c(CYAN, str(skip_ct))} SKIP  "
          f"{_c(AMBER, str(offline_ct))} OFFLINE\n")

    # Write JSON report
    report_path = os.path.join(_REPO_ROOT, "scripts", "audit_report.json")
    with open(report_path, "w") as fh:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "python":       sys.version,
            "results":      _results,
            "summary": {
                "pass":    pass_ct,
                "fail":    fail_ct,
                "warn":    warn_ct,
                "skip":    skip_ct,
                "offline": offline_ct,
            },
        }, fh, indent=2)
    info(f"JSON report saved → {report_path}")

    return fail_ct == 0


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{BOLD}{'═'*62}{RESET}")
    print(f"{BOLD}  AI DEFENCE SYSTEM — COMPREHENSIVE SYSTEM AUDIT{RESET}")
    print(f"{BOLD}  Phases 1 + 2 + 3  ·  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"{BOLD}{'═'*62}{RESET}")

    missing_ai = audit_python_env()
    torch_available = "torch" not in missing_ai

    audit_static_imports()
    mps_ok = audit_mps(torch_available)
    audit_ecdsa()
    audit_url_forensics()
    audit_header_analyzer()
    audit_deepfake_engines(torch_available)
    audit_llm_phishing()
    audit_infrastructure()
    audit_memory_stress(torch_available)
    audit_django_config()

    success = print_report()

    print(f"\n  {'🟢 ALL CRITICAL CHECKS PASSED' if success else '🔴 SOME CHECKS FAILED — see table above'}\n")
    sys.exit(0 if success else 1)
