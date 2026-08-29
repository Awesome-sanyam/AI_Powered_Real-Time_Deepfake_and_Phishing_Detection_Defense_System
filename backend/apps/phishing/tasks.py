"""
Phishing App — Celery Tasks
============================
Phase 2: Calls the AI Engine phishing endpoint, persists results in PostgreSQL,
and writes a threat topology into Neo4j:

  Node types:
    (:Email  {id, hash})            — the scanned email/content
    (:Domain {name, risk_score})    — extracted URL domain
    (:IP     {address, risk_score}) — any IP-address-as-hostname found

  Relationships:
    (Email)-[:CONTAINS_URL]->(Domain)
    (Domain)-[:ORIGINATED_FROM]->(IP)   [when IP hostname detected]

Neo4j writes are best-effort and never block the task from completing.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

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
    Celery task: send content to the AI Engine phishing endpoint,
    persist the result to PostgreSQL, and write threat nodes to Neo4j.

    Args:
        session_id: Unique identifier for this phishing scan.
        content:    Email body / suspicious message text.
        url:        Optional suspicious URL to analyse.
        headers:    Optional dict of email headers for SPF/DKIM checks.
    """
    try:
        payload = {
            "session_id": session_id,
            "content": content,
            "url": url or None,
            "headers": headers,
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{AI_ENGINE_BASE_URL}/scan/phishing",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        # ── 1. Persist to PostgreSQL ───────────────────────────────────────────
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
        logger.info(
            "Phishing scan saved: session=%s is_phishing=%s conf=%.3f",
            session_id,
            result.get("is_phishing"),
            result.get("confidence", 0.0),
        )

        # ── 2. Write threat topology to Neo4j (best-effort) ───────────────────
        if result.get("is_phishing"):
            _write_phishing_to_graph(
                session_id=session_id,
                url=url,
                confidence=result.get("confidence", 0.0),
                signals=result.get("signals", []),
            )

    except httpx.HTTPError as exc:
        logger.error(f"AI Engine HTTP error (phishing): {exc}")
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception(f"Unexpected error in analyze_phishing_async: {exc}")
        raise


def _write_phishing_to_graph(
    session_id: str,
    url: str,
    confidence: float,
    signals: list[str],
) -> None:
    """
    Write phishing scan topology to Neo4j.

    Graph structure:
        (:Email {id: session_id}) -[:CONTAINS_URL]-> (:Domain {name: domain})
        (:Domain) -[:ORIGINATED_FROM]-> (:IP {address}) [if IP hostname]

    Gracefully no-ops if Neo4j is offline.
    """
    try:
        from apps.threat_graph.graph_client import (
            create_relationship,
            upsert_threat_node,
        )

        # Create Email node representing this scan session
        upsert_threat_node(
            node_type="email",
            label=session_id,
            risk_score=confidence,
            metadata={"signals": ",".join(signals[:10])},  # truncate for storage
        )

        if not url:
            return

        # Parse domain from URL
        try:
            parsed = urlparse(url if "://" in url else f"https://{url}")
            domain = parsed.hostname or url
        except Exception:
            domain = url

        # Create Domain node
        upsert_threat_node(
            node_type="domain",
            label=domain,
            risk_score=confidence,
        )

        # Email -[:CONTAINS_URL]-> Domain
        create_relationship(
            from_label=session_id,
            from_type="email",
            rel_type="CONTAINS_URL",
            to_label=domain,
            to_type="domain",
            properties={"confidence": confidence},
        )

        # If IP address used as hostname, create IP node and link it
        import re
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", domain):
            upsert_threat_node(
                node_type="ip",
                label=domain,
                risk_score=confidence,
            )
            create_relationship(
                from_label=domain,
                from_type="domain",
                rel_type="ORIGINATED_FROM",
                to_label=domain,
                to_type="ip",
            )

        logger.info(
            "Neo4j threat graph updated: session=%s domain=%s", session_id, domain
        )

    except Exception as exc:
        logger.warning(f"Neo4j graph write skipped (non-critical): {exc}")
