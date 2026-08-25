"""
DeepfakeStreamConsumer
======================
Accepts a binary WebSocket stream of JPEG frames + PCM audio chunks from the
Flutter dashboard, dispatches them to the Celery AI task queue, and pushes
signed verdict JSON back to the client in real time.

Message protocol (client → server):
  Binary: raw JPEG bytes
  Text:   JSON {"type": "audio_chunk", "data": "<base64 PCM>", "fps": 25.0}

Message protocol (server → client):
  Text: JSON {"type": "verdict", "session_id": "...", "is_deepfake": bool,
              "confidence": 0.0, "signed_verdict": "...", "processing_ms": 0.0}
"""
import base64
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from .tasks import analyze_deepfake_async

logger = logging.getLogger(__name__)

FRAME_BUFFER_SIZE = 25   # Accumulate 1 second of frames before dispatching


class DeepfakeStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self) -> None:
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = f"deepfake_{self.session_id}"
        self._frame_buffer: list[bytes] = []
        self._audio_buffer: bytes = b""
        self._fps: float = 25.0

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"WS connected: session={self.session_id}")

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"WS disconnected: session={self.session_id} code={close_code}")

    async def receive(self, text_data: str = None, bytes_data: bytes = None) -> None:
        if bytes_data:
            # Binary frame (JPEG)
            self._frame_buffer.append(bytes_data)
            if len(self._frame_buffer) >= FRAME_BUFFER_SIZE:
                await self._dispatch_analysis()

        elif text_data:
            payload = json.loads(text_data)
            if payload.get("type") == "audio_chunk":
                self._audio_buffer += base64.b64decode(payload["data"])
                self._fps = float(payload.get("fps", 25.0))
            elif payload.get("type") == "flush":
                # Force analysis of remaining buffered frames
                if self._frame_buffer:
                    await self._dispatch_analysis()

    async def _dispatch_analysis(self) -> None:
        """Send buffered frames + audio to Celery for AI analysis."""
        frames_b64 = [base64.b64encode(f).decode() for f in self._frame_buffer]
        audio_b64 = base64.b64encode(self._audio_buffer).decode()

        analyze_deepfake_async.delay(
            session_id=self.session_id,
            channel_name=self.channel_name,
            frames_b64=frames_b64,
            audio_b64=audio_b64,
            fps=self._fps,
        )
        self._frame_buffer.clear()
        self._audio_buffer = b""

    async def deepfake_verdict(self, event: dict) -> None:
        """Push verdict from Celery task back to the WebSocket client."""
        await self.send(text_data=json.dumps(event["verdict"]))
