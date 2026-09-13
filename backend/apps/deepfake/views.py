"""
Deepfake App Views
==================
Phase 4: Adds DeepfakeMonitorView (HTML, @login_required) that passes
real DB context alongside the existing DRF API views.

Phase 3 (File Upload):
  DeepfakeFileUploadView  — POST /api/deepfake/upload/
      Accepts multipart video/audio upload, saves to a temp dir,
      dispatches analyze_deepfake_file_async Celery task,
      returns {session_id, status: "queued"}.

  DeepfakeFileScanResultView — GET /api/deepfake/file-scan/<session_id>/
      Returns the current verdict from the database (poll until complete).
"""
from __future__ import annotations

import logging
import os
import tempfile
import uuid

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from .models import DeepfakeScanSession
from .serializers import DeepfakeScanSessionSerializer
from .tasks import analyze_deepfake_file_async

logger = logging.getLogger(__name__)

# Accepted MIME types for video and audio uploads
_VIDEO_TYPES = {
    "video/mp4", "video/webm", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "application/octet-stream",
}
_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav",
    "audio/aac", "audio/ogg", "audio/webm",
}

# Temp dir for uploaded files (cleaned up by the Celery task)
_UPLOAD_DIR = os.path.join(
    settings.BASE_DIR, "media", "deepfake_uploads"
)


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


class DeepfakeFileUploadView(APIView):
    """
    POST /api/deepfake/upload/  — Upload video or audio file for deepfake analysis.

    Accepts multipart/form-data with a single field `file`.
    Returns {session_id, status: "queued"} immediately.
    Poll /api/deepfake/file-scan/<session_id>/ for the verdict.
    """
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def post(self, request):
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response(
                {"error": "No file provided. Use multipart/form-data with field 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = (uploaded.content_type or "application/octet-stream").split(";")[0].strip()
        ext = os.path.splitext(uploaded.name or "")[1].lower()

        if content_type in _VIDEO_TYPES or ext in (".mp4", ".webm", ".mov", ".avi", ".mkv"):
            file_type = "video"
        elif content_type in _AUDIO_TYPES or ext in (".mp3", ".wav", ".aac", ".ogg", ".m4a"):
            file_type = "audio"
        else:
            return Response(
                {
                    "error": (
                        f"Unsupported file type '{content_type}' (ext: '{ext}'). "
                        "Accepted: .mp4, .webm, .mov (video) or .mp3, .wav, .aac (audio)."
                    )
                },
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

        # Sanity check: max 500 MB
        max_size = 500 * 1024 * 1024
        if uploaded.size and uploaded.size > max_size:
            return Response(
                {"error": "File too large. Maximum size is 500 MB."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        # Save to temp dir (Celery task cleans it up)
        os.makedirs(_UPLOAD_DIR, exist_ok=True)
        session_id = str(uuid.uuid4())
        file_name = f"{session_id}{ext or ('.mp4' if file_type == 'video' else '.wav')}"
        file_path = os.path.join(_UPLOAD_DIR, file_name)

        with open(file_path, "wb") as f:
            for chunk in uploaded.chunks():
                f.write(chunk)

        logger.info(
            "File upload received: session=%s type=%s size=%s path=%s",
            session_id, file_type, uploaded.size, file_path,
        )

        # Dispatch async task
        analyze_deepfake_file_async.delay(
            session_id=session_id,
            file_path=file_path,
            file_type=file_type,
        )

        return Response(
            {
                "session_id": session_id,
                "status": "queued",
                "file_type": file_type,
                "message": (
                    f"File analysis queued. "
                    f"Poll /api/deepfake/file-scan/{session_id}/ for the verdict."
                ),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class DeepfakeFileScanResultView(APIView):
    """
    GET /api/deepfake/file-scan/<session_id>/
    Returns current verdict for an uploaded-file scan.
    Returns {"status": "pending"} if the Celery task has not completed yet.
    """

    def get(self, request, session_id: str):
        try:
            session = DeepfakeScanSession.objects.get(session_id=session_id)
        except DeepfakeScanSession.DoesNotExist:
            # Task queued but not yet saved — still pending
            return Response({"status": "pending", "session_id": session_id})

        if session.is_deepfake is None:
            return Response({"status": "pending", "session_id": session_id})

        return Response({
            "status": "complete",
            "session_id": session_id,
            "is_deepfake": session.is_deepfake,
            "confidence": session.confidence,
            "frame_count": session.frame_count,
            "processing_time_ms": session.processing_time_ms,
            "signed_verdict": session.signed_verdict,
            "public_key_pem": session.public_key_pem,
        })
