"""
Audio Analyzer
==============
Extracts acoustic features from raw PCM audio for deepfake detection.
Works alongside LipSyncVerifier for the cross-modal analysis pipeline.
"""
from __future__ import annotations

import logging

import librosa
import numpy as np

logger = logging.getLogger(__name__)


def extract_mfcc(
    audio_bytes: bytes,
    sample_rate: int = 16000,
    n_mfcc: int = 13,
) -> np.ndarray:
    """
    Extract Mel-frequency cepstral coefficients (MFCCs) from raw PCM bytes.

    Args:
        audio_bytes:  Raw 16-bit signed PCM mono bytes.
        sample_rate:  Sample rate in Hz (default 16000).
        n_mfcc:       Number of MFCC coefficients to compute.

    Returns:
        ndarray of shape [n_mfcc, T] — MFCCs over time frames.
    """
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    mfcc = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=n_mfcc)
    return mfcc.astype(np.float32)


def extract_rms_energy(
    audio_bytes: bytes,
    frame_length: int = 512,
    hop_length: int = 512,
) -> np.ndarray:
    """
    Extract frame-level RMS energy envelope from raw PCM bytes.

    Returns:
        1-D ndarray of RMS energy values per frame.
    """
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)
    return rms[0].astype(np.float32)


def extract_spectral_centroid(
    audio_bytes: bytes,
    sample_rate: int = 16000,
) -> np.ndarray:
    """Extract spectral centroid — higher values indicate brighter audio (TTS artefact)."""
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    centroid = librosa.feature.spectral_centroid(y=audio, sr=sample_rate)
    return centroid[0].astype(np.float32)


def detect_audio_anomaly(
    audio_bytes: bytes,
    sample_rate: int = 16000,
    silence_threshold: float = 0.01,
) -> dict:
    """
    High-level anomaly detection combining multiple acoustic features.

    Returns:
        dict with keys: is_anomalous, rms_mean, silence_ratio, signals
    """
    signals: list[str] = []

    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    if len(audio) == 0:
        return {"is_anomalous": True, "rms_mean": 0.0, "silence_ratio": 1.0, "signals": ["empty-audio"]}

    rms = librosa.feature.rms(y=audio, frame_length=512, hop_length=512)[0]
    rms_mean = float(np.mean(rms))
    silence_ratio = float(np.mean(rms < silence_threshold))

    # Flag excessive silence (TTS-generated audio often has uniform energy)
    if silence_ratio > 0.6:
        signals.append(f"excessive-silence:{silence_ratio:.2f}")

    # Flag unusually flat energy profile (synthetic voice fingerprint)
    rms_std = float(np.std(rms))
    if rms_std < 0.005 and rms_mean > 0.01:
        signals.append(f"flat-energy-profile:std={rms_std:.4f}")

    return {
        "is_anomalous": len(signals) > 0,
        "rms_mean": round(rms_mean, 4),
        "silence_ratio": round(silence_ratio, 4),
        "signals": signals,
    }
