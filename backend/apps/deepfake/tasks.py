"""
Deepfake App — Celery Tasks
============================
Phase 2: Calls the AI Engine, persists results to PostgreSQL,
pushes verdicts via Django Channels, and writes threat nodes to Neo4j.

Task chain per scan session:
  1. POST frames + audio → AI Engine /scan/deepfake
  2. Save/update DeepfakeScanSession in PostgreSQL
  3. Push signed verdict back to client WebSocket via channel layer
  4. Write session threat node to Neo4j graph (non-blocking)

Phase 3 (File Upload):
  analyze_deepfake_file_async — extracts frames from uploaded video/audio
  files using OpenCV/wave, batches them to the AI Engine, and broadcasts
  the cumulative verdict via a per-session Redis group key.
"""
from __future__ import annotations

import base64
import gc
import logging
import os
import tempfile
import wave

import httpx
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings

from .models import DeepfakeScanSession

logger = logging.getLogger(__name__)

AI_ENGINE_BASE_URL = settings.AI_ENGINE_BASE_URL


# ─────────────────────────────────────────────────────────────────────────────
# Task 1: Live-stream analysis (called from DeepfakeStreamConsumer)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=1)
def analyze_deepfake_async(
    self,
    session_id: str,
    channel_name: str,
    frames_b64: list[str],
    audio_b64: str,
    fps: float = 25.0,
) -> None:
    """
    Celery task: forward frame + audio data to the AI Engine,
    persist the verdict to PostgreSQL, and push it back over WebSocket.

    Args:
        session_id:   Unique scan session identifier.
        channel_name: Django Channels channel name for the requesting WS client.
        frames_b64:   List of base64-encoded JPEG frame bytes.
        audio_b64:    Base64-encoded raw 16-bit PCM mono audio bytes.
        fps:          Frames per second of the source stream.
    """
    try:
        payload = {
            "session_id": session_id,
            "frames_b64": frames_b64,
            "audio_b64": audio_b64,
            "fps": fps,
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{AI_ENGINE_BASE_URL}/scan/deepfake",
                json=payload,
            )
            response.raise_for_status()
            verdict = response.json()

        # ── 1. Persist to PostgreSQL ───────────────────────────────────────────
        DeepfakeScanSession.objects.update_or_create(
            session_id=session_id,
            defaults={
                "is_deepfake": verdict.get("is_deepfake"),
                "confidence": verdict.get("confidence"),
                "frame_count": verdict.get("frame_count", len(frames_b64)),
                "processing_time_ms": verdict.get("processing_time_ms"),
                "signed_verdict": verdict.get("signed_verdict", ""),
                "public_key_pem": verdict.get("public_key_pem", ""),
            },
        )
        logger.info(
            "Deepfake scan saved: session=%s is_deepfake=%s conf=%.3f",
            session_id,
            verdict.get("is_deepfake"),
            verdict.get("confidence", 0.0),
        )

        # ── 2. Push verdict over WebSocket ────────────────────────────────────
        channel_layer = get_channel_layer()
        if channel_layer and channel_name:
            async_to_sync(channel_layer.send)(
                channel_name,
                {
                    "type": "deepfake_verdict",
                    "verdict": {
                        "type": "verdict",
                        "session_id": verdict["session_id"],
                        "is_deepfake": verdict["is_deepfake"],
                        "confidence": verdict["confidence"],
                        "processing_ms": verdict.get("processing_time_ms"),
                        "frame_count": verdict.get("frame_count"),
                        "signed_verdict": verdict.get("signed_verdict"),
                        "public_key_pem": verdict.get("public_key_pem"),
                        "frame_results": verdict.get("frame_results", []),
                    },
                },
            )

        # ── 3. Broadcast to alert_feed group (dashboard bell) ───────────────
        if channel_layer and verdict.get("is_deepfake"):
            from datetime import datetime, timezone
            conf_pct = round((verdict.get("confidence", 0.0)) * 100)
            async_to_sync(channel_layer.group_send)(
                "alert_feed",
                {
                    "type": "threat.alert",
                    "title": "⚠️ Deepfake Detected",
                    "message": (
                        f"Session {session_id[:8]}… classified as FAKE "
                        f"(confidence {conf_pct}%)"
                    ),
                    "alert_type": "deepfake",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "session_id": session_id,
                },
            )

        # ── 4. Write to Neo4j Threat Graph (non-blocking, best-effort) ────────
        _write_deepfake_to_graph(
            session_id=session_id,
            is_deepfake=verdict.get("is_deepfake", False),
            confidence=verdict.get("confidence", 0.0),
        )

    except httpx.HTTPError as exc:
        logger.error(f"AI Engine HTTP error (deepfake): {exc}")
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception(f"Unexpected error in analyze_deepfake_async: {exc}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Task 2: File upload analysis (Video / Audio files)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=1, default_retry_delay=5)
def analyze_deepfake_file_async(
    self,
    session_id: str,
    file_path: str,
    file_type: str,           # "video" | "audio"
    sample_fps: float = 5.0,  # frames per second to sample from video
) -> None:
    """
    Celery task: extract frames (and audio) from an uploaded video or audio file,
    batch them to the AI Engine, persist the verdict, and broadcast updates to the
    polling group `file_scan_{session_id}`.

    Args:
        session_id: Unique identifier for this file scan.
        file_path:  Absolute path to the uploaded file on disk.
        file_type:  "video" or "audio"
        sample_fps: For video, how many frames/second to sample (default: 5).
    """
    channel_layer = get_channel_layer()

    def _broadcast(status: str, progress: int = 0, **extra):
        """Send a progress/verdict update to the file-upload polling group."""
        if channel_layer:
            try:
                async_to_sync(channel_layer.group_send)(
                    f"file_scan_{session_id}",
                    {
                        "type": "file.scan.update",
                        "session_id": session_id,
                        "status": status,
                        "progress": progress,
                        **extra,
                    },
                )
            except Exception as e:
                logger.warning("file_scan broadcast failed: %s", e)

    try:
        _broadcast("processing", 5)

        frames_b64: list[str] = []
        audio_b64: str = ""

        if file_type == "video":
            frames_b64, audio_b64 = _extract_from_video(file_path, sample_fps)
        elif file_type == "audio":
            audio_b64 = _extract_audio_b64(file_path)
            # For audio-only, send a small dummy frame so the engine gets data
            import numpy as np
            import cv2
            dummy = np.zeros((224, 224, 3), dtype=np.uint8)
            _, buf = cv2.imencode(".jpg", dummy)
            frames_b64 = [base64.b64encode(buf.tobytes()).decode()]
        else:
            _broadcast("error", 0, error=f"Unsupported file_type: {file_type}")
            return

        if not frames_b64:
            _broadcast("error", 0, error="Could not extract any frames from the file.")
            return

        _broadcast("analysing", 40)
        logger.info(
            "File scan: session=%s frames=%d audio_bytes=%d",
            session_id, len(frames_b64), len(audio_b64) * 3 // 4,
        )

        # ── Send to AI Engine in a single batch ───────────────────────────────
        payload = {
            "session_id": session_id,
            "frames_b64": frames_b64,
            "audio_b64": audio_b64,
            "fps": sample_fps,
        }

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{AI_ENGINE_BASE_URL}/scan/deepfake",
                json=payload,
            )
            response.raise_for_status()
            verdict = response.json()

        _broadcast("saving", 80)

        # ── Persist verdict ───────────────────────────────────────────────────
        DeepfakeScanSession.objects.update_or_create(
            session_id=session_id,
            defaults={
                "is_deepfake": verdict.get("is_deepfake"),
                "confidence": verdict.get("confidence"),
                "frame_count": verdict.get("frame_count", len(frames_b64)),
                "processing_time_ms": verdict.get("processing_time_ms"),
                "signed_verdict": verdict.get("signed_verdict", ""),
                "public_key_pem": verdict.get("public_key_pem", ""),
            },
        )
        logger.info(
            "File deepfake scan saved: session=%s is_deepfake=%s conf=%.3f",
            session_id, verdict.get("is_deepfake"), verdict.get("confidence", 0.0),
        )

        # ── Broadcast final verdict ───────────────────────────────────────────
        _broadcast(
            "complete",
            100,
            is_deepfake=verdict.get("is_deepfake"),
            confidence=verdict.get("confidence"),
            frame_count=verdict.get("frame_count"),
            processing_time_ms=verdict.get("processing_time_ms"),
            signed_verdict=verdict.get("signed_verdict"),
            public_key_pem=verdict.get("public_key_pem"),
            frame_results=verdict.get("frame_results", []),
        )

        # ── Alert feed broadcast ──────────────────────────────────────────────
        if channel_layer and verdict.get("is_deepfake"):
            from datetime import datetime, timezone
            conf_pct = round((verdict.get("confidence", 0.0)) * 100)
            async_to_sync(channel_layer.group_send)(
                "alert_feed",
                {
                    "type": "threat.alert",
                    "title": "⚠️ Deepfake in Uploaded File",
                    "message": (
                        f"File session {session_id[:8]}… flagged as FAKE "
                        f"(confidence {conf_pct}%)"
                    ),
                    "alert_type": "deepfake",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "session_id": session_id,
                },
            )

        _write_deepfake_to_graph(
            session_id=session_id,
            is_deepfake=verdict.get("is_deepfake", False),
            confidence=verdict.get("confidence", 0.0),
        )

    except httpx.HTTPError as exc:
        logger.error("AI Engine HTTP error (file scan): %s", exc)
        _broadcast("error", 0, error=f"AI Engine unreachable: {exc}")
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception("Unexpected error in analyze_deepfake_file_async")
        _broadcast("error", 0, error=str(exc))
        raise
    finally:
        # Always clean up the temp file
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        gc.collect()


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_from_video(file_path: str, sample_fps: float) -> tuple[list[str], str]:
    """
    Extract JPEG frames and raw PCM audio from a video file using OpenCV.
    Audio extraction falls back gracefully to an empty byte string if ffmpeg
    is unavailable.

    Returns:
        (frames_b64, audio_b64)
    """
    import cv2
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise ValueError(f"OpenCV cannot open file: {file_path}")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(native_fps / sample_fps))

    frames_b64: list[str] = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % step == 0:
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frames_b64.append(base64.b64encode(buf.tobytes()).decode())
            # Cap at 150 frames to avoid OOM on very long videos
            if len(frames_b64) >= 150:
                break
        frame_idx += 1

    cap.release()
    logger.info("Extracted %d frames from video (step=%d, native_fps=%.1f)", len(frames_b64), step, native_fps)

    # Try to extract audio via moviepy (wraps ffmpeg)
    audio_b64 = ""
    try:
        from moviepy.editor import VideoFileClip
        with VideoFileClip(file_path) as clip:
            if clip.audio is not None:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_wav = tmp.name
                try:
                    clip.audio.write_audiofile(tmp_wav, fps=16000, nbytes=2, codec="pcm_s16le", verbose=False, logger=None)
                    audio_b64 = _wav_to_pcm_b64(tmp_wav)
                finally:
                    if os.path.exists(tmp_wav):
                        os.remove(tmp_wav)
    except Exception as exc:
        logger.warning("Audio extraction skipped (moviepy error): %s", exc)

    return frames_b64, audio_b64


def _extract_audio_b64(file_path: str) -> str:
    """
    Load an audio file (wav/mp3) and return raw 16kHz mono PCM as base64.
    Tries librosa first, falls back to wave for raw WAV.
    """
    try:
        import librosa
        import numpy as np
        y, _ = librosa.load(file_path, sr=16000, mono=True)
        # Convert float32 [-1,1] → int16 PCM
        pcm = (y * 32767).astype(np.int16)
        return base64.b64encode(pcm.tobytes()).decode()
    except Exception as exc:
        logger.warning("librosa audio load failed, trying wave: %s", exc)

    # Fallback: raw WAV
    try:
        with wave.open(file_path, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
        return base64.b64encode(raw).decode()
    except Exception as exc:
        logger.warning("wave audio load also failed: %s", exc)
        return ""


def _wav_to_pcm_b64(wav_path: str) -> str:
    """Read a WAV file and return its raw PCM data as base64."""
    try:
        with wave.open(wav_path, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
        return base64.b64encode(raw).decode()
    except Exception as exc:
        logger.warning("wav→pcm conversion failed: %s", exc)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Neo4j helper (shared by both tasks)
# ─────────────────────────────────────────────────────────────────────────────

def _write_deepfake_to_graph(
    session_id: str,
    is_deepfake: bool,
    confidence: float,
) -> None:
    """
    Write deepfake scan result to Neo4j as a Session threat node.
    Gracefully no-ops if Neo4j is offline.
    """
    try:
        from apps.threat_graph.graph_client import upsert_threat_node
        upsert_threat_node(
            node_type="session",
            label=session_id,
            risk_score=confidence if is_deepfake else 0.0,
            metadata={
                "type": "deepfake_scan",
                "is_deepfake": is_deepfake,
                "confidence": confidence,
            },
        )
    except ImportError as exc:
        logger.warning("graph_client import unavailable (non-critical): %s", exc)
    except Exception as exc:
        logger.warning("Neo4j graph write skipped (non-critical): %s", exc)
