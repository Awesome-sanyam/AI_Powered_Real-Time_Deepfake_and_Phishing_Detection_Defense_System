"""
AI Engine FastAPI Microservice
==============================
Exposes HTTP endpoints consumed by the Django Celery task layer.
Runs as an isolated process on port 8001.

Start (from project root):
    uvicorn ai_engine.server:app --host 0.0.0.0 --port 8001 --workers 1 --reload

Endpoints:
    GET  /health          → Device status + model load state
    POST /scan/frame      → Single JPEG/PNG upload → mock artifact score (Phase 1)
    POST /scan/deepfake   → Full cross-modal deepfake analysis (Phase 2+)
    POST /scan/phishing   → LLM phishing analysis (Phase 2+)

Author: Sanyam Gehlot
"""
from __future__ import annotations

import base64
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from ai_engine.config import DEVICE_NAME, IS_MPS, get_device_report
from ai_engine.deepfake.frame_preprocessor import jpeg_bytes_to_bgr, preprocess_frame

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Startup timestamp ────────────────────────────────────────────────────────
_STARTUP_TIME: float = time.time()

# ── Singleton AI engine instances (heavy models — loaded once) ────────────────
_deepfake_engine = None
_phishing_engine = None
_models_loaded: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load AI models at startup, release resources at shutdown.
    Phase 1: loads CrossModalVerificationEngine (may be slow — ~2 GB on MPS).
    """
    global _deepfake_engine, _phishing_engine, _models_loaded

    logger.info(f"AI Engine starting on device: {DEVICE_NAME}")
    logger.info(f"MPS active: {IS_MPS}")

    try:
        from ai_engine.deepfake.cross_modal_engine import CrossModalVerificationEngine
        _deepfake_engine = CrossModalVerificationEngine(
            ecdsa_private_key_pem=os.environ.get("ECDSA_PRIVATE_KEY_PEM") or None,
        )

        from ai_engine.phishing.llm_analyzer import PhishingAnalyzer
        _phishing_engine = PhishingAnalyzer(
            model_path=os.environ.get("GGUF_MODEL_PATH", "models/llama.gguf"),
            ecdsa_service=_deepfake_engine.ecdsa_service,
        )
        _models_loaded = True
        logger.info("✅ All AI models loaded. Engine ready.")
    except Exception as exc:
        logger.warning(f"⚠️  Model load failed (Phase 1 mode — no weights): {exc}")
        _models_loaded = False

    yield  # ← application runs here

    if _deepfake_engine is not None:
        try:
            _deepfake_engine.cleanup()
        except Exception:
            pass
    logger.info("AI Engine shut down cleanly.")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Defence Engine",
    description="Deepfake & Phishing Detection Microservice — Phase 1",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class DeepfakeScanRequest(BaseModel):
    session_id: str
    frames_b64: list[str]       # base64-encoded JPEG bytes per frame
    audio_b64: str              # base64-encoded raw PCM mono bytes
    fps: float = 25.0
    sample_rate: int = 16000


class PhishingScanRequest(BaseModel):
    session_id: str
    content: str
    headers: Optional[dict] = None
    url: Optional[str] = None


# ── GET /health ───────────────────────────────────────────────────────────────

@app.get("/health", summary="System health + device report")
async def health() -> dict:
    """
    Returns:
        - status: "ok" always (if server is reachable)
        - device: active compute device name ("mps", "cuda", "cpu")
        - mps_available: whether Apple Metal is present on this host
        - models_loaded: whether AI engines initialised successfully
        - uptime_seconds: seconds since server start
    """
    report = get_device_report()
    return {
        "status": "ok",
        "models_loaded": _models_loaded,
        "uptime_seconds": round(time.time() - _STARTUP_TIME, 1),
        **report,
    }


# ── POST /scan/frame ─────────────────────────────────────────────────────────

@app.post("/scan/frame", summary="Single-frame artifact score (Phase 1)")
async def scan_frame(file: UploadFile = File(...)) -> dict:
    """
    Accepts a JPEG or PNG image upload.
    Decodes via OpenCV, preprocesses through the MPS pipeline (fp16),
    and returns a mock artifact score.

    In Phase 2, the preprocessed tensor is passed to VisualArtifactDetector.
    In Phase 1, we return a structural mock to validate the pipeline end-to-end.

    Returns:
        JSON with preprocessing metadata and a mock artifact_score [0.0, 1.0].
    """
    # ── Validate content type ──────────────────────────────────────────────────
    content_type = file.content_type or ""
    if content_type not in ("image/jpeg", "image/png", "image/jpg", "application/octet-stream"):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type '{content_type}'. Send image/jpeg or image/png.",
        )

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty file received.")

    # ── Decode JPEG/PNG → OpenCV BGR ──────────────────────────────────────────
    frame = jpeg_bytes_to_bgr(raw_bytes)
    if frame is None:
        raise HTTPException(status_code=422, detail="Could not decode image. Ensure it is a valid JPEG or PNG.")

    h, w = frame.shape[:2]

    # ── Run through MPS preprocessing pipeline ────────────────────────────────
    try:
        tensor = preprocess_frame(frame)  # [1, 3, 224, 224] float32 CPU
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # ── Phase 1 mock score (no model weights loaded yet) ─────────────────────
    # Compute a deterministic mock score from pixel statistics so the
    # response varies by input — useful for integration testing.
    pixel_mean = float(frame.mean()) / 255.0
    mock_artifact_score = round(abs(pixel_mean - 0.5) * 2.0, 4)  # [0, 1]

    return {
        "status": "processed",
        "device": DEVICE_NAME,
        "mps_active": IS_MPS,
        "input_shape": {"height": h, "width": w, "channels": 3},
        "tensor_shape": list(tensor.shape),   # [1, 3, 224, 224]
        "tensor_dtype": str(tensor.dtype),
        "artifact_score": mock_artifact_score,
        "phase": 1,
        "note": "Mock score — Phase 1 skeleton. Real inference activates in Phase 2 with model weights.",
    }


# ── POST /scan/deepfake ───────────────────────────────────────────────────────

@app.post("/scan/deepfake", summary="Full cross-modal deepfake analysis")
async def scan_deepfake(request: DeepfakeScanRequest) -> dict:
    """Full deepfake analysis (Phase 2+). Returns 503 if models are not loaded."""
    if _deepfake_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Deepfake engine not loaded. Ensure model weights are present and Phase 2 is complete.",
        )
    try:
        frames: list[np.ndarray] = []
        for b64 in request.frames_b64:
            frame = jpeg_bytes_to_bgr(base64.b64decode(b64))
            if frame is not None:
                frames.append(frame)

        if not frames:
            raise HTTPException(status_code=400, detail="No valid frames decoded from frames_b64.")

        audio_bytes = base64.b64decode(request.audio_b64)

        verdict = _deepfake_engine.analyze(
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
    except Exception as exc:
        logger.exception("Unexpected error in /scan/deepfake")
        raise HTTPException(status_code=500, detail=str(exc))


# ── POST /scan/phishing ───────────────────────────────────────────────────────

@app.post("/scan/phishing", summary="LLM-powered phishing analysis")
async def scan_phishing(request: PhishingScanRequest) -> dict:
    """Phishing analysis (Phase 2+). Returns 503 if LLM model is not loaded."""
    if _phishing_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Phishing engine not loaded. Ensure GGUF model is present and Phase 2 is complete.",
        )
    try:
        result = _phishing_engine.analyze(
            session_id=request.session_id,
            content=request.content,
            url=request.url,
            headers=request.headers,
        )
        return result
    except Exception as exc:
        logger.exception("Phishing analysis error in /scan/phishing")
        raise HTTPException(status_code=500, detail=str(exc))
