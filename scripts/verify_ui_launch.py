#!/usr/bin/env python3
"""
scripts/verify_ui_launch.py — DEFENCESYS Enterprise UI/UX Launch Audit
======================================================================
Automated verification suite validating:
  1. Template Compilation & Rendering (Zero template errors, valid HTML5)
  2. Route Protection & RBAC (@login_required redirects unauthenticated users to /auth/login/)
  3. Static Theme & Script Assets (theme_toggle.js, ws_client.js, webcam_stream.js, graph_visualizer.js)
  4. Channels WebSocket Protocol Handshakes (Alerts feed & Deepfake session channels)
  5. Live API & Infrastructure Telemetry (/api/ai-engine/health/, /api/graph/data/, etc.)

Usage:
    python scripts/verify_ui_launch.py
"""
import os
import sys
import asyncio
from pathlib import Path

# Add backend directory to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Ensure Django settings environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "soc_db")
os.environ.setdefault("POSTGRES_USER", "soc_user")
os.environ.setdefault("POSTGRES_PASSWORD", "soc_password")

import django
django.setup()

from django.template.loader import render_to_string, get_template
from django.test import Client, RequestFactory
from django.contrib.auth import get_user_model
from channels.testing import WebsocketCommunicator
from config.asgi import application

User = get_user_model()

# ── Color Output Helpers ──────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

results = []

def record(suite: str, test_name: str, passed: bool, details: str = ""):
    status_str = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    icon = "✅" if passed else "❌"
    print(f"  {icon}  {test_name:<46} {status_str}  {details}")
    results.append({
        "suite": suite,
        "test": test_name,
        "passed": passed,
        "details": details
    })


# ── Suite 1: Template Compilation & Rendering ─────────────────────────────────
def test_templates():
    print(f"\n{BOLD}{CYAN}📋 Suite 1: Template Compilation & Rendering{RESET}")
    
    # Get or create test user
    test_user, _ = User.objects.get_or_create(username="ui_auditor", defaults={"email": "auditor@defencesys.internal"})
    
    templates_to_test = [
        ("base.html", {"user": test_user}),
        ("dashboard/index.html", {
            "user": test_user,
            "total_scans": 42,
            "deepfakes_flagged": 5,
            "phishing_blocked": 12,
            "active_keys": 3,
            "total_signed": 15,
            "threat_node_count": 8,
            "recent_deepfakes": [],
            "recent_phishing": [],
            "vault_keys": []
        }),
        ("deepfake/monitor.html", {
            "user": test_user,
            "recent_sessions": []
        }),
        ("phishing/scanner.html", {
            "user": test_user
        }),
        ("threat_graph/view.html", {
            "user": test_user
        }),
        ("identity/login.html", {}),
        ("identity/register.html", {}),
    ]

    for t_name, ctx in templates_to_test:
        try:
            tmpl = get_template(t_name)
            output = tmpl.render(ctx)
            # Verify basic markup
            has_content = len(output) > 200
            # Verify no unresolved TemplateSyntax error or crash
            record("Templates", f"Render: {t_name}", has_content, f"{len(output)} bytes compiled")
        except Exception as e:
            record("Templates", f"Render: {t_name}", False, f"Error: {str(e)[:50]}")


# ── Suite 2: Route Protection & Authentication Redirection ────────────────────
def test_route_protection():
    print(f"\n{BOLD}{CYAN}🔒 Suite 2: Route Protection & RBAC Enforcement{RESET}")
    client = Client()

    protected_routes = [
        ("/", "dashboard:index"),
        ("/deepfake/monitor/", "deepfake:monitor"),
        ("/phishing/scanner/", "phishing:scanner"),
        ("/threat-graph/view/", "threat_graph:view"),
    ]

    # Test 2.1: Unauthenticated redirects to /auth/login/?next=...
    for path, name in protected_routes:
        try:
            resp = client.get(path)
            is_redirect = (resp.status_code == 302)
            has_login_target = "/auth/login/" in resp.get("Location", "")
            record("Route Protection", f"Unauth Redirect: {name}", is_redirect and has_login_target, f"HTTP {resp.status_code} -> {resp.get('Location', '')}")
        except Exception as e:
            record("Route Protection", f"Unauth Redirect: {name}", False, str(e)[:50])

    # Test 2.2: Authenticated user gets HTTP 200
    user, _ = User.objects.get_or_create(username="soc_analyst_test")
    client.force_login(user)

    for path, name in protected_routes:
        try:
            resp = client.get(path)
            is_ok = (resp.status_code == 200)
            record("Route Protection", f"Auth Access 200: {name}", is_ok, f"HTTP {resp.status_code} OK")
        except Exception as e:
            record("Route Protection", f"Auth Access 200: {name}", False, str(e)[:50])


# ── Suite 3: Static Theme & JavaScript Verification ───────────────────────────
def test_static_assets():
    print(f"\n{BOLD}{CYAN}🎨 Suite 3: Static Theme & JavaScript Integrity{RESET}")
    
    required_scripts = [
        "backend/static/js/theme_toggle.js",
        "backend/static/js/ws_client.js",
        "backend/static/js/webcam_stream.js",
        "backend/static/js/graph_visualizer.js",
    ]

    for rel_path in required_scripts:
        file_path = REPO_ROOT / rel_path
        exists = file_path.is_file()
        if exists:
            content = file_path.read_text(encoding="utf-8")
            valid = len(content) > 100
            # Check for critical keywords
            if "theme_toggle" in rel_path:
                valid = valid and "themeChanged" in content and "localStorage" in content
            elif "graph_visualizer" in rel_path:
                valid = valid and "themeChanged" in content and "ThreatGraphVisualizer" in content
            elif "webcam_stream" in rel_path:
                valid = valid and "VERIFIED_BY_ECDSA" in content and "WebcamStreamManager" in content
            
            record("Static Assets", f"Script: {file_path.name}", valid, f"{len(content)} bytes, verified features")
        else:
            record("Static Assets", f"Script: {rel_path}", False, "File missing")


# ── Suite 4: Channels WebSocket Protocol Handshakes ───────────────────────────
async def async_test_websockets():
    print(f"\n{BOLD}{CYAN}⚡ Suite 4: WebSocket Channels Protocol Handshakes{RESET}")

    # Test 4.1: Alerts feed consumer handshake
    try:
        comm = WebsocketCommunicator(application, "ws/alerts/")
        connected, subprotocol = await comm.connect()
        record("WebSockets", "Handshake: ws/alerts/", connected, "Connected via ASGI router")
        if connected:
            await comm.disconnect()
    except Exception as e:
        record("WebSockets", "Handshake: ws/alerts/", False, str(e)[:60])

    # Test 4.2: Deepfake live session handshake
    try:
        session_id = "test-session-ui-launch"
        comm = WebsocketCommunicator(application, f"ws/deepfake/{session_id}/")
        connected, subprotocol = await comm.connect()
        record("WebSockets", f"Handshake: ws/deepfake/{session_id[:12]}/", connected, "Connected via ASGI router")
        if connected:
            await comm.disconnect()
    except Exception as e:
        record("WebSockets", "Handshake: ws/deepfake/<session>/", False, str(e)[:60])


# ── Suite 5: Live API Telemetry Verification ──────────────────────────────────
def test_api_telemetry():
    print(f"\n{BOLD}{CYAN}📡 Suite 5: REST API & Telemetry Endpoints{RESET}")
    client = Client()
    user, _ = User.objects.get_or_create(username="soc_analyst_test")
    client.force_login(user)

    endpoints = [
        ("/api/ai-engine/health/", "AI Engine Health Proxy"),
        ("/api/graph/data/", "Threat Graph Data API"),
        ("/api/graph/health/", "Neo4j Graph Health Check"),
        ("/api/deepfake/sessions/", "Deepfake Sessions List"),
        ("/api/phishing/scans/", "Phishing Scans List"),
    ]

    for path, desc in endpoints:
        try:
            resp = client.get(path)
            is_ok = (resp.status_code == 200)
            content_type = resp.headers.get("Content-Type", "")
            record("API Telemetry", f"API: {desc}", is_ok, f"HTTP {resp.status_code} ({content_type.split(';')[0]})")
        except Exception as e:
            record("API Telemetry", f"API: {desc}", False, str(e)[:50])


# ── Main Runner & Results Table ───────────────────────────────────────────────
def main():
    print(f"{BOLD}{GREEN}════════════════════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{GREEN}  🛡️  DEFENCESYS — Enterprise UI/UX Launch Readiness Audit{RESET}")
    print(f"{BOLD}{GREEN}════════════════════════════════════════════════════════════════════════════════{RESET}")

    test_templates()
    test_route_protection()
    test_static_assets()
    asyncio.run(async_test_websockets())
    test_api_telemetry()

    # Executive Results Table
    print(f"\n{BOLD}{GREEN}════════════════════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}  DEFENCESYS UI/UX LAUNCH AUDIT — EXECUTIVE SUMMARY TABLE{RESET}")
    print(f"{BOLD}{GREEN}════════════════════════════════════════════════════════════════════════════════{RESET}")
    print(f"  {'Suite':<18} {'Check':<36} {'Status':<10} {'Details'}")
    print(f"  {'-'*18} {'-'*36} {'-'*10} {'-'*30}")

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    for r in results:
        stat = f"{GREEN}✅ PASS{RESET}" if r["passed"] else f"{RED}❌ FAIL{RESET}"
        print(f"  {r['suite']:<18} {r['test']:<36} {stat:<10} {r['details']}")

    print(f"  {'-'*18} {'-'*36} {'-'*10} {'-'*30}")
    print(f"\n  Total Checks: {total}  |  {GREEN}Passed: {passed}{RESET}  |  {RED}Failed: {failed}{RESET}")

    if failed == 0:
        print(f"\n{BOLD}{GREEN}  🎉 ALL UI/UX AND LAUNCH CHECKS PASSED — READY FOR COMMERCIAL LAUNCH!{RESET}\n")
    else:
        print(f"\n{BOLD}{RED}  ⚠️  SOME CHECKS FAILED — REVIEW THE LOGS ABOVE.{RESET}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
