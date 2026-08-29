"""
Blink Rate Detector
===================
Calculates per-video blink rate in beats per minute (BPM) using MediaPipe
FaceMesh Eye Aspect Ratio (EAR). Abnormal blink rates are a reliable
deepfake signal:

  - Too slow (< 8 BPM): Deepfakes often omit blink synthesis
  - Too fast (> 30 BPM): GAN artefact from temporal instability

Algorithm:
  EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
  where p1–p6 are six eye landmarks from MediaPipe FaceMesh.

  A blink is counted when EAR drops below EAR_THRESHOLD for one or more
  consecutive frames and then recovers above it.

FaceMesh landmark indices used:
  Right eye: 385 (top-right), 380 (bottom-right), 386 (top-left),
             374 (bottom-left), 362 (outer), 263 (inner)

Author: Sanyam Gehlot
"""
from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False
    logger.warning("mediapipe not installed — BlinkRateDetector will return 0 BPM")


# ── Constants ──────────────────────────────────────────────────────────────────

EAR_THRESHOLD: float = 0.20    # Below this → eye closed (blink in progress)
MIN_BPM: float       = 8.0     # Below → abnormally low (suspicious)
MAX_BPM: float       = 30.0    # Above → abnormally high (suspicious)

# MediaPipe FaceMesh right-eye landmark indices
_LM_TOP_RIGHT    = 385
_LM_BOTTOM_RIGHT = 380
_LM_TOP_LEFT     = 386
_LM_BOTTOM_LEFT  = 374
_LM_OUTER_CORNER = 362
_LM_INNER_CORNER = 263


# ── BlinkRateDetector class ───────────────────────────────────────────────────

class BlinkRateDetector:
    """
    Deepfake blink rate anomaly detector using MediaPipe FaceMesh EAR.

    Usage:
        detector = BlinkRateDetector()
        bpm, is_suspicious = detector.compute_blink_rate(frames, fps=25.0)
    """

    def __init__(
        self,
        ear_threshold: float = EAR_THRESHOLD,
        min_bpm: float = MIN_BPM,
        max_bpm: float = MAX_BPM,
    ) -> None:
        self.ear_threshold = ear_threshold
        self.min_bpm = min_bpm
        self.max_bpm = max_bpm
        self._face_mesh = None

        if _MP_AVAILABLE:
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

    @staticmethod
    def _euclidean(lm, idx_a: int, idx_b: int) -> float:
        """Euclidean distance between two FaceMesh landmark points."""
        a = lm[idx_a]
        b = lm[idx_b]
        return float(np.linalg.norm(np.array([a.x, a.y]) - np.array([b.x, b.y])))

    def _compute_ear(self, landmarks) -> float:
        """
        Compute Eye Aspect Ratio (EAR) from MediaPipe FaceMesh landmarks.

        EAR = (||p1-p4|| + ||p2-p5||) / (2 * ||p3-p6||)
        Uses the right eye landmark set for consistency.
        """
        e = self._euclidean
        vertical_1 = e(landmarks, _LM_TOP_RIGHT,  _LM_BOTTOM_RIGHT)
        vertical_2 = e(landmarks, _LM_TOP_LEFT,   _LM_BOTTOM_LEFT)
        horizontal = e(landmarks, _LM_OUTER_CORNER, _LM_INNER_CORNER)
        return (vertical_1 + vertical_2) / (2.0 * horizontal + 1e-8)

    def compute_blink_rate(
        self,
        frames: list[np.ndarray],
        fps: float = 25.0,
    ) -> tuple[float, bool]:
        """
        Compute blink rate in BPM and flag abnormal values.

        A rising-edge counter is used: a blink is counted when EAR first
        drops below ear_threshold (i.e., eye closes). The counter resets
        when EAR recovers to prevent double-counting within a single blink.

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

        if self._face_mesh is None:
            return 0.0, True

        blink_count = 0
        blink_in_progress = False

        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self._face_mesh.process(rgb)

            if result.multi_face_landmarks:
                lm = result.multi_face_landmarks[0].landmark
                ear = self._compute_ear(lm)

                if ear < self.ear_threshold and not blink_in_progress:
                    # Rising edge — eye just closed
                    blink_count += 1
                    blink_in_progress = True
                elif ear >= self.ear_threshold:
                    # Eye opened again — reset for next blink
                    blink_in_progress = False

        # Convert blink count to BPM using video duration
        duration_minutes = len(frames) / (fps * 60.0)
        bpm = (blink_count / duration_minutes) if duration_minutes > 0 else 0.0
        is_suspicious = not (self.min_bpm <= bpm <= self.max_bpm)

        return bpm, is_suspicious

    def get_ear_series(self, frames: list[np.ndarray]) -> list[float]:
        """
        Return the raw EAR value per frame for diagnostic purposes.

        Args:
            frames: List of BGR video frames.

        Returns:
            list[float] — EAR value for each frame (0.0 if no face detected).
        """
        if self._face_mesh is None:
            return [0.0] * len(frames)

        ears: list[float] = []
        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self._face_mesh.process(rgb)
            if result.multi_face_landmarks:
                lm = result.multi_face_landmarks[0].landmark
                ears.append(self._compute_ear(lm))
            else:
                ears.append(0.0)
        return ears


__all__ = ["BlinkRateDetector", "EAR_THRESHOLD", "MIN_BPM", "MAX_BPM"]
