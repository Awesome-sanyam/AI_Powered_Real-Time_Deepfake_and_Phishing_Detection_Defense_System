"""
Lip Sync Verifier
=================
Detects audio-visual temporal desynchronisation — a hallmark of deepfakes —
by cross-correlating two signals derived from the same video segment:

  1. Lip aperture time-series  (MediaPipe FaceMesh landmarks 13 & 14)
  2. Audio RMS energy envelope  (Librosa frame-level RMS)

A cross-correlation peak lag > LIP_SYNC_THRESHOLD_MS (80 ms) indicates that
the audio and video are out of phase, strongly suggesting synthetic manipulation.

Author: Sanyam Gehlot
"""
from __future__ import annotations

import logging

import cv2
import librosa
import numpy as np

logger = logging.getLogger(__name__)

# MediaPipe lazy import so the module is importable even without MediaPipe
try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False
    logger.warning("mediapipe not installed — LipSyncVerifier will return 0 delay")


# ── Constants ──────────────────────────────────────────────────────────────────

LIP_SYNC_THRESHOLD_MS: float = 80.0  # per About.md spec
UPPER_LIP_IDX: int = 13              # MediaPipe 468-point model landmark index
LOWER_LIP_IDX: int = 14
FRAME_LENGTH: int = 512
HOP_LENGTH: int = 512


# ── LipSyncVerifier class ─────────────────────────────────────────────────────

class LipSyncVerifier:
    """
    Cross-modal lip-sync analyser using MediaPipe FaceMesh + Librosa.

    Usage:
        verifier = LipSyncVerifier()
        delay_ms, is_suspicious = verifier.verify(frames, audio_bytes, fps=25.0)
    """

    def __init__(
        self,
        threshold_ms: float = LIP_SYNC_THRESHOLD_MS,
        sample_rate: int = 16_000,
    ) -> None:
        self.threshold_ms = threshold_ms
        self.sample_rate = sample_rate
        self._face_mesh = None

        if _MP_AVAILABLE:
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

    def extract_lip_aperture(
        self,
        frames: list[np.ndarray],
        fps: float = 25.0,  # noqa: ARG002 — kept for API symmetry
    ) -> np.ndarray:
        """
        Extract normalised lip aperture per frame via MediaPipe FaceMesh.

        Landmark indices 13 (upper inner lip) and 14 (lower inner lip) give
        the vertical distance. The signal is normalised to [0, 1] by the
        face mesh's own coordinate system (fractional image height).

        Args:
            frames: List of BGR uint8 np.ndarray video frames.
            fps:    Frames per second (kept for API symmetry, not used here).

        Returns:
            1-D float32 np.ndarray of aperture values, one per frame.
        """
        apertures: list[float] = []

        if self._face_mesh is None:
            return np.zeros(len(frames), dtype=np.float32)

        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self._face_mesh.process(rgb)
            if result.multi_face_landmarks:
                lm = result.multi_face_landmarks[0].landmark
                aperture = abs(lm[LOWER_LIP_IDX].y - lm[UPPER_LIP_IDX].y)
                apertures.append(float(aperture))
            else:
                apertures.append(0.0)

        return np.array(apertures, dtype=np.float32)

    def extract_audio_energy(
        self,
        audio_bytes: bytes,
    ) -> np.ndarray:
        """
        Extract frame-level RMS energy envelope from raw 16-bit PCM bytes.

        Args:
            audio_bytes: Raw 16-bit signed PCM mono audio.

        Returns:
            1-D float32 np.ndarray of RMS energy values per analysis frame.
        """
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
        """
        Compute the cross-correlation lag between lip and audio signals.

        Both signals are zero-mean normalised before correlation to make the
        result invariant to scale differences. The lag is converted from frames
        to milliseconds using the video FPS.

        Args:
            lip_signal:   Lip aperture array [T_lip].
            audio_signal: RMS energy array [T_audio].
            fps:          Video frame rate used to convert lag → ms.

        Returns:
            Absolute delay in milliseconds (float).
        """
        n = min(len(lip_signal), len(audio_signal))
        if n < 2:
            return 0.0

        lip = lip_signal[:n]
        audio = audio_signal[:n]

        # Zero-mean normalise to remove scale bias
        lip = (lip - lip.mean()) / (lip.std() + 1e-8)
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

        Args:
            frames:       BGR video frames.
            audio_bytes:  Raw 16-bit PCM mono audio.
            fps:          Video frame rate.
            sample_rate:  Audio sample rate (Hz) — unused currently but
                          kept for API completeness.

        Returns:
            (delay_ms, is_suspicious):
                delay_ms       — computed lag in milliseconds.
                is_suspicious  — True if delay > threshold_ms (80 ms).
        """
        lip_signal   = self.extract_lip_aperture(frames, fps)
        audio_signal = self.extract_audio_energy(audio_bytes)
        delay_ms     = self.compute_sync_delay_ms(lip_signal, audio_signal, fps)
        return delay_ms, delay_ms > self.threshold_ms


__all__ = ["LipSyncVerifier", "LIP_SYNC_THRESHOLD_MS"]
