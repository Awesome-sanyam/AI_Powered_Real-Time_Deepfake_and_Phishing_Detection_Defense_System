"""
Audio Analyzer
==============
Extracts acoustic features from raw 16-bit PCM mono audio bytes for use in
the Cross-Modal Verification pipeline. Wraps librosa operations inside a
class for clean lifecycle management.

Features extracted:
  - 40-coefficient MFCCs (industry standard for speech/voice analysis)
  - Frame-level RMS energy envelope (for lip-sync cross-correlation)
  - Spectral centroid (TTS/synthetic voice fingerprint)
  - Anomaly score combining silence ratio and energy flatness

Author: Sanyam Gehlot
"""
from __future__ import annotations

import logging
from typing import Optional

import librosa
import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

DEFAULT_SAMPLE_RATE: int   = 16_000
DEFAULT_N_MFCC: int        = 40   # 40-coefficient MFCCs per Phase 2 spec
FRAME_LENGTH: int          = 512
HOP_LENGTH: int            = 512
SILENCE_THRESHOLD: float   = 0.01
FLAT_ENERGY_STD_THRESHOLD  = 0.005


# ── AudioAnalyzer class ───────────────────────────────────────────────────────

class AudioAnalyzer:
    """
    Acoustic feature extractor for deepfake detection.

    All methods accept raw 16-bit signed PCM mono bytes and return
    numpy float32 arrays for downstream cross-modal analysis.

    Usage:
        analyzer = AudioAnalyzer()
        mfcc = analyzer.extract_mfcc(audio_bytes)         # [40, T]
        rms  = analyzer.extract_rms_energy(audio_bytes)   # [T]
        report = analyzer.detect_anomaly(audio_bytes)     # dict
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        n_mfcc: int = DEFAULT_N_MFCC,
    ) -> None:
        self.sample_rate = sample_rate
        self.n_mfcc = n_mfcc

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _bytes_to_float(audio_bytes: bytes) -> np.ndarray:
        """Decode raw 16-bit PCM bytes → normalised float32 array in [-1, 1]."""
        return (
            np.frombuffer(audio_bytes, dtype=np.int16)
            .astype(np.float32) / 32768.0
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def extract_mfcc(
        self,
        audio_bytes: bytes,
        n_mfcc: Optional[int] = None,
    ) -> np.ndarray:
        """
        Extract Mel-Frequency Cepstral Coefficients from raw PCM bytes.

        Args:
            audio_bytes: Raw 16-bit PCM mono audio.
            n_mfcc: Number of MFCC coefficients. Defaults to self.n_mfcc (40).

        Returns:
            np.ndarray of shape [n_mfcc, T] — coefficients over time frames.
        """
        audio = self._bytes_to_float(audio_bytes)
        coeffs = n_mfcc or self.n_mfcc
        mfcc = librosa.feature.mfcc(
            y=audio,
            sr=self.sample_rate,
            n_mfcc=coeffs,
        )
        return mfcc.astype(np.float32)

    def extract_rms_energy(
        self,
        audio_bytes: bytes,
        frame_length: int = FRAME_LENGTH,
        hop_length: int = HOP_LENGTH,
    ) -> np.ndarray:
        """
        Extract frame-level RMS energy envelope for lip-sync cross-correlation.

        Args:
            audio_bytes: Raw 16-bit PCM mono audio.
            frame_length: STFT frame size (samples).
            hop_length: Hop size between frames (samples).

        Returns:
            1-D np.ndarray of RMS energy values per frame.
        """
        audio = self._bytes_to_float(audio_bytes)
        rms = librosa.feature.rms(
            y=audio,
            frame_length=frame_length,
            hop_length=hop_length,
        )
        return rms[0].astype(np.float32)

    def extract_spectral_centroid(self, audio_bytes: bytes) -> np.ndarray:
        """
        Extract spectral centroid per frame.
        Higher values indicate brighter audio — a common TTS artefact.

        Returns:
            1-D np.ndarray of centroid frequencies per frame (Hz).
        """
        audio = self._bytes_to_float(audio_bytes)
        centroid = librosa.feature.spectral_centroid(
            y=audio, sr=self.sample_rate
        )
        return centroid[0].astype(np.float32)

    def detect_anomaly(
        self,
        audio_bytes: bytes,
        silence_threshold: float = SILENCE_THRESHOLD,
    ) -> dict:
        """
        Run acoustic anomaly detection combining multiple feature signals.

        Checks:
          - Excessive silence (>60% silent frames → TTS-generated audio)
          - Flat RMS energy profile (std < 0.005 → synthetic voice)

        Args:
            audio_bytes: Raw 16-bit PCM mono audio.
            silence_threshold: RMS value below which a frame is "silent".

        Returns:
            dict with keys:
                is_anomalous (bool): True if any anomaly signal detected.
                rms_mean (float):    Mean RMS energy.
                silence_ratio (float): Fraction of silent frames.
                signals (list[str]): Human-readable anomaly signal names.
        """
        signals: list[str] = []

        audio = self._bytes_to_float(audio_bytes)
        if len(audio) == 0:
            return {
                "is_anomalous": True,
                "rms_mean": 0.0,
                "silence_ratio": 1.0,
                "signals": ["empty-audio"],
            }

        rms = librosa.feature.rms(
            y=audio, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH
        )[0]

        rms_mean = float(np.mean(rms))
        silence_ratio = float(np.mean(rms < silence_threshold))
        rms_std = float(np.std(rms))

        if silence_ratio > 0.6:
            signals.append(f"excessive-silence:{silence_ratio:.2f}")

        if rms_std < FLAT_ENERGY_STD_THRESHOLD and rms_mean > 0.01:
            signals.append(f"flat-energy-profile:std={rms_std:.4f}")

        return {
            "is_anomalous": len(signals) > 0,
            "rms_mean": round(rms_mean, 4),
            "silence_ratio": round(silence_ratio, 4),
            "signals": signals,
        }


# ── Module-level convenience functions (backwards-compatible) ─────────────────

def extract_mfcc(
    audio_bytes: bytes,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    n_mfcc: int = DEFAULT_N_MFCC,
) -> np.ndarray:
    """Module-level convenience wrapper around AudioAnalyzer.extract_mfcc."""
    return AudioAnalyzer(sample_rate=sample_rate, n_mfcc=n_mfcc).extract_mfcc(audio_bytes)


def extract_rms_energy(
    audio_bytes: bytes,
    frame_length: int = FRAME_LENGTH,
    hop_length: int = HOP_LENGTH,
) -> np.ndarray:
    """Module-level convenience wrapper around AudioAnalyzer.extract_rms_energy."""
    return AudioAnalyzer().extract_rms_energy(audio_bytes, frame_length, hop_length)


def detect_audio_anomaly(
    audio_bytes: bytes,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    silence_threshold: float = SILENCE_THRESHOLD,
) -> dict:
    """Module-level convenience wrapper around AudioAnalyzer.detect_anomaly."""
    return AudioAnalyzer(sample_rate=sample_rate).detect_anomaly(audio_bytes, silence_threshold)


__all__ = ["AudioAnalyzer", "extract_mfcc", "extract_rms_energy", "detect_audio_anomaly"]
