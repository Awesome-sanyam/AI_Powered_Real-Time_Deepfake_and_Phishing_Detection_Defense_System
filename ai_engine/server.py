"""
AI Engine FastAPI Microservice
==============================
Phase 2 — fully wired to real AI detectors.

Endpoints:
    GET  /health          → Device status + model load state
    POST /scan/frame      → Single JPEG/PNG upload → artifact score
    POST /scan/deepfake   → Full cross-modal deepfake analysis (signed)
    POST /scan/phishing   → LLM + heuristic phishing analysis (signed)

Start (from project root):
    uvicorn ai_engine.server:app --host 0.0.0.0 --port 8001 --workers 1

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

_STARTUP_TIME: float = time.time()

# ── Singleton AI engine instances (loaded once at startup) ─────────────────────
_deepfake_engine = None
_phishing_engine = None
_models_loaded: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load AI models at startup, release resources at shutdown.
    Gracefully degrades — server remains reachable even if models fail to load.
    """
    global _deepfake_engine, _phishing_engine, _models_loaded

    logger.info(f"AI Engine starting on device: {DEVICE_NAME}")
    logger.info(f"MPS active: {IS_MPS}")

    try:
        from ai_engine.deepfake.cross_modal_engine import CrossModalVerificationEngine
        _deepfake_engine = CrossModalVerificationEngine(
            ecdsa_private_key_pem=os.environ.get("ECDSA_PRIVATE_KEY_PEM") or None,
        )
        logger.info("✅ CrossModalVerificationEngine loaded")

        from ai_engine.phishing.llm_analyzer import PhishingAnalyzer
        _phishing_engine = PhishingAnalyzer(
            model_path=os.environ.get("GGUF_MODEL_PATH", "models/llama.gguf"),
            ecdsa_service=_deepfake_engine.ecdsa,
        )
        logger.info("✅ PhishingAnalyzer loaded")
        _models_loaded = True

    except Exception as exc:
        logger.warning(f"⚠️  Model load failed (Phase 1 fallback mode): {exc}")
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
    description="Deepfake & Phishing Detection Microservice — Phase 2",
    version="2.0.0",
    lifespan=lifespan,
)


# ── Pydantic request schemas ──────────────────────────────────────────────────

class DeepfakeScanRequest(BaseModel):
    session_id: str
    frames_b64: list[str]       # base64-encoded JPEG bytes per frame
    audio_b64: str              # base64-encoded raw PCM mono bytes
    fps: float = 25.0
    sample_rate: int = 16000


class PhishingScanRequest(BaseModel):
    session_id: str
    content: str                # Email body or any suspicious text
    headers: Optional[dict] = None   # Email headers dict (optional)
    url: Optional[str] = None       # Suspicious URL (optional)


# ── GET /health ───────────────────────────────────────────────────────────────

@app.get("/health", summary="System health + device report")
async def health() -> dict:
    """
    Returns:
        status: "ok" always (if server is reachable)
        device: active compute device ("mps", "cuda", "cpu")
        models_loaded: whether AI engines initialised successfully
        uptime_seconds: seconds since server start
    """
    report = get_device_report()
    return {
        "status": "ok",
        "models_loaded": _models_loaded,
        "uptime_seconds": round(time.time() - _STARTUP_TIME, 1),
        **report,
    }


# ── POST /scan/frame ─────────────────────────────────────────────────────────

@app.post("/scan/frame", summary="Single-frame artifact score")
async def scan_frame(file: UploadFile = File(...)) -> dict:
    """
    Accepts a JPEG or PNG image upload. Decodes via OpenCV, preprocesses
    through the MPS pipeline (fp16), and returns an artifact score.

    Phase 1: Returns a pixel-statistics mock score (deterministic, no model).
    Phase 2: When models are loaded, passes through VisualArtifactDetector.
    """
    content_type = file.content_type or ""
    if content_type not in (
        "image/jpeg", "image/png", "image/jpg", "application/octet-stream"
    ):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type '{content_type}'. Send image/jpeg or image/png.",
        )

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty file received.")

    frame = jpeg_bytes_to_bgr(raw_bytes)
    if frame is None:
        raise HTTPException(
            status_code=422,
            detail="Could not decode image. Ensure it is a valid JPEG or PNG.",
        )

    h, w = frame.shape[:2]

    try:
        tensor = preprocess_frame(frame)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # If visual detector is available, use real inference
    if _deepfake_engine is not None:
        try:
            scores = _deepfake_engine.visual.score_batch([frame])
            artifact_score = round(float(scores[0]), 4)
            phase = 2
            note = "Real MPS inference via VisualArtifactDetector"
        except Exception as exc:
            logger.warning(f"Visual detector fallback: {exc}")
            artifact_score = round(abs(float(frame.mean()) / 255.0 - 0.5) * 2.0, 4)
            phase = 1
            note = "Fallback mock score (model error)"
    else:
        # Phase 1 mock score from pixel statistics
        pixel_mean = float(frame.mean()) / 255.0
        artifact_score = round(abs(pixel_mean - 0.5) * 2.0, 4)
        phase = 1
        note = "Mock score — Phase 1. Real inference activates with model weights."

    return {
        "status": "processed",
        "device": DEVICE_NAME,
        "mps_active": IS_MPS,
        "input_shape": {"height": h, "width": w, "channels": 3},
        "tensor_shape": list(tensor.shape),
        "tensor_dtype": str(tensor.dtype),
        "artifact_score": artifact_score,
        "phase": phase,
        "note": note,
    }


# ── POST /scan/deepfake ───────────────────────────────────────────────────────

@app.post("/scan/deepfake", summary="Full cross-modal deepfake analysis")
async def scan_deepfake(request: DeepfakeScanRequest) -> dict:
    """
    Full cross-modal deepfake analysis using all three detectors:
      1. Visual artifact detection (MobileNetV2, MPS fp16)
      2. Lip-sync delay (MediaPipe + Librosa cross-correlation)
      3. Blink rate anomaly (FaceMesh EAR)

    Verdict is cryptographically signed with ECDSA P-256.

    Returns 503 if models are not loaded (model weights missing).
    """
    if _deepfake_engine is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Deepfake engine not loaded. "
                "Ensure model weights are present and ECDSA key is configured."
            ),
        )

    try:
        # Decode frames from base64
        frames: list[np.ndarray] = []
        for b64 in request.frames_b64:
            frame = jpeg_bytes_to_bgr(base64.b64decode(b64))
            if frame is not None:
                frames.append(frame)

        if not frames:
            raise HTTPException(
                status_code=400,
                detail="No valid frames decoded from frames_b64.",
            )

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
            "confidence": round(verdict.confidence, 4),
            "processing_time_ms": round(verdict.processing_time_ms, 1),
            "frame_count": len(verdict.frame_results),
            "signed_verdict": verdict.signed_verdict,
            "public_key_pem": verdict.public_key_pem,
            "frame_results": [
                {
                    "frame_index": fr.frame_index,
                    "visual_artifact_score": round(fr.visual_artifact_score, 4),
                    "lip_sync_delay_ms": round(fr.lip_sync_delay_ms, 1),
                    "blink_rate_bpm": round(fr.blink_rate_bpm, 1),
                    "is_suspicious": fr.is_suspicious,
                    "confidence": round(fr.confidence, 4),
                }
                for fr in verdict.frame_results
            ],
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in /scan/deepfake")
        raise HTTPException(status_code=500, detail=str(exc))


# ── POST /scan/phishing ───────────────────────────────────────────────────────

@app.post("/scan/phishing", summary="LLM-powered phishing analysis")
async def scan_phishing(request: PhishingScanRequest) -> dict:
    """
    Multi-signal phishing analysis combining:
      1. LLM intent classification (4-bit GGUF LLaMA via llama-cpp-python)
      2. URL forensics (entropy, homoglyph, TLD, brand impersonation)
      3. Email header analysis (SPF, DKIM, DMARC, Reply-To mismatch)

    All signals are aggregated into a weighted confidence score.
    Verdict is cryptographically signed with ECDSA P-256.

    Returns 503 if the phishing engine is not loaded.
    """
    if _phishing_engine is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Phishing engine not loaded. "
                "Ensure GGUF model is present at GGUF_MODEL_PATH."
            ),
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
