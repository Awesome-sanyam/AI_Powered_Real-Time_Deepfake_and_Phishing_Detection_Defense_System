"""
Django project URL configuration.
Phase 4: Added auth routes (/auth/login/, /auth/register/, /auth/logout/)
and replaced TemplateView stubs with real login-protected views that supply
DB context to templates.
"""
from django.contrib import admin
from django.urls import path, include

# HTML views — these replace the old TemplateView stubs
from apps.core.views import DashboardView
from apps.deepfake.views import DeepfakeMonitorView
from apps.phishing.views import PhishingScannerView
from apps.threat_graph.views import ThreatGraphPageView

# Auth views
from apps.identity.views import login_view, register_view, logout_view

# ── Auth URL group ────────────────────────────────────────────────────────────
auth_patterns = ([
    path("login/",    login_view,    name="login"),
    path("register/", register_view, name="register"),
    path("logout/",   logout_view,   name="logout"),
], "auth")

# ── UI route groups (namespaced to match base.html url tags) ──────────────────
ui_dashboard_patterns = ([
    path("", DashboardView.as_view(), name="index"),
], "dashboard")

ui_deepfake_patterns = ([
    path("monitor/", DeepfakeMonitorView.as_view(), name="monitor"),
], "deepfake")

ui_phishing_patterns = ([
    path("scanner/", PhishingScannerView.as_view(), name="scanner"),
], "phishing")

ui_graph_patterns = ([
    path("view/", ThreatGraphPageView.as_view(), name="view"),
], "threat_graph")

# ── Root URL patterns ─────────────────────────────────────────────────────────
urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth
    path("auth/", include(auth_patterns)),

    # API Routes
    path("api/deepfake/", include("apps.deepfake.urls")),
    path("api/phishing/", include("apps.phishing.urls")),
    path("api/identity/", include("apps.identity.urls")),
    path("api/graph/",    include("apps.threat_graph.urls")),

    # Frontend UI Routes
    path("",              include(ui_dashboard_patterns)),
    path("deepfake/",     include(ui_deepfake_patterns)),
    path("phishing/",     include(ui_phishing_patterns)),
    path("threat-graph/", include(ui_graph_patterns)),
]
