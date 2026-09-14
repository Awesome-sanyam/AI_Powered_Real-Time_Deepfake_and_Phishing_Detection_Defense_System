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
import uuid

import base64
import sys
import cv2
import httpx
import numpy as np

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
from .tasks import (
    analyze_deepfake_file_async,
    _extract_from_video,
    _extract_audio_b64,
    _write_deepfake_to_graph,
)

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


class DeepfakeUploadScanView(APIView):
    """
    POST /api/deepfake/upload-scan/
    Accepts multipart file upload for direct multi-modal deepfake analysis.
    Extracts frames at 5 FPS via OpenCV and extracts audio.
    Executes CrossModalVerificationEngine analysis and returns signed DeepfakeVerdict JSON.
    """
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def post(self, request):
        uploaded = request.FILES.get("file") or request.FILES.get("media_file")
        if not uploaded:
            return Response(
                {"error": "No file provided. Use multipart/form-data with field 'file' or 'media_file'."},
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
                        "Accepted: .mp4, .mov, .avi, .webm (video) or .wav, .mp3, .aac (audio)."
                    )
                },
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

        max_size = 500 * 1024 * 1024
        if uploaded.size and uploaded.size > max_size:
            return Response(
                {"error": "File too large. Maximum size is 500 MB."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        os.makedirs(_UPLOAD_DIR, exist_ok=True)
        session_id = str(uuid.uuid4())
        file_name = f"{session_id}{ext or ('.mp4' if file_type == 'video' else '.wav')}"
        file_path = os.path.join(_UPLOAD_DIR, file_name)

        with open(file_path, "wb") as f:
            for chunk in uploaded.chunks():
                f.write(chunk)

        try:
            sample_fps = 5.0
            frames_b64 = []
            audio_b64 = ""

            if file_type == "video":
                frames_b64, audio_b64 = _extract_from_video(file_path, sample_fps)
            elif file_type == "audio":
                audio_b64 = _extract_audio_b64(file_path)
                dummy = np.zeros((224, 224, 3), dtype=np.uint8)
                _, buf = cv2.imencode(".jpg", dummy)
                frames_b64 = [base64.b64encode(buf.tobytes()).decode()] * 3

            if not frames_b64:
                return Response(
                    {"error": "Could not extract valid media frames from uploaded file."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Cap frames to keep real-time performance smooth (max 60 frames = 12 sec at 5 FPS)
            if len(frames_b64) > 60:
                frames_b64 = frames_b64[:60]

            payload = {
                "session_id": session_id,
                "frames_b64": frames_b64,
                "audio_b64": audio_b64,
                "fps": sample_fps,
            }

            verdict = None
            # 1. Try FastAPI AI Engine on port 8001
            try:
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(
                        f"{settings.AI_ENGINE_BASE_URL}/scan/deepfake",
                        json=payload,
                    )
                    if resp.status_code == 200:
                        verdict = resp.json()
            except Exception as exc:
                logger.warning("AI Engine HTTP call failed, falling back to local engine: %s", exc)

            # 2. Local fallback if AI Engine HTTP was unavailable
            if verdict is None:
                parent_dir = str(settings.BASE_DIR.parent)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                from ai_engine.deepfake.cross_modal_engine import CrossModalVerificationEngine
                engine = CrossModalVerificationEngine()
                raw_frames = []
                for b64 in frames_b64:
                    raw_bytes = base64.b64decode(b64)
                    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
                    raw_frames.append(cv2.imdecode(arr, cv2.IMREAD_COLOR))
                raw_audio = base64.b64decode(audio_b64) if audio_b64 else b""
                local_verdict = engine.analyze(
                    session_id=session_id,
                    frames=raw_frames,
                    audio_bytes=raw_audio,
                    fps=sample_fps,
                )
                verdict = {
                    "session_id": local_verdict.session_id,
                    "is_deepfake": local_verdict.is_deepfake,
                    "confidence": local_verdict.confidence,
                    "frame_count": len(local_verdict.frame_results),
                    "processing_time_ms": local_verdict.processing_time_ms,
                    "signed_verdict": local_verdict.signed_verdict,
                    "public_key_pem": local_verdict.public_key_pem,
                    "frame_results": [
                        {
                            "frame_index": fr.frame_index,
                            "visual_artifact_score": fr.visual_artifact_score,
                            "lip_sync_delay_ms": fr.lip_sync_delay_ms,
                            "blink_rate_bpm": fr.blink_rate_bpm,
                            "is_suspicious": fr.is_suspicious,
                            "confidence": fr.confidence,
                        }
                        for fr in local_verdict.frame_results
                    ],
                }

            # 3. Save to PostgreSQL
            is_deepfake = verdict.get("is_deepfake", False)
            confidence = float(verdict.get("confidence", 0.0))
            frame_count = int(verdict.get("frame_count", len(frames_b64)))
            processing_time_ms = float(verdict.get("processing_time_ms", 0.0))
            signed_verdict = verdict.get("signed_verdict", "")
            public_key_pem = verdict.get("public_key_pem", "")

            DeepfakeScanSession.objects.create(
                session_id=session_id,
                is_deepfake=is_deepfake,
                confidence=confidence,
                frame_count=frame_count,
                processing_time_ms=processing_time_ms,
                signed_verdict=signed_verdict,
                public_key_pem=public_key_pem,
            )

            # 4. Neo4j threat graph node
            _write_deepfake_to_graph(
                session_id=session_id,
                is_deepfake=is_deepfake,
                confidence=confidence,
            )

            # 5. Enrich metrics for UI rendering
            frame_results = verdict.get("frame_results", [])
            lip_timeline = [
                {
                    "time_sec": round(i / sample_fps, 2),
                    "delay_ms": round(float(fr.get("lip_sync_delay_ms", 0.0)), 1),
                    "is_suspicious": bool(fr.get("lip_sync_delay_ms", 0.0) > 80.0),
                }
                for i, fr in enumerate(frame_results)
            ]
            blink_bpm_vals = [float(fr.get("blink_rate_bpm", 0.0)) for fr in frame_results if fr.get("blink_rate_bpm")]
            avg_blink = float(np.mean(blink_bpm_vals)) if blink_bpm_vals else 16.0
            blink_anomaly = bool(avg_blink < 8.0 or avg_blink > 30.0)

            artifact_scores = [float(fr.get("visual_artifact_score", 0.0)) for fr in frame_results]
            mean_artifact = float(np.mean(artifact_scores)) if artifact_scores else 0.0
            max_artifact = float(np.max(artifact_scores)) if artifact_scores else 0.0
            suspicious_count = sum(1 for fr in frame_results if fr.get("is_suspicious"))

            verdict_text = "DEEPFAKE DETECTED" if is_deepfake else "AUTHENTIC MEDIA"
            signals_list = []
            if is_deepfake:
                signals_list.append("facial-inconsistency")
            if blink_anomaly:
                signals_list.append("blink-rate-anomaly")
            if mean_artifact > 0.40:
                signals_list.append("visual-compression-artifact")

            response_payload = {
                "session_id": session_id,
                "is_deepfake": is_deepfake,
                "verdict": verdict_text,
                "confidence": confidence,
                "threat_score": round(confidence * 100, 1),
                "signals": signals_list,
                "frame_count": frame_count,
                "processing_time_ms": processing_time_ms,
                "signed_verdict": signed_verdict,
                "public_key_pem": public_key_pem,
                "frame_results": frame_results,
                "lip_sync_timeline": lip_timeline,
                "blink_report": {
                    "bpm": round(avg_blink, 1),
                    "normal_range": "8–30 BPM",
                    "is_anomaly": blink_anomaly,
                },
                "artifact_breakdown": {
                    "mean_score": round(mean_artifact, 3),
                    "max_score": round(max_artifact, 3),
                    "suspicious_frames_count": suspicious_count,
                    "total_frames": len(frame_results),
                },
                "breakdown": {
                    "frames_analyzed": frame_count,
                    "lip_sync_timeline": lip_timeline,
                    "blink_report": {
                        "bpm": round(avg_blink, 1),
                        "normal_range": "8–30 BPM",
                        "is_anomaly": blink_anomaly,
                    },
                    "visual_artifacts": {
                        "mean_score": round(mean_artifact, 3),
                        "max_score": round(max_artifact, 3),
                    },
                },
                "file_type": file_type,
                "file_name": uploaded.name,
            }

            return Response(response_payload, status=status.HTTP_200_OK)

        finally:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
