"""
DeepfakeStreamConsumer
======================
Accepts a binary WebSocket stream of JPEG frames + PCM audio chunks from the
Frontend JS clients, dispatches them to the Celery AI task queue, and pushes
signed verdict JSON back to the client in real time.

Message protocol (client → server):
  Text: JSON {"type": "video_frame", "data": "<base64 JPEG>", "fps": 12.0, "ts": 0}
  Text: JSON {"type": "audio_chunk", "data": "<base64 PCM>", "sample_rate": 16000}
  Text: JSON {"type": "flush"}      — force analysis of remaining buffered frames
  Text: JSON {"type": "ping", "ts": 0}  — heartbeat from SOCWebSocketClient

Message protocol (server → client):
  Text: JSON {"type": "connection.established", "session_id": "..."}
  Text: JSON {"type": "pong", "ts": 0}
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
        self._frame_buffer: list[str] = []   # list of base64 JPEG strings
        self._audio_buffer: bytes = b""
        self._fps: float = 12.0

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Immediately reply so SOCWebSocketClient resets its missed-pong counter
        await self.send(text_data=json.dumps({
            "type": "connection.established",
            "session_id": self.session_id,
        }))
        logger.info("WS connected: session=%s", self.session_id)

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info("WS disconnected: session=%s code=%s", self.session_id, close_code)

    async def receive(self, text_data: str = None, bytes_data: bytes = None) -> None:
        if text_data:
            payload = json.loads(text_data)
            p_type = payload.get("type")

            if p_type == "video_frame":
                raw_b64 = payload.get("data", "")
                if raw_b64:
                    self._frame_buffer.append(raw_b64)
                    self._fps = float(payload.get("fps", self._fps))
                if len(self._frame_buffer) >= FRAME_BUFFER_SIZE:
                    await self._dispatch_analysis()

            elif p_type == "audio_chunk":
                raw_b64 = payload.get("data", "")
                if raw_b64:
                    try:
                        self._audio_buffer += base64.b64decode(raw_b64)
                    except Exception as exc:
                        logger.warning("Audio decode error: %s", exc)

            elif p_type == "ping":
                await self.send(text_data=json.dumps({
                    "type": "pong",
                    "ts": payload.get("ts", 0),
                }))

            elif p_type == "flush":
                if self._frame_buffer or self._audio_buffer:
                    await self._dispatch_analysis()

    async def _dispatch_analysis(self) -> None:
        """Send buffered frames + audio to Celery for AI analysis."""
        if not self._frame_buffer:
            return
        n_frames = len(self._frame_buffer)
        audio_b64 = base64.b64encode(self._audio_buffer).decode() if self._audio_buffer else ""

        analyze_deepfake_async.delay(
            session_id=self.session_id,
            channel_name=self.channel_name,
            frames_b64=list(self._frame_buffer),
            audio_b64=audio_b64,
            fps=self._fps,
        )
        logger.debug("Dispatched %d frames to Celery: session=%s", n_frames, self.session_id)
        self._frame_buffer.clear()
        self._audio_buffer = b""

    async def deepfake_verdict(self, event: dict) -> None:
        """Push verdict from Celery task back to the WebSocket client."""
        await self.send(text_data=json.dumps(event["verdict"]))
