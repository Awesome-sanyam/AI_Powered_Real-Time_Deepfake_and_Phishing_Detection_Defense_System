"""
Phishing App Views
==================
Phase 4: Adds PhishingScannerView (HTML, @login_required) alongside
the existing DRF REST + submit views.
"""
from __future__ import annotations

import logging
import uuid

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PhishingScan
from .serializers import PhishingScanSerializer
from .tasks import analyze_phishing_async

logger = logging.getLogger(__name__)


# ── HTML View ──────────────────────────────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class PhishingScannerView(View):
    """GET /phishing/scanner/ — Scanner page with recent scan history."""

    template_name = "phishing/scanner.html"

    def get(self, request):
        recent_scans = list(
            PhishingScan.objects.order_by("-created_at")
            .values(
                "id", "session_id", "is_phishing", "confidence",
                "risk_level", "signals", "explanation",
                "url", "processing_time_ms", "created_at",
            )[:10]
        )
        total_scans    = PhishingScan.objects.count()
        blocked_count  = PhishingScan.objects.filter(is_phishing=True).count()

        return render(request, self.template_name, {
            "recent_scans":  recent_scans,
            "total_scans":   total_scans,
            "blocked_count": blocked_count,
        })


# ── DRF API Views ──────────────────────────────────────────────────────────────

class PhishingScanListView(generics.ListAPIView):
    """GET /api/phishing/scans/ — list all phishing scan results."""
    queryset = PhishingScan.objects.all()
    serializer_class = PhishingScanSerializer


class PhishingScanDetailView(generics.RetrieveAPIView):
    """GET /api/phishing/scans/<pk>/ — retrieve a single scan result."""
    queryset = PhishingScan.objects.all()
    serializer_class = PhishingScanSerializer


class PhishingScanSubmitView(APIView):
    """
    POST /api/phishing/scan/ — Submit content for async phishing analysis.

    Request body (JSON):
        {
            "content":  str,          # Email body or suspicious message (required)
            "url":      str | null,   # Suspicious URL (optional)
            "headers":  dict | null   # Email headers dict (optional)
        }

    Response:
        {
            "session_id": str,        # UUID for this scan session
            "status":     "queued"    # Always — result comes back via /api/phishing/scans/<id>/
        }
    """

    def post(self, request):
        content = request.data.get("content", "").strip()
        if not content:
            return Response(
                {"error": "content is required and must not be empty."},
                status=400,
            )

        session_id = str(uuid.uuid4())
        url     = request.data.get("url") or ""
        headers = request.data.get("headers") or None

        analyze_phishing_async.delay(
            session_id=session_id,
            content=content,
            url=url,
            headers=headers,
        )

        return Response({
            "session_id": session_id,
            "status":     "queued",
            "message":    "Phishing analysis queued. Poll /api/phishing/scans/ for results.",
        }, status=202)
