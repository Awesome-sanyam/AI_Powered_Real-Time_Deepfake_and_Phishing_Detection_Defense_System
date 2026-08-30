"""
Core App Views
==============
DashboardView — authenticated landing page that aggregates live stats
from PostgreSQL models and passes them as template context.
"""
from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

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

        return render(request, self.template_name, {
            "total_scans":       total_scans,
            "deepfakes_flagged": deepfakes_flagged,
            "phishing_blocked":  phishing_blocked,
            "active_keys":       active_keys,
            "total_signed":      total_signed,
            "recent_deepfakes":  recent_deepfakes,
            "recent_phishing":   recent_phishing,
        })
