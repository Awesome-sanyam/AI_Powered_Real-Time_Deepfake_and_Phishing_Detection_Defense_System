"""
Celery tasks for the deepfake app.
Calls the AI Engine FastAPI microservice and pushes verdicts via Channels.
"""
import logging

import httpx
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings

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
    Celery task: forwards frame + audio data to the AI Engine
    and pushes the signed verdict back over the WebSocket channel.
    """
    try:
        payload = {
            "session_id": session_id,
            "frames_b64": frames_b64,
            "audio_b64": audio_b64,
            "fps": fps,
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{AI_ENGINE_BASE_URL}/scan/deepfake",
                json=payload,
            )
            response.raise_for_status()
            verdict = response.json()

        # Push verdict back to WebSocket via channel layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.send)(
            channel_name,
            {
                "type": "deepfake_verdict",
                "verdict": {
                    "type": "verdict",
                    "session_id": verdict["session_id"],
                    "is_deepfake": verdict["is_deepfake"],
                    "confidence": verdict["confidence"],
                    "processing_ms": verdict["processing_time_ms"],
                    "signed_verdict": verdict.get("signed_verdict"),
                    "public_key_pem": verdict.get("public_key_pem"),
                },
            },
        )
    except httpx.HTTPError as exc:
        logger.error(f"AI Engine HTTP error: {exc}")
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception(f"Unexpected error in analyze_deepfake_async: {exc}")
        raise
