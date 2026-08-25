"""
AI Engine FastAPI Microservice
==============================
Exposes HTTP endpoints called by Django Celery tasks.
Runs as a separate process on port 8001.

Start with:
    uvicorn ai_engine.server:app --host 0.0.0.0 --port 8001 --workers 1
"""
import base64
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import cv2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ai_engine.deepfake.cross_modal_engine import CrossModalVerificationEngine, DeepfakeVerdict
from ai_engine.phishing.llm_analyzer import PhishingAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Singleton engine instances (loaded once at startup) ───────────────────────
_deepfake_engine: Optional[CrossModalVerificationEngine] = None
_phishing_engine: Optional[PhishingAnalyzer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _deepfake_engine, _phishing_engine
    logger.info("Loading AI models...")
    _deepfake_engine = CrossModalVerificationEngine(
        ecdsa_private_key_pem=os.environ.get("ECDSA_PRIVATE_KEY_PEM")
    )
    _phishing_engine = PhishingAnalyzer(
        model_path=os.environ.get("GGUF_MODEL_PATH", "models/llama.gguf"),
        ecdsa_service=_deepfake_engine.ecdsa,
    )
    logger.info("✅ All models loaded. AI Engine ready.")
    yield
    _deepfake_engine.cleanup()
    logger.info("AI Engine shut down.")


app = FastAPI(
    title="AI Defence Engine",
    description="Deepfake & Phishing Detection Microservice",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request / Response schemas ────────────────────────────────────────────────

class DeepfakeScanRequest(BaseModel):
    session_id: str
    frames_b64: list[str]       # List of base64-encoded JPEG bytes
    audio_b64: str              # Base64-encoded raw PCM bytes
    fps: float = 25.0
    sample_rate: int = 16000


class PhishingScanRequest(BaseModel):
    session_id: str
    content: str                # Email body or URL to analyse
    headers: Optional[dict] = None
    url: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "engine": "loaded" if _deepfake_engine else "loading"}


@app.post("/scan/deepfake")
async def scan_deepfake(request: DeepfakeScanRequest) -> dict:
    if _deepfake_engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    try:
        # Decode base64 JPEGs → OpenCV BGR frames
        frames: list[np.ndarray] = []
        for b64 in request.frames_b64:
            jpg_bytes = base64.b64decode(b64)
            arr = np.frombuffer(jpg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                frames.append(frame)

        if not frames:
            raise HTTPException(status_code=400, detail="No valid frames decoded")

        audio_bytes = base64.b64decode(request.audio_b64)

        verdict: DeepfakeVerdict = _deepfake_engine.analyze(
            session_id=request.session_id,
            frames=frames,
            audio_bytes=audio_bytes,
            fps=request.fps,
            sample_rate=request.sample_rate,
        )

        return {
            "session_id": verdict.session_id,
            "is_deepfake": verdict.is_deepfake,
            "confidence": verdict.confidence,
            "processing_time_ms": verdict.processing_time_ms,
            "signed_verdict": verdict.signed_verdict,
            "public_key_pem": verdict.public_key_pem,
            "frame_count": len(verdict.frame_results),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/scan/phishing")
async def scan_phishing(request: PhishingScanRequest) -> dict:
    if _phishing_engine is None:
        raise HTTPException(status_code=503, detail="Phishing engine not ready")
    try:
        result = _phishing_engine.analyze(
            session_id=request.session_id,
            content=request.content,
            url=request.url,
            headers=request.headers,
        )
        return result
    except Exception as exc:
        logger.exception("Phishing analysis error")
        raise HTTPException(status_code=500, detail=str(exc))
