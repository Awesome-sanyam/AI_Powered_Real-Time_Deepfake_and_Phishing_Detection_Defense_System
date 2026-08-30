"""
Deepfake App Views
==================
Phase 4: Adds DeepfakeMonitorView (HTML, @login_required) that passes
real DB context alongside the existing DRF API views.
"""
from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import generics

from .models import DeepfakeScanSession
from .serializers import DeepfakeScanSessionSerializer

logger = logging.getLogger(__name__)


# ── HTML View ──────────────────────────────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class DeepfakeMonitorView(View):
    """GET /deepfake/monitor/ — Live monitor page with recent session history."""

    template_name = "deepfake/monitor.html"

    def get(self, request):
        recent_sessions = list(
            DeepfakeScanSession.objects.order_by("-created_at")
            .values(
                "session_id", "is_deepfake", "confidence",
                "frame_count", "processing_time_ms", "created_at",
            )[:10]
        )
        total_sessions = DeepfakeScanSession.objects.count()
        flagged_count  = DeepfakeScanSession.objects.filter(is_deepfake=True).count()

        return render(request, self.template_name, {
            "recent_sessions": recent_sessions,
            "total_sessions":  total_sessions,
            "flagged_count":   flagged_count,
        })


# ── DRF API Views ──────────────────────────────────────────────────────────────

class DeepfakeScanSessionListView(generics.ListAPIView):
    """GET /api/deepfake/sessions/ — list all scan sessions (newest first)."""
    queryset = DeepfakeScanSession.objects.all()
    serializer_class = DeepfakeScanSessionSerializer


class DeepfakeScanSessionDetailView(generics.RetrieveAPIView):
    """GET /api/deepfake/sessions/<session_id>/ — retrieve a single session."""
    queryset = DeepfakeScanSession.objects.all()
    serializer_class = DeepfakeScanSessionSerializer
    lookup_field = "session_id"
