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
"""
from __future__ import annotations

import logging

import httpx
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings

from .models import DeepfakeScanSession

logger = logging.getLogger(__name__)

AI_ENGINE_BASE_URL = settings.AI_ENGINE_BASE_URL


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
                    },
                },
            )

        # ── 3. Write to Neo4j Threat Graph (non-blocking, best-effort) ────────
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
    except Exception as exc:
        logger.warning(f"Neo4j graph write skipped (non-critical): {exc}")
