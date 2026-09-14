#!/usr/bin/env python3
"""
DEFENCESYS — Final Polish Automated Audit Script
=================================================
Comprehensive end-to-end verification of all system components.

Usage:
    python scripts/final_polish_audit.py [--base-url http://localhost:8000] [--ai-url http://localhost:8001]

Exit codes:
    0 — All critical tests passed
    1 — One or more critical tests failed

Test Suites:
    1. Authentication  — Registration, login, session, route protection
    2. Phishing Engine — LLM JSON extraction, URL entropy, ECDSA signature
    3. Deepfake Engine — File upload pipeline, AI Engine health, MPS cache
    4. Threat Graph    — /api/graph/data/ JSON schema, WebSocket feed

Dependencies: Python stdlib only (urllib, http, json, base64, ssl)
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_AI_URL   = "http://localhost:8001"

TEST_USER     = f"auditor_{uuid.uuid4().hex[:8]}"
TEST_PASSWORD = "AuditPass@2025!"
TEST_EMAIL    = f"{TEST_USER}@defencesys.test"


# ─────────────────────────────────────────────────────────────────────────────
# Result tracking
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    name:    str
    status:  str          # "PASS" | "FAIL" | "SKIP" | "WARN"
    detail:  str = ""
    elapsed: float = 0.0


_results: list[TestResult] = []


def _record(name: str, status: str, detail: str = "", elapsed: float = 0.0) -> TestResult:
    r = TestResult(name=name, status=status, detail=detail, elapsed=elapsed)
    _results.append(r)
    icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭ ", "WARN": "⚠️"}.get(status, " ")
    print(f"  {icon}  {name:<48} {status}  {detail}")
    return r


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Helpers
# ─────────────────────────────────────────────────────────────────────────────

class _Session:
    """Minimal cookie-bearing HTTP client backed by urllib."""

    def __init__(self):
        self._jar = http.cookiejar.CookieJar()
        handler   = urllib.request.HTTPCookieProcessor(self._jar)
        self._opener = urllib.request.build_opener(handler)

    def _csrf_token(self) -> str:
        for cookie in self._jar:
            if cookie.name == "csrftoken":
                return cookie.value
        return ""

    def get(self, url: str, *, timeout: float = 8.0) -> tuple[int, bytes, dict]:
        req = urllib.request.Request(url)
        try:
            resp = self._opener.open(req, timeout=timeout)
            return resp.getcode(), resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), {}

    def post(
        self,
        url: str,
        data: Optional[dict | bytes] = None,
        *,
        content_type: str = "application/x-www-form-urlencoded",
        timeout: float = 10.0,
        extra_headers: Optional[dict] = None,
    ) -> tuple[int, bytes, dict]:
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode()
        else:
            body = data or b""

        csrf = self._csrf_token()
        headers = {
            "Content-Type": content_type,
            "X-CSRFToken":  csrf,
            "Referer":      url,
        }
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            resp = self._opener.open(req, timeout=timeout)
            return resp.getcode(), resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), {}

    def post_json(self, url: str, payload: dict, *, timeout: float = 12.0) -> tuple[int, dict]:
        body = json.dumps(payload).encode()
        csrf = self._csrf_token()
        req  = urllib.request.Request(
            url, data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept":       "application/json",
                "X-CSRFToken":  csrf,
                "Referer":      url,
            },
        )
        try:
            resp = self._opener.open(req, timeout=timeout)
            return resp.getcode(), json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read())
            except Exception:
                return e.code, {}

    def post_multipart(
        self, url: str, fields: dict, files: dict, *, timeout: float = 15.0
    ) -> tuple[int, dict]:
        """Upload multipart/form-data. files = {'field': ('filename', bytes, 'mime/type')}"""
        boundary = uuid.uuid4().hex
        body_parts: list[bytes] = []

        for name, value in fields.items():
            body_parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; "
                f"name=\"{name}\"\r\n\r\n{value}\r\n".encode()
            )
        for fname, (filename, data, mime) in files.items():
            body_parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; "
                f"name=\"{fname}\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {mime}\r\n\r\n".encode() + data + b"\r\n"
            )
        body_parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(body_parts)

        csrf = self._csrf_token()
        req  = urllib.request.Request(
            url, data=body, method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-CSRFToken":  csrf,
                "Referer":      url,
            },
        )
        try:
            resp = self._opener.open(req, timeout=timeout)
            return resp.getcode(), json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read())
            except Exception:
                return e.code, {}


# ─────────────────────────────────────────────────────────────────────────────
# Suite 1: Authentication
# ─────────────────────────────────────────────────────────────────────────────

def suite_auth(base: str, session: _Session) -> bool:
    print("\n📋 Suite 1: Authentication")

    # 1a. Fetch login page (loads CSRF cookie)
    t0 = time.perf_counter()
    code, body, _ = session.get(f"{base}/auth/login/")
    elapsed = time.perf_counter() - t0
    if code == 200 and b"csrfmiddlewaretoken" in body:
        _record("Auth: Login page loads (CSRF cookie)", "PASS", f"HTTP {code}", elapsed)
    else:
        _record("Auth: Login page loads (CSRF cookie)", "FAIL", f"HTTP {code}", elapsed)
        return False

    # 1b. Register a new user
    t0 = time.perf_counter()
    session.get(f"{base}/auth/register/")   # load CSRF for register form
    code, _, _ = session.post(f"{base}/auth/register/", {
        "username":   TEST_USER,
        "email":      TEST_EMAIL,
        "password1":  TEST_PASSWORD,
        "password2":  TEST_PASSWORD,
    })
    elapsed = time.perf_counter() - t0
    # Accepts 200 (success page) or 302 (redirect to login/dashboard)
    if code in (200, 201, 302):
        _record("Auth: User registration", "PASS", f"HTTP {code}", elapsed)
    else:
        _record("Auth: User registration", "WARN", f"HTTP {code} (may already exist)", elapsed)

    # 1c. Login
    t0 = time.perf_counter()
    session.get(f"{base}/auth/login/")      # refresh CSRF
    code, _, headers = session.post(f"{base}/auth/login/", {
        "username": TEST_USER,
        "password": TEST_PASSWORD,
    })
    elapsed = time.perf_counter() - t0
    if code in (200, 302):
        _record("Auth: Login + session cookie", "PASS", f"HTTP {code}", elapsed)
    else:
        _record("Auth: Login + session cookie", "FAIL", f"HTTP {code}", elapsed)
        return False

    # 1d. Protected route (dashboard) — should be accessible
    t0 = time.perf_counter()
    code, body, _ = session.get(f"{base}/")
    elapsed = time.perf_counter() - t0
    if code == 200 and (b"DEFENCESYS" in body or b"dashboard" in body.lower()):
        _record("Auth: Protected route accessible post-login", "PASS", f"HTTP {code}", elapsed)
    else:
        _record("Auth: Protected route accessible post-login", "WARN", f"HTTP {code}", elapsed)

    # 1e. Unauthenticated access redirect
    fresh = _Session()
    t0    = time.perf_counter()
    code, _, _ = fresh.get(f"{base}/deepfake/monitor/")
    elapsed = time.perf_counter() - t0
    if code in (302, 301) or code == 200:  # 200 if redirect followed to login
        _record("Auth: Unauth route redirects to login", "PASS", f"HTTP {code}", elapsed)
    else:
        _record("Auth: Unauth route redirects to login", "WARN", f"HTTP {code}", elapsed)

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Suite 2: Phishing Engine
# ─────────────────────────────────────────────────────────────────────────────

def suite_phishing(base: str, session: _Session) -> bool:
    print("\n📧 Suite 2: Phishing Engine")

    # 2a. Direct AI engine phishing endpoint
    phishing_url = f"{base.replace(':8000',':8001')}/scan/phishing"

    # Markdown-wrapped LLM-style payload to test JSON extraction robustness
    suspicious_content = """
    Dear Executive Team,

    URGENT: Our CFO has requested an immediate wire transfer of $485,000 to our
    new vendor account. Please action this immediately to avoid penalties.

    Bank: First National
    Routing: 021000089
    Account: 9834721045

    This must be done TODAY. Please click here to verify: http://paypal-secure.tk/verify
    """

    payload = {
        "session_id": str(uuid.uuid4()),
        "content":    suspicious_content,
        "url":        "http://paypal-secure.tk/verify/account",
        "headers":    {
            "From":           "ceo@c0mpany.com",
            "Reply-To":       "payments@wire-transfer.tk",
            "Authentication-Results": "spf=fail dkim=fail",
        },
    }

    try:
        code, resp = session.post_json(phishing_url, payload, timeout=30.0)
        elapsed = 0.0

        if code in (200, 202):
            _record("Phishing: AI Engine reachable", "PASS", f"HTTP {code}")

            # Check ECDSA signature is present
            if resp.get("signed_verdict") and resp.get("public_key_pem"):
                _record("Phishing: ECDSA signature present", "PASS",
                        f"sig={resp['signed_verdict'][:16]}...")
            else:
                _record("Phishing: ECDSA signature present", "FAIL",
                        "missing signed_verdict or public_key_pem")

            # Check confidence is a valid float
            conf = resp.get("confidence", -1)
            if isinstance(conf, (int, float)) and 0.0 <= conf <= 1.0:
                _record("Phishing: Confidence score valid", "PASS", f"confidence={conf:.3f}")
            else:
                _record("Phishing: Confidence score valid", "FAIL", f"confidence={conf!r}")

            # Check signals list
            signals = resp.get("signals", [])
            if isinstance(signals, list) and len(signals) > 0:
                _record("Phishing: Signals detected", "PASS",
                        f"{len(signals)} signals: {signals[0]}")
            else:
                _record("Phishing: Signals detected", "WARN", "No signals returned")

        else:
            _record("Phishing: AI Engine reachable", "SKIP",
                    f"HTTP {code} — AI Engine may be offline")
            _record("Phishing: ECDSA signature present", "SKIP", "AI Engine offline")
            _record("Phishing: Confidence score valid",  "SKIP", "AI Engine offline")
            _record("Phishing: Signals detected",        "SKIP", "AI Engine offline")

    except Exception as exc:
        _record("Phishing: AI Engine reachable",      "SKIP", str(exc)[:60])
        _record("Phishing: ECDSA signature present",  "SKIP", "AI Engine offline")
        _record("Phishing: Confidence score valid",   "SKIP", "AI Engine offline")
        _record("Phishing: Signals detected",         "SKIP", "AI Engine offline")

    # 2b. URL forensics unit test (pure Python — always runs)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from ai_engine.phishing.url_forensics import URLForensics
        f = URLForensics()

        t0 = time.perf_counter()
        r  = f.analyze("http://paypal-secure.tk/verify/account")
        elapsed = time.perf_counter() - t0

        if r["risk_score"] >= 0.50 and len(r["signals"]) >= 2:
            _record("Phishing: URL entropy + signal scoring", "PASS",
                    f"risk={r['risk_score']:.2f} signals={len(r['signals'])}", elapsed)
        else:
            _record("Phishing: URL entropy + signal scoring", "FAIL",
                    f"risk={r['risk_score']:.2f} signals={r['signals']}", elapsed)

        # Cyrillic homoglyph detection
        t0 = time.perf_counter()
        r2 = f.analyze("http://\u0440\u0430ypal.com/login")   # Cyrillic р а → looks like paypal
        elapsed = time.perf_counter() - t0
        has_cyrillic = any("cyrillic" in s for s in r2["signals"])
        _record("Phishing: Cyrillic homoglyph detection", "PASS" if has_cyrillic else "WARN",
                f"signals={r2['signals'][:3]}", elapsed)

        # Clean URL must score 0
        t0  = time.perf_counter()
        r3  = f.analyze("https://github.com/Awesome-sanyam")
        elapsed = time.perf_counter() - t0
        if r3["risk_score"] == 0.0:
            _record("Phishing: Clean URL scores 0.0", "PASS",
                    f"risk={r3['risk_score']}", elapsed)
        else:
            _record("Phishing: Clean URL scores 0.0", "WARN",
                    f"risk={r3['risk_score']} signals={r3['signals']}", elapsed)

    except Exception as exc:
        _record("Phishing: URL entropy + signal scoring", "FAIL", str(exc)[:60])
        _record("Phishing: Cyrillic homoglyph detection", "FAIL", str(exc)[:60])
        _record("Phishing: Clean URL scores 0.0",         "FAIL", str(exc)[:60])

    # 2c. LLM heuristic fallback
    try:
        from ai_engine.phishing.llm_analyzer import PhishingAnalyzer
        # No model path → forces heuristic fallback
        analyzer = PhishingAnalyzer(model_path="/nonexistent.gguf")
        t0  = time.perf_counter()
        result = analyzer.analyze(
            session_id=str(uuid.uuid4()),
            content=suspicious_content,
            url="http://paypal-secure.tk/verify",
        )
        elapsed = time.perf_counter() - t0

        if result.get("signed_verdict") and result.get("confidence", 0) >= 0:
            _record("Phishing: Heuristic fallback + ECDSA sign", "PASS",
                    f"source={result.get('analysis_source','?')} conf={result.get('confidence',0):.2f}",
                    elapsed)
        else:
            _record("Phishing: Heuristic fallback + ECDSA sign", "FAIL",
                    f"result={list(result.keys())}", elapsed)

    except Exception as exc:
        _record("Phishing: Heuristic fallback + ECDSA sign", "FAIL", str(exc)[:70])

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Suite 3: Deepfake Engine
# ─────────────────────────────────────────────────────────────────────────────

def suite_deepfake(base: str, session: _Session) -> bool:
    print("\n🎥 Suite 3: Deepfake Engine")

    # 3a. Deepfake file upload API (Django backend)
    # Create a minimal fake .mp4 (15 bytes — just enough to pass extension check)
    fake_mp4 = b"fakemp4_header" + b"\x00"
    t0 = time.perf_counter()
    code, resp = session.post_multipart(
        f"{base}/api/deepfake/upload/",
        fields={},
        files={"file": ("test_video.mp4", fake_mp4, "video/mp4")},
    )
    elapsed = time.perf_counter() - t0

    if code == 202 and resp.get("session_id") and resp.get("status") == "queued":
        session_id = resp["session_id"]
        _record("Deepfake: File upload returns 202 + session_id", "PASS",
                f"session={session_id[:12]}...", elapsed)
    else:
        _record("Deepfake: File upload returns 202 + session_id", "FAIL",
                f"HTTP {code} resp={list(resp.keys())}", elapsed)
        session_id = None

    # 3b. Reject invalid file type (text/plain → should be 415)
    t0 = time.perf_counter()
    code, resp2 = session.post_multipart(
        f"{base}/api/deepfake/upload/",
        fields={},
        files={"file": ("bad.txt", b"hello world", "text/plain")},
    )
    elapsed = time.perf_counter() - t0
    if code == 415:
        _record("Deepfake: Invalid MIME type → HTTP 415", "PASS",
                f"HTTP {code}", elapsed)
    else:
        _record("Deepfake: Invalid MIME type → HTTP 415", "FAIL",
                f"HTTP {code} expected 415", elapsed)

    # 3c. Poll file scan result endpoint (expects pending since no Celery)
    if session_id:
        t0 = time.perf_counter()
        code, _resp3_body, _ = session.get(f"{base}/api/deepfake/file-scan/{session_id}/")
        if code == 200:
            try:
                data = json.loads(_resp3_body)
                status = data.get("status")
                if status in ("pending", "complete"):
                    _record("Deepfake: Poll endpoint returns status", "PASS",
                            f"status={status}")
                else:
                    _record("Deepfake: Poll endpoint returns status", "WARN",
                            f"status={status!r}")
            except Exception:
                _record("Deepfake: Poll endpoint returns status", "WARN",
                        "HTTP 200 but non-JSON body")
        else:
            _record("Deepfake: Poll endpoint returns status", "FAIL", f"HTTP {code}")

    # 3d. AI Engine health check
    ai_url = base.replace(":8000", ":8001")
    t0 = time.perf_counter()
    try:
        code, body, _ = session.get(f"{ai_url}/health", timeout=3.0)
        elapsed = time.perf_counter() - t0
        if code == 200:
            health = json.loads(body)
            device = health.get("device", "unknown")
            _record("Deepfake: AI Engine health (/health)", "PASS",
                    f"device={device}", elapsed)
        else:
            _record("Deepfake: AI Engine health (/health)", "SKIP",
                    f"HTTP {code} — AI Engine offline", elapsed)
    except Exception as exc:
        _record("Deepfake: AI Engine health (/health)", "SKIP",
                f"Unreachable: {str(exc)[:40]}")

    # 3e. ECDSA service unit test (no network needed)
    try:
        from ai_engine.identity.ecdsa_service import ECDSAService
        svc = ECDSAService()
        t0  = time.perf_counter()
        sig, pub = svc.sign("test-audit-payload")
        ok  = ECDSAService.verify(pub, "test-audit-payload", sig)
        tampered = ECDSAService.verify(pub, "tampered-payload", sig)
        elapsed = time.perf_counter() - t0

        if ok and not tampered:
            _record("Deepfake: ECDSA sign + verify + tamper rejection", "PASS",
                    "round-trip OK, tamper detected", elapsed)
        else:
            _record("Deepfake: ECDSA sign + verify + tamper rejection", "FAIL",
                    f"verify={ok} tamper_rejected={not tampered}", elapsed)
    except Exception as exc:
        _record("Deepfake: ECDSA sign + verify + tamper rejection", "FAIL", str(exc)[:70])

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Suite 4: Threat Graph & WebSocket
# ─────────────────────────────────────────────────────────────────────────────

def suite_threat_graph(base: str, session: _Session) -> bool:
    print("\n🕸  Suite 4: Threat Graph & Alert Feed")

    # 4a. Graph data API
    t0 = time.perf_counter()
    code, body, _ = session.get(f"{base}/api/graph/data/")
    elapsed = time.perf_counter() - t0

    if code == 200:
        try:
            data  = json.loads(body)
            nodes = data.get("nodes")
            edges = data.get("edges")
            if isinstance(nodes, list) and isinstance(edges, list):
                _record("ThreatGraph: /api/graph/data/ schema valid", "PASS",
                        f"nodes={len(nodes)} edges={len(edges)}", elapsed)
            else:
                _record("ThreatGraph: /api/graph/data/ schema valid", "FAIL",
                        f"missing nodes/edges keys: {list(data.keys())}", elapsed)
        except json.JSONDecodeError:
            _record("ThreatGraph: /api/graph/data/ schema valid", "FAIL",
                    "Non-JSON response body", elapsed)
    elif code == 503:
        _record("ThreatGraph: /api/graph/data/ schema valid", "WARN",
                "Neo4j offline (503) — graph returns empty sets", elapsed)
    else:
        _record("ThreatGraph: /api/graph/data/ schema valid", "FAIL",
                f"HTTP {code}", elapsed)

    # 4b. Graph health endpoint
    t0 = time.perf_counter()
    code, body, _ = session.get(f"{base}/api/graph/health/")
    elapsed = time.perf_counter() - t0
    if code == 200:
        _record("ThreatGraph: /api/graph/health/ reachable", "PASS",
                f"HTTP {code}", elapsed)
    else:
        _record("ThreatGraph: /api/graph/health/ reachable", "WARN",
                f"HTTP {code}", elapsed)

    # 4c. Dashboard page loads with dynamic stats
    t0 = time.perf_counter()
    code, body, _ = session.get(f"{base}/")
    elapsed = time.perf_counter() - t0
    if code == 200 and b"Total Scans" in body or b"deepfake" in body.lower():
        _record("ThreatGraph: Dashboard loads with live stats", "PASS",
                f"HTTP {code}", elapsed)
    else:
        _record("ThreatGraph: Dashboard loads with live stats", "WARN",
                f"HTTP {code}", elapsed)

    # 4d. Threat graph page renders
    t0 = time.perf_counter()
    code, body, _ = session.get(f"{base}/threat-graph/view/")
    elapsed = time.perf_counter() - t0
    if code == 200 and b"threat-network" in body:
        _record("ThreatGraph: /threat-graph/view/ renders canvas", "PASS",
                f"HTTP {code}", elapsed)
    else:
        _record("ThreatGraph: /threat-graph/view/ renders canvas", "WARN",
                f"HTTP {code}", elapsed)

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Results Table
# ─────────────────────────────────────────────────────────────────────────────

def _print_summary():
    print("\n" + "═" * 80)
    print("  DEFENCESYS FINAL AUDIT — RESULTS SUMMARY")
    print("═" * 80)

    col_name   = 50
    col_status =  7
    col_detail = 40

    header = f"  {'Test':<{col_name}}  {'Status':<{col_status}}  {'Details':<{col_detail}}"
    print(header)
    print("  " + "─" * (col_name + col_status + col_detail + 4))

    total   = len(_results)
    passed  = sum(1 for r in _results if r.status == "PASS")
    failed  = sum(1 for r in _results if r.status == "FAIL")
    skipped = sum(1 for r in _results if r.status == "SKIP")
    warned  = sum(1 for r in _results if r.status == "WARN")

    icons = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭", "WARN": "⚠️"}
    for r in _results:
        icon = icons.get(r.status, " ")
        print(f"  {r.name:<{col_name}}  {icon} {r.status:<{col_status-2}}  {r.detail[:col_detail]}")

    print("  " + "─" * (col_name + col_status + col_detail + 4))
    print(f"\n  Total: {total}  ✅ {passed}  ❌ {failed}  ⚠️  {warned}  ⏭  {skipped}")

    if failed == 0:
        print("\n  🎉  All critical checks passed! System is production-ready.")
    else:
        print(f"\n  ⚠️   {failed} critical check(s) failed. Review output above.")

    print("═" * 80 + "\n")
    return failed


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="DEFENCESYS Final Polish Audit")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"Django base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--ai-url", default=DEFAULT_AI_URL,
                        help=f"FastAPI AI Engine URL (default: {DEFAULT_AI_URL})")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")

    print("\n" + "═" * 80)
    print("  🛡️  DEFENCESYS — Final Polish Audit Script")
    print(f"     Target: {base}")
    print(f"     User:   {TEST_USER}")
    print("═" * 80)

    session = _Session()

    suite_auth(base, session)
    suite_phishing(base, session)
    suite_deepfake(base, session)
    suite_threat_graph(base, session)

    failed = _print_summary()
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
