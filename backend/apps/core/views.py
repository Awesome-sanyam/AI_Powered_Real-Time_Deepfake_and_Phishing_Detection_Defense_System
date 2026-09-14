"""
Core App Views
==============
DashboardView — authenticated landing page that aggregates live stats
from PostgreSQL models and passes them as template context.
"""
from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
import httpx

from apps.deepfake.models import DeepfakeScanSession
from apps.identity.models import IdentityKey
from apps.phishing.models import PhishingScan

logger = logging.getLogger(__name__)


@method_decorator(login_required, name="dispatch")
class DashboardView(View):
    """
    GET / — SOC Overview dashboard.

    Renders real aggregate stats from PostgreSQL so the page has server-side
    initial values before the JS polling takes over.
    """

    template_name = "dashboard/index.html"

    def get(self, request):
        # Deepfake stats
        total_deepfake_sessions = DeepfakeScanSession.objects.count()
        deepfakes_flagged = DeepfakeScanSession.objects.filter(is_deepfake=True).count()
        deepfake_signed = DeepfakeScanSession.objects.exclude(signed_verdict="").count()

        # Phishing stats
        total_phishing_scans = PhishingScan.objects.count()
        phishing_blocked = PhishingScan.objects.filter(is_phishing=True).count()
        phishing_signed = PhishingScan.objects.exclude(signed_verdict="").count()

        # Identity keys
        active_keys = IdentityKey.objects.filter(is_revoked=False).count()
        vault_keys = list(
            IdentityKey.objects.select_related("user")
            .order_by("-created_at")[:5]
        )

        total_scans = total_deepfake_sessions + total_phishing_scans
        total_signed = deepfake_signed + phishing_signed

        # Recent activity for feed pre-population (last 10, newest first)
        recent_deepfakes = list(
            DeepfakeScanSession.objects.filter(is_deepfake=True)
            .order_by("-created_at")
            .values("session_id", "confidence", "created_at")[:5]
        )
        recent_phishing = list(
            PhishingScan.objects.filter(is_phishing=True)
            .order_by("-created_at")
            .values("session_id", "risk_level", "confidence", "created_at")[:5]
        )

        # Neo4j threat node count (best-effort — graceful fallback)
        threat_node_count = 0
        try:
            from apps.threat_graph.graph_client import count_threat_nodes
            threat_node_count = count_threat_nodes()
        except Exception:
            pass  # Neo4j offline is non-critical

        return render(request, self.template_name, {
            "total_scans":        total_scans,
            "deepfakes_flagged":  deepfakes_flagged,
            "phishing_blocked":   phishing_blocked,
            "active_keys":        active_keys,
            "vault_keys":         vault_keys,
            "total_signed":       total_signed,
            "threat_node_count":  threat_node_count,
            "recent_deepfakes":   recent_deepfakes,
            "recent_phishing":    recent_phishing,
        })


def ai_engine_health(request):
    """
    Proxy endpoint to check the actual health of the FastAPI AI Engine (port 8001).
    Used by the dashboard UI status dot.
    """
    try:
        url = f"{settings.AI_ENGINE_BASE_URL}/health"
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return JsonResponse({"status": "ok"})
    except Exception:
        pass
    return JsonResponse({"status": "offline"})
