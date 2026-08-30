"""
Phishing App Views
==================
Phase 3: Added PhishingScanSubmitView for async scan submission via REST.
"""
import uuid

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PhishingScan
from .serializers import PhishingScanSerializer
from .tasks import analyze_phishing_async


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

    The Celery task analyze_phishing_async runs asynchronously, persists the
    verdict in PostgreSQL (PhishingScan) and writes Neo4j threat nodes.
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
