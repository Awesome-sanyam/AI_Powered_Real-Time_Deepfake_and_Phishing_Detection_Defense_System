"""
Blink Rate Detector
===================
Calculates per-video blink rate in beats per minute (BPM) using dlib's
68-point face landmark predictor with Eye Aspect Ratio (EAR).

Abnormal blink rates are a reliable deepfake signal:
  - Too slow (< 8 BPM): Deepfakes often omit blink synthesis
  - Too fast (> 30 BPM): GAN artefact from temporal instability

Algorithm:
  EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
  where p1–p6 are six eye landmarks from dlib's 68-pt model.

  A blink is counted when EAR drops below EAR_THRESHOLD for one or more
  consecutive frames and then recovers above it.

dlib 68-pt right eye landmarks:
  36=outer, 37=top-outer, 38=top-inner, 39=inner, 40=bot-inner, 41=bot-outer

Face detection backend priority:
  1. dlib HOG + 68-pt shape predictor (models/shape_predictor_68_face_landmarks.dat)
  2. Graceful degradation to 0 BPM + suspicious=True

NOTE: MediaPipe ≥ 0.10.30 crashes on macOS arm64 (DrishtiMetal SIGABRT).
      dlib is used as the stable CPU-only replacement.

Author: Sanyam Gehlot
"""
from __future__ import annotations

import logging
import os

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

EAR_THRESHOLD: float = 0.20
MIN_BPM: float       = 8.0
MAX_BPM: float       = 30.0

# dlib 68-pt right eye landmark indices (0-indexed)
_LE_OUTER      = 36
_LE_TOP_OUTER  = 37
_LE_TOP_INNER  = 38
_LE_INNER      = 39
_LE_BOT_INNER  = 40
_LE_BOT_OUTER  = 41

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
    logger.warning("dlib not installed — BlinkRateDetector will return 0 BPM")


def _build_dlib_detectors(predictor_path: str):
    """Build dlib face detector + shape predictor. Returns (detector, predictor) or (None, None)."""
    if not _DLIB_AVAILABLE:
        return None, None
    abs_path = os.path.abspath(predictor_path)
    if not os.path.exists(abs_path):
        logger.warning(
            "dlib shape predictor not found at %s — BlinkRateDetector degraded. "
            "Download: see models/README.md",
            abs_path,
        )
        return None, None
    detector  = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(abs_path)
    return detector, predictor


# ── BlinkRateDetector class ───────────────────────────────────────────────────

class BlinkRateDetector:
    """
    Deepfake blink rate anomaly detector using dlib 68-pt EAR.

    Usage:
        detector = BlinkRateDetector()
        bpm, is_suspicious = detector.compute_blink_rate(frames, fps=25.0)
    """

    def __init__(
        self,
        ear_threshold: float = EAR_THRESHOLD,
        min_bpm: float = MIN_BPM,
        max_bpm: float = MAX_BPM,
        predictor_path: str = _DEFAULT_PREDICTOR_PATH,
    ) -> None:
        self.ear_threshold = ear_threshold
        self.min_bpm = min_bpm
        self.max_bpm = max_bpm
        self._detector, self._predictor = _build_dlib_detectors(predictor_path)

    @staticmethod
    def _dist(p1, p2) -> float:
        return float(np.linalg.norm(
            np.array([p1.x, p1.y]) - np.array([p2.x, p2.y])
        ))

    def _compute_ear(self, shape) -> float:
        """
        Eye Aspect Ratio from dlib 68-pt landmarks (right eye).

        EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
        """
        d = self._dist
        vertical_1 = d(shape.part(_LE_TOP_OUTER), shape.part(_LE_BOT_OUTER))
        vertical_2 = d(shape.part(_LE_TOP_INNER), shape.part(_LE_BOT_INNER))
        horizontal = d(shape.part(_LE_OUTER),     shape.part(_LE_INNER))
        return (vertical_1 + vertical_2) / (2.0 * horizontal + 1e-8)

    def compute_blink_rate(
        self,
        frames: list[np.ndarray],
        fps: float = 25.0,
    ) -> tuple[float, bool]:
        """
        Compute blink rate in BPM and flag abnormal values.

        Args:
            frames: List of BGR uint8 np.ndarray video frames.
            fps:    Frames per second of the video stream.

        Returns:
            (blink_rate_bpm, is_suspicious):
                blink_rate_bpm — blinks per minute (float).
                is_suspicious  — True if BPM < min_bpm or BPM > max_bpm.
        """
        if not frames:
            return 0.0, True

        if self._detector is None or self._predictor is None:
            return 0.0, True

        blink_count = 0
        blink_in_progress = False

        for frame in frames:
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self._detector(gray, 0)
            if not faces:
                continue
            shape = self._predictor(gray, faces[0])
            ear   = self._compute_ear(shape)
            if ear < self.ear_threshold and not blink_in_progress:
                blink_count += 1
                blink_in_progress = True
            elif ear >= self.ear_threshold:
                blink_in_progress = False

        duration_minutes = len(frames) / (fps * 60.0)
        bpm = (blink_count / duration_minutes) if duration_minutes > 0 else 0.0
        is_suspicious = not (self.min_bpm <= bpm <= self.max_bpm)

        return bpm, is_suspicious

    def get_ear_series(self, frames: list[np.ndarray]) -> list[float]:
        """Return the raw EAR value per frame for diagnostic purposes."""
        if self._detector is None or self._predictor is None:
            return [0.0] * len(frames)

        ears: list[float] = []
        for frame in frames:
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self._detector(gray, 0)
            if faces:
                shape = self._predictor(gray, faces[0])
                ears.append(self._compute_ear(shape))
            else:
                ears.append(0.0)
        return ears

    def close(self) -> None:
        """No-op — dlib objects are GC'd automatically."""
        pass


__all__ = ["BlinkRateDetector", "EAR_THRESHOLD", "MIN_BPM", "MAX_BPM"]
