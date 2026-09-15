"""
AI Engine — Cross-Modal Verification Engine
============================================
Detects deepfakes by analysing the temporal coherence between:
  1. Visual artifacts   (MobileNetV2 + Laplacian spatial-frequency + face cropping)
  2. Lip-sync delay     (dlib 68-pt landmarks + Librosa RMS cross-correlation)
  3. Blink rate anomaly (dlib 68-pt EAR blink counter)
  4. Audio anomaly      (Librosa MFCC + RMS — silence ratio, flat energy profile)

All verdicts are cryptographically signed via ECDSA P-256.

CALIBRATION (v3 — Face-Crop + Override Edition):
  Visual detector now runs on cropped faces instead of whole frames.
  This prevents GAN blending artefacts from being diluted by background pixels.

  Override Trigger (new in v3):
    If visual_score > VISUAL_OVERRIDE_THRESHOLD (0.85), the overall confidence
    is raised to at least VISUAL_OVERRIDE_FLOOR (0.80), regardless of how
    perfect the lip-sync or blink rate appear.

    Rationale: High-quality face-swap deepfakes often have perfect temporal
    consistency (seamless lip-sync, normal blink rate). Without this override,
    a MobileNetV2 high-confidence detection on a cropped face gets diluted to
    ~0.38 (= 0.85 × 0.45 weight). The override ensures a strong visual signal
    cannot be outvoted by temporal signals.

  Calibrated Signal Weights (v3):
    visual:   0.45  — MobileNetV2 + Laplacian (now on cropped faces)
    lip_sync: 0.35  — dlib + Librosa 160ms threshold
    blink:    0.20  — dlib EAR, min 300-frame guard

  FAKE_THRESHOLD:
    0.72 — unchanged. Override acts independently before threshold check.

NOTE: MediaPipe ≥ 0.10.21 removed mp.solutions. All face detection now uses
      dlib HOG + 68-pt shape predictor (CPU-only, stable on macOS arm64).
      MediaPipe FaceDetection is used ONLY in visual_detector for cropping
      and is accessed through a separate mp.solutions.face_detection path.

Hardware target: Apple Silicon M4 — uses torch.device("mps") with CPU fallback.
Memory budget  : ≤ 2 GB peak (batch_size=4, fp16 inference).

Author: Sanyam Gehlot & Alefiya
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
from ai_engine.deepfake.visual_detector import (
    VisualArtifactDetector,
    FACE_OVERRIDE_THRESHOLD,
    FACE_OVERRIDE_FLOOR,
)
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
# Override constants — re-exported from visual_detector for centralised access
# ─────────────────────────────────────────────────────────────────────────────

# If the mean visual score across frames exceeds this, apply the override.
_VISUAL_OVERRIDE_THRESHOLD: float = FACE_OVERRIDE_THRESHOLD   # 0.85
# The overall confidence will be raised to at least this floor when triggered.
_VISUAL_OVERRIDE_FLOOR: float     = 0.80   # Set at 0.80 — clear "deepfake" signal


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FrameAnalysisResult:
    """Per-frame analysis result."""
    frame_index: int
    visual_artifact_score: float    # 0.0 (real) → 1.0 (fake)
    lip_sync_delay_ms: float        # >160ms = suspicious (v2 calibrated)
    blink_rate_bpm: float           # <8 or >30 = suspicious (if sample is long enough)
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
    # v3 metadata fields
    visual_override_triggered: bool = False
    mean_visual_score: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Cross-Modal Verification Engine (Orchestrator)
# ─────────────────────────────────────────────────────────────────────────────

class CrossModalVerificationEngine:
    """
    Orchestrates all four deepfake detection signal streams and aggregates
    them into a weighted confidence score with an ECDSA-signed verdict.

    v3 Changes (False Negative Fix):
    ─────────────────────────────────
    1. Visual detector now crops faces before MobileNetV2 inference.
       This forces the model to examine GAN blending/texture artefacts
       rather than background pixels that dilute the signal.

    2. Override Trigger:
       If mean_visual_score > 0.85, overall_confidence is raised to at
       least 0.80, regardless of how clean the lip-sync and blink rate are.
       This catches high-quality face-swap deepfakes that defeat temporal
       analysis by being perfectly consistent.

    Calibrated Signal Weights (v3):
        Visual artifact score  : 0.45  (now on cropped faces)
        Lip-sync delay         : 0.35  (dlib + Librosa, 160ms threshold)
        Blink rate anomaly     : 0.20  (dlib EAR, min 300-frame guard)

    Fake Threshold (v3):
        0.72 — unchanged. Override acts independently and can bypass this.

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
        "visual":    0.45,   # MobileNetV2 + Laplacian spatial-frequency (calibrated, face-crop)
        "lip_sync":  0.35,   # dlib + Librosa cross-correlation (>160ms = suspicious)
        "blink":     0.20,   # dlib EAR blink counter (requires ≥300 frames)
    }
    FAKE_THRESHOLD: float = 0.72          # Requires genuine multi-signal convergence
    LIP_SYNC_THRESHOLD_MS: float = 160.0  # Updated to match LipSyncVerifier v2

    def __init__(
        self,
        visual_weights_path: Optional[str] = None,
        ecdsa_private_key_pem: Optional[str] = None,
    ) -> None:
        # Visual model (MobileNetV2 + Laplacian on MPS/CUDA, face-crop v3)
        self.visual = VisualArtifactDetector(visual_weights_path)

        # FaceLandmarker-based detectors — each manages its own model instance
        self.lip_sync = LipSyncVerifier()
        self.blink    = BlinkRateDetector()

        # Audio feature extractor (pure-CPU, librosa)
        self.audio_analyzer = AudioAnalyzer()

        # ECDSA signing service
        self.ecdsa = ECDSAService(private_key_pem=ecdsa_private_key_pem)

        logger.info("CrossModalVerificationEngine v3 (face-crop + override) ready on %s", DEVICE)

    def _confidence(
        self,
        visual_score: float,
        lip_sus: bool,
        blink_sus: bool,
    ) -> float:
        """
        Compute weighted deepfake confidence in [0, 1].

        Uses calibrated weights:
            visual:   0.45
            lip_sync: 0.35
            blink:    0.20

        Both lip_sus and blink_sus are boolean signals — they contribute their
        full weight only when flagged.

        For a genuine webcam stream with calibrated visual scores (~0.05-0.15),
        no lip desync, and no blink anomaly, confidence ≈ 0.02–0.07 < 0.72.
        """
        return float(np.clip(
            self.WEIGHTS["visual"]   * visual_score
            + self.WEIGHTS["lip_sync"] * (1.0 if lip_sus else 0.0)
            + self.WEIGHTS["blink"]    * (1.0 if blink_sus else 0.0),
            0.0, 1.0,
        ))

    def _apply_visual_override(self, conf: float, visual_score: float) -> tuple[float, bool]:
        """
        Apply the visual override trigger.

        If the mean visual score exceeds _VISUAL_OVERRIDE_THRESHOLD (0.85),
        the confidence is raised to at least _VISUAL_OVERRIDE_FLOOR (0.80).

        This prevents high-quality face-swap deepfakes from being cleared by
        perfect temporal consistency (lip-sync, blink rate).

        Args:
            conf:         Weighted confidence before override.
            visual_score: Mean visual artifact score across all frames.

        Returns:
            (final_confidence, override_triggered)
        """
        if visual_score >= _VISUAL_OVERRIDE_THRESHOLD:
            override_conf = max(conf, _VISUAL_OVERRIDE_FLOOR)
            logger.warning(
                "🚨 Visual override triggered: visual_score=%.3f (≥%.2f) "
                "→ confidence raised %.3f → %.3f",
                visual_score, _VISUAL_OVERRIDE_THRESHOLD, conf, override_conf,
            )
            return override_conf, True
        return conf, False

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

        # 1. Visual artifact detection (MobileNetV2 + Laplacian on CROPPED FACES)
        scores = self.visual.score_batch(frames)
        mean_score = float(np.mean(scores)) if scores else 0.0

        # 2. Lip-sync delay analysis (dlib + Librosa, 160ms threshold)
        lip_delay, lip_sus = self.lip_sync.verify(frames, audio_bytes, fps, sample_rate)

        # 3. Blink rate analysis (dlib EAR — with 300-frame minimum guard)
        blink_bpm, blink_sus = self.blink.compute_blink_rate(frames, fps)

        # 4. Audio anomaly detection (advisory signal — not in primary weights)
        audio_report = self.audio_analyzer.detect_anomaly(audio_bytes)
        _ = audio_report.get("is_anomalous", False)  # advisory only; weights removed

        # 5. Confidence aggregation (weighted blend)
        conf = self._confidence(mean_score, lip_sus, blink_sus)

        # 6. Visual Override Trigger (v3 — False Negative Fix)
        #    If the cropped-face visual score is very high, a perfect lip-sync
        #    or normal blink rate cannot pull the verdict back to "genuine".
        conf, override_triggered = self._apply_visual_override(conf, mean_score)

        is_fake = conf >= self.FAKE_THRESHOLD

        logger.info(
            "Deepfake analysis [%s]: visual=%.3f lip_sus=%s blink_sus=%s "
            "conf=%.4f override=%s fake=%s threshold=%.2f",
            session_id, mean_score, lip_sus, blink_sus,
            conf, override_triggered, is_fake, self.FAKE_THRESHOLD
        )

        # 7. ECDSA signing
        payload = (
            f"{session_id}|deepfake={is_fake}|"
            f"confidence={conf:.4f}|ts={int(time.time())}"
        )
        sig, pubkey = self.ecdsa.sign(payload)

        # 8. Memory cleanup (face-crop routine releases intermediates via gc;
        #    explicit MPS empty_cache called here as final sweep)
        if DEVICE.type == "mps":
            torch.mps.empty_cache()
        gc.collect()

        # Build frame-level results using calibrated per-frame visual scores
        frame_results = []
        for i in range(len(frames)):
            frame_visual = scores[i] if i < len(scores) else 0.0
            frame_conf = self._confidence(frame_visual, lip_sus, blink_sus)
            # Also apply per-frame override
            frame_conf, _ = self._apply_visual_override(frame_conf, frame_visual)
            frame_suspicious = (
                (frame_visual > 0.3)
                or lip_sus
                or blink_sus
            )
            frame_results.append(FrameAnalysisResult(
                frame_index=i,
                visual_artifact_score=frame_visual,
                lip_sync_delay_ms=lip_delay,
                blink_rate_bpm=blink_bpm,
                is_suspicious=frame_suspicious,
                confidence=frame_conf,
            ))

        return DeepfakeVerdict(
            session_id=session_id,
            is_deepfake=is_fake,
            confidence=conf,
            frame_results=frame_results,
            processing_time_ms=(time.perf_counter() - t0) * 1000,
            signed_verdict=sig,
            public_key_pem=pubkey,
            visual_override_triggered=override_triggered,
            mean_visual_score=mean_score,
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
