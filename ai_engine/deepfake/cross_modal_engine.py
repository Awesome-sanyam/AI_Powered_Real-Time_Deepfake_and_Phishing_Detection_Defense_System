"""
AI Engine — Cross-Modal Verification Engine
============================================
Detects deepfakes by analysing the temporal coherence between:
  1. Visual artifacts   (MobileNetV2 on MPS/CUDA, fp16, batch_size=4)
  2. Lip-sync delay     (MediaPipe FaceLandmarker Tasks API + Librosa cross-correlation)
  3. Blink rate anomaly (Eye Aspect Ratio via FaceLandmarker Tasks API)
  4. Audio anomaly      (Librosa MFCC + RMS — silence ratio, flat energy profile)

All verdicts are cryptographically signed via ECDSA P-256.

NOTE: MediaPipe ≥ 0.10.21 removed mp.solutions. All face detection now uses
      the Tasks API (mp.tasks.vision.FaceLandmarker) with the model bundle at
      models/face_landmarker.task.

Hardware target: Apple Silicon M4 — uses torch.device("mps") with CPU fallback.
Memory budget  : ≤ 2 GB peak (batch_size=4, fp16 inference).
"""
from __future__ import annotations

import gc
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import torch

from ai_engine.identity.ecdsa_service import ECDSAService
from ai_engine.deepfake.visual_detector import VisualArtifactDetector
from ai_engine.deepfake.lip_sync_verifier import LipSyncVerifier
from ai_engine.deepfake.blink_detector import BlinkRateDetector
from ai_engine.deepfake.audio_analyzer import AudioAnalyzer

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Device Resolution — MPS → CUDA → CPU
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_device() -> torch.device:
    """Select the best available compute device."""
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        logger.info("✅ MPS device — Apple Metal GPU")
        return torch.device("mps")
    elif torch.cuda.is_available():
        logger.info("✅ CUDA device available")
        return torch.device("cuda")
    else:
        logger.warning("⚠️  CPU fallback — MPS unavailable")
        return torch.device("cpu")


DEVICE: torch.device = _resolve_device()


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FrameAnalysisResult:
    """Per-frame analysis result."""
    frame_index: int
    visual_artifact_score: float    # 0.0 (real) → 1.0 (fake)
    lip_sync_delay_ms: float        # >80ms = suspicious
    blink_rate_bpm: float           # <8 or >30 = suspicious
    is_suspicious: bool
    confidence: float               # aggregated [0, 1]


@dataclass
class DeepfakeVerdict:
    """Final verdict for a video segment."""
    session_id: str
    is_deepfake: bool
    confidence: float
    frame_results: list[FrameAnalysisResult] = field(default_factory=list)
    processing_time_ms: float = 0.0
    signed_verdict: Optional[str] = None    # ECDSA hex signature
    public_key_pem: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Cross-Modal Verification Engine (Orchestrator)
# ─────────────────────────────────────────────────────────────────────────────

class CrossModalVerificationEngine:
    """
    Orchestrates all four deepfake detection signal streams and aggregates
    them into a weighted confidence score with an ECDSA-signed verdict.

    Signal weights:
        Visual artifact score  : 0.40  (MobileNetV2 ImageNet backbone, fp16 MPS)
        Lip-sync delay         : 0.30  (FaceLandmarker + Librosa cross-correlation)
        Blink rate anomaly     : 0.20  (FaceLandmarker EAR blink counter)
        Audio anomaly          : 0.10  (Librosa MFCC silence/flatness heuristic)

    Usage:
        engine = CrossModalVerificationEngine()
        verdict = engine.analyze(
            session_id="abc-123",
            frames=frame_list,      # list of BGR np.ndarray
            audio_bytes=raw_audio,  # raw 16-bit PCM mono bytes
            fps=25.0,
        )
        engine.cleanup()            # call on shutdown
    """

    WEIGHTS: dict[str, float] = {
        "visual":    0.40,
        "lip_sync":  0.30,
        "blink":     0.20,
        "audio":     0.10,
    }
    FAKE_THRESHOLD: float = 0.55

    def __init__(
        self,
        visual_weights_path: Optional[str] = None,
        ecdsa_private_key_pem: Optional[str] = None,
    ) -> None:
        # Visual model (MobileNetV2 on MPS/CUDA)
        self.visual = VisualArtifactDetector(visual_weights_path)

        # FaceLandmarker-based detectors — each manages its own model instance
        # (avoids VIDEO-mode timestamp conflict when using a shared landmarker)
        self.lip_sync = LipSyncVerifier()
        self.blink    = BlinkRateDetector()

        # Audio feature extractor (pure-CPU, librosa)
        self.audio_analyzer = AudioAnalyzer()

        # ECDSA signing service
        self.ecdsa = ECDSAService(private_key_pem=ecdsa_private_key_pem)

        logger.info("CrossModalVerificationEngine ready on %s", DEVICE)

    def _confidence(
        self,
        visual_score: float,
        lip_sus: bool,
        blink_sus: bool,
        audio_anomalous: bool,
    ) -> float:
        """Compute weighted deepfake confidence in [0, 1]."""
        return float(np.clip(
            self.WEIGHTS["visual"]   * visual_score
            + self.WEIGHTS["lip_sync"] * (1.0 if lip_sus else 0.0)
            + self.WEIGHTS["blink"]    * (1.0 if blink_sus else 0.0)
            + self.WEIGHTS["audio"]    * (1.0 if audio_anomalous else 0.0),
            0.0, 1.0,
        ))

    def analyze(
        self,
        session_id: str,
        frames: list,
        audio_bytes: bytes,
        fps: float = 25.0,
        sample_rate: int = 16000,
    ) -> DeepfakeVerdict:
        """
        Run full cross-modal deepfake analysis on a video segment.

        Args:
            session_id:   Unique identifier for this scan session.
            frames:       List of BGR OpenCV frames (np.ndarray).
            audio_bytes:  Raw 16-bit PCM mono audio bytes.
            fps:          Frames per second of the video stream.
            sample_rate:  Audio sample rate in Hz.

        Returns:
            DeepfakeVerdict with ECDSA-signed result.
        """
        if not frames:
            raise ValueError("frames cannot be empty")

        t0 = time.perf_counter()

        # 1. Visual artifact detection (MobileNetV2 on MPS)
        scores = self.visual.score_batch(frames)
        mean_score = float(np.mean(scores))

        # 2. Lip-sync delay analysis (FaceLandmarker VIDEO mode)
        lip_delay, lip_sus = self.lip_sync.verify(frames, audio_bytes, fps, sample_rate)

        # 3. Blink rate analysis (FaceLandmarker VIDEO mode — separate instance)
        blink_bpm, blink_sus = self.blink.compute_blink_rate(frames, fps)

        # 4. Audio anomaly detection (MFCC silence + flat energy)
        audio_report = self.audio_analyzer.detect_anomaly(audio_bytes)
        audio_anomalous = audio_report.get("is_anomalous", False)

        # 5. Confidence aggregation
        conf = self._confidence(mean_score, lip_sus, blink_sus, audio_anomalous)
        is_fake = conf >= self.FAKE_THRESHOLD

        # 6. ECDSA signing
        payload = (
            f"{session_id}|deepfake={is_fake}|"
            f"confidence={conf:.4f}|ts={int(time.time())}"
        )
        sig, pubkey = self.ecdsa.sign(payload)

        # 7. Memory cleanup
        if DEVICE.type == "mps":
            torch.mps.empty_cache()
        gc.collect()

        return DeepfakeVerdict(
            session_id=session_id,
            is_deepfake=is_fake,
            confidence=conf,
            frame_results=[
                FrameAnalysisResult(
                    frame_index=i,
                    visual_artifact_score=scores[i],
                    lip_sync_delay_ms=lip_delay,
                    blink_rate_bpm=blink_bpm,
                    is_suspicious=(scores[i] > 0.5 or lip_sus or blink_sus),
                    confidence=self._confidence(scores[i], lip_sus, blink_sus, audio_anomalous),
                )
                for i in range(len(frames))
            ],
            processing_time_ms=(time.perf_counter() - t0) * 1000,
            signed_verdict=sig,
            public_key_pem=pubkey,
        )

    def cleanup(self) -> None:
        """Release all GPU/MPS resources. Called by FastAPI lifespan on shutdown."""
        try:
            self.visual.model.cpu()
        except Exception:
            pass
        del self.visual

        self.lip_sync.close()
        self.blink.close()

        if DEVICE.type == "mps":
            torch.mps.empty_cache()
        gc.collect()
        logger.info("CrossModalVerificationEngine resources released.")
