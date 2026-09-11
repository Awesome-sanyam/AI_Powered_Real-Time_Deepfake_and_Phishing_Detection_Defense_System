"""
Lip Sync Verifier
=================
Detects audio-visual temporal desynchronisation — a hallmark of deepfakes —
by cross-correlating two signals derived from the same video segment:

  1. Lip aperture time-series  (dlib 68-point shape predictor, landmarks 62 & 66)
  2. Audio RMS energy envelope  (Librosa frame-level RMS)

A cross-correlation peak lag > LIP_SYNC_THRESHOLD_MS (80 ms) indicates that
the audio and video are out of phase, strongly suggesting synthetic manipulation.

Face detection backend priority:
  1. dlib HOG + 68-pt shape predictor (models/shape_predictor_68_face_landmarks.dat)
  2. Graceful degradation to zero-signal (returns 0 delay, not suspicious)

NOTE: MediaPipe ≥ 0.10.30 crashes on macOS arm64 due to a DrishtiMetal bug
      (SIGABRT in TensorsToDetectionsCalculator). dlib is used as the
      stable, CPU-only replacement.

Author: Sanyam Gehlot
"""
from __future__ import annotations

import logging
import os

import cv2
import librosa
import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

LIP_SYNC_THRESHOLD_MS: float = 80.0
FRAME_LENGTH: int = 512
HOP_LENGTH: int = 512

# dlib 68-point model — inner lip landmarks (0-indexed):
#   62 = upper inner lip centre, 66 = lower inner lip centre
_DLIB_UPPER_LIP = 62
_DLIB_LOWER_LIP = 66

_DEFAULT_PREDICTOR_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "models",
    "shape_predictor_68_face_landmarks.dat"
)

# ── dlib import guard ─────────────────────────────────────────────────────────
try:
    import dlib
    _DLIB_AVAILABLE = True
except ImportError:
    _DLIB_AVAILABLE = False
    logger.warning("dlib not installed — LipSyncVerifier will return 0 delay")


def _build_dlib_detectors(predictor_path: str):
    """Build dlib face detector + shape predictor. Returns (detector, predictor) or (None, None)."""
    if not _DLIB_AVAILABLE:
        return None, None
    abs_path = os.path.abspath(predictor_path)
    if not os.path.exists(abs_path):
        logger.warning(
            "dlib shape predictor not found at %s — LipSyncVerifier degraded. "
            "Download: see models/README.md",
            abs_path,
        )
        return None, None
    detector  = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(abs_path)
    return detector, predictor


# ── LipSyncVerifier class ─────────────────────────────────────────────────────

class LipSyncVerifier:
    """
    Cross-modal lip-sync analyser using dlib face landmarks + Librosa RMS.

    Usage:
        verifier = LipSyncVerifier()
        delay_ms, is_suspicious = verifier.verify(frames, audio_bytes, fps=25.0)
    """

    def __init__(
        self,
        threshold_ms: float = LIP_SYNC_THRESHOLD_MS,
        sample_rate: int = 16_000,
        predictor_path: str = _DEFAULT_PREDICTOR_PATH,
    ) -> None:
        self.threshold_ms = threshold_ms
        self.sample_rate = sample_rate
        self._detector, self._predictor = _build_dlib_detectors(predictor_path)

    def extract_lip_aperture(
        self,
        frames: list[np.ndarray],
        fps: float = 25.0,  # noqa: ARG002
    ) -> np.ndarray:
        """
        Extract normalised lip aperture per frame using dlib 68-pt landmarks.

        Landmark 62 (upper inner lip) and 66 (lower inner lip) give the
        vertical distance. Falls back to 0.0 if no face is detected.

        Args:
            frames: List of BGR uint8 np.ndarray video frames.
            fps:    Frames per second (kept for API symmetry).

        Returns:
            1-D float32 np.ndarray of aperture values, one per frame.
        """
        apertures: list[float] = []

        if self._detector is None or self._predictor is None:
            return np.zeros(len(frames), dtype=np.float32)

        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            h = gray.shape[0]
            faces = self._detector(gray, 0)  # 0 = no upsampling (fast)
            if faces:
                shape = self._predictor(gray, faces[0])
                upper = shape.part(_DLIB_UPPER_LIP)
                lower = shape.part(_DLIB_LOWER_LIP)
                # Normalise by frame height
                aperture = abs(lower.y - upper.y) / (h + 1e-8)
                apertures.append(float(aperture))
            else:
                apertures.append(0.0)

        return np.array(apertures, dtype=np.float32)

    def extract_audio_energy(self, audio_bytes: bytes) -> np.ndarray:
        """Extract frame-level RMS energy from raw 16-bit PCM bytes."""
        audio = (
            np.frombuffer(audio_bytes, dtype=np.int16)
            .astype(np.float32) / 32768.0
        )
        rms = librosa.feature.rms(
            y=audio, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH
        )
        return rms[0].astype(np.float32)

    def compute_sync_delay_ms(
        self,
        lip_signal: np.ndarray,
        audio_signal: np.ndarray,
        fps: float,
    ) -> float:
        """Compute the cross-correlation lag between lip and audio signals."""
        n = min(len(lip_signal), len(audio_signal))
        if n < 2:
            return 0.0
        lip   = lip_signal[:n]
        audio = audio_signal[:n]
        lip   = (lip   - lip.mean())   / (lip.std()   + 1e-8)
        audio = (audio - audio.mean()) / (audio.std() + 1e-8)
        correlation = np.correlate(lip, audio, mode="full")
        lag_frames = int(np.argmax(correlation)) - (n - 1)
        return abs(lag_frames) * (1000.0 / fps)

    def verify(
        self,
        frames: list[np.ndarray],
        audio_bytes: bytes,
        fps: float = 25.0,
        sample_rate: int = 16_000,
    ) -> tuple[float, bool]:
        """
        Run the full lip-sync verification pipeline.

        Returns:
            (delay_ms, is_suspicious):
                delay_ms       — computed lag in milliseconds.
                is_suspicious  — True if delay > threshold_ms (80 ms).
        """
        lip_signal   = self.extract_lip_aperture(frames, fps)
        audio_signal = self.extract_audio_energy(audio_bytes)
        delay_ms     = self.compute_sync_delay_ms(lip_signal, audio_signal, fps)
        return delay_ms, delay_ms > self.threshold_ms

    def close(self) -> None:
        """No-op — dlib objects are GC'd automatically."""
        pass


__all__ = ["LipSyncVerifier", "LIP_SYNC_THRESHOLD_MS"]
