"""Phishing app Celery tasks."""
import logging

import httpx
from celery import shared_task
from django.conf import settings

from .models import PhishingScan
from apps.core.utils import sha256_hex

logger = logging.getLogger(__name__)

AI_ENGINE_BASE_URL = settings.AI_ENGINE_BASE_URL


@shared_task(bind=True, max_retries=2, default_retry_delay=1)
def analyze_phishing_async(
    self,
    session_id: str,
    content: str,
    url: str = "",
    headers: dict | None = None,
) -> None:
    """
    Celery task: sends content to the AI Engine phishing endpoint,
    then persists the result to PhishingScan.
    """
    try:
        payload = {
            "session_id": session_id,
            "content": content,
            "url": url or None,
            "headers": headers,
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{AI_ENGINE_BASE_URL}/scan/phishing",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        PhishingScan.objects.create(
            session_id=session_id,
            content_hash=sha256_hex(content),
            is_phishing=result.get("is_phishing"),
            confidence=result.get("confidence"),
            risk_level=result.get("risk_level", ""),
            signals=result.get("signals", []),
            explanation=result.get("explanation", ""),
            url=url or "",
            signed_verdict=result.get("signed_verdict", ""),
            public_key_pem=result.get("public_key_pem", ""),
            processing_time_ms=result.get("processing_time_ms"),
        )
        logger.info(f"Phishing scan saved: session={session_id} is_phishing={result.get('is_phishing')}")

    except httpx.HTTPError as exc:
        logger.error(f"AI Engine HTTP error (phishing): {exc}")
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception(f"Unexpected error in analyze_phishing_async: {exc}")
        raise
