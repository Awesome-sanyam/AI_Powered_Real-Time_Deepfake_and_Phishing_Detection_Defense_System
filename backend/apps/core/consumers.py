"""
Core App — WebSocket Consumers
================================
AlertFeedConsumer: broadcasts real-time threat alerts to all connected
Frontend SOC dashboard clients.

Group "alert_feed" — any backend service can publish to this group via
channel_layer.group_send() to push instant alerts to all dashboard tabs.

Message format sent to clients:
    {
        "type":      "threat.alert",
        "title":     "Deepfake Detected",
        "message":   "Session abc-123 classified as FAKE (confidence 0.78)",
        "alert_type": "deepfake" | "phishing" | "identity" | "info",
        "timestamp": "2026-08-26T12:00:00Z",
        "session_id": "abc-123"
    }

Author: Sanyam Gehlot
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

ALERT_GROUP = "alert_feed"


class AlertFeedConsumer(AsyncWebsocketConsumer):
    """
    Broadcasts real-time threat alerts to the Frontend SOC dashboard clients.

    All connected dashboard clients subscribe to the 'alert_feed' group.
    Alerts are published by Celery tasks after AI verdict delivery.
    """

    async def connect(self) -> None:
        await self.channel_layer.group_add(ALERT_GROUP, self.channel_name)
        await self.accept()
        # Send a welcome ping so the client knows the feed is live
        await self.send(text_data=json.dumps({
            "type": "connection.established",
            "message": "Alert feed connected",
            "timestamp": _now_iso(),
        }))
        logger.info(f"Alert feed client connected: {self.channel_name}")

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(ALERT_GROUP, self.channel_name)
        logger.info(f"Alert feed client disconnected: {self.channel_name} code={close_code}")

    async def receive(self, text_data: str = None, bytes_data: bytes = None) -> None:
        """
        Clients can send a ping to keep the connection alive.
        Any other messages are silently ignored (read-only feed).
        """
        if text_data:
            try:
                msg = json.loads(text_data)
                if msg.get("type") == "ping":
                    await self.send(text_data=json.dumps({
                        "type": "pong",
                        "timestamp": _now_iso(),
                    }))
            except json.JSONDecodeError:
                pass

    # ── Channel layer message handlers ────────────────────────────────────────

    async def threat_alert(self, event: dict) -> None:
        """
        Handler for channel layer messages of type 'threat.alert'.
        Called when Celery tasks broadcast to the alert_feed group.
        """
        await self.send(text_data=json.dumps({
            "type":       event.get("alert_type", "info"),
            "title":      event.get("title", "Alert"),
            "message":    event.get("message", ""),
            "timestamp":  event.get("timestamp", _now_iso()),
            "session_id": event.get("session_id", ""),
        }))

    async def connection_established(self, event: dict) -> None:
        """Forward connection status messages."""
        await self.send(text_data=json.dumps(event))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
