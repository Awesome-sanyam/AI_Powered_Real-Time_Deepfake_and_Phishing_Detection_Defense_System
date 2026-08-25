"""
AI Engine — Cross-Modal Verification Engine
============================================
Detects deepfakes by analysing the temporal coherence between:
  1. Visual artifacts (MobileNetV2 on MPS, fp16, batch_size=4)
  2. Lip-sync delay (MediaPipe FaceMesh + Librosa cross-correlation)
  3. Blink rate anomaly (Eye Aspect Ratio via FaceMesh)

All verdicts are cryptographically signed via ECDSA P-256.
See About.md for the fully annotated boilerplate with algorithm commentary.

Hardware target: Apple Silicon M4 — uses torch.device("mps") with CPU fallback.
Memory budget  : ≤ 2 GB peak (batch_size=4, fp16 inference).
"""
from __future__ import annotations

import gc
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import librosa
import mediapipe as mp
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T

from ai_engine.identity.ecdsa_service import ECDSAService

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
# Visual Artifact Detector (MobileNetV2 on MPS, fp16)
# ─────────────────────────────────────────────────────────────────────────────

class VisualArtifactDetector(nn.Module):
    """
    Lightweight deepfake artifact classifier.
    Backbone: MobileNetV2 pretrained on ImageNet.
    Head    : Binary classifier (real=0 / fake=1) with frozen backbone.
    Memory  : ~14 MB weights, ~50 MB activations per batch-of-4 @ fp16.
    """

    _TRANSFORM = T.Compose([
        T.ToPILImage(),
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    def __init__(self, weights_path: Optional[str] = None) -> None:
        super().__init__()
        backbone = models.mobilenet_v2(
            weights=models.MobileNet_V2_Weights.IMAGENET1K_V1
        )
        # Freeze backbone — only train the classification head
        for param in backbone.features.parameters():
            param.requires_grad = False

        in_features = backbone.classifier[1].in_features
        backbone.classifier = nn.Sequential(
            nn.Dropout(0.2),
            nn.Linear(in_features, 1),
            nn.Sigmoid(),
        )
        self.model = backbone

        if weights_path and os.path.exists(weights_path):
            self.model.load_state_dict(
                torch.load(weights_path, map_location="cpu", weights_only=True)
            )
            logger.info(f"Loaded fine-tuned weights from {weights_path}")

        # fp16 on MPS for memory efficiency
        self.model = self.model.to(DEVICE).half()
        self.model.eval()

    def preprocess_frames(self, frames: list[np.ndarray]) -> torch.Tensor:
        """BGR OpenCV frames → batched normalised MPS tensor [B, 3, 224, 224]."""
        tensors = [self._TRANSFORM(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)) for f in frames]
        return torch.stack(tensors).to(DEVICE).half()

    @torch.no_grad()
    def score_batch(self, frames: list[np.ndarray]) -> list[float]:
        """
        Score frames in sub-batches of 4.
        Returns artifact probability per frame (0=real, 1=fake).
        """
        scores: list[float] = []
        for i in range(0, len(frames), 4):
            sub = frames[i : i + 4]
            out = self.model(self.preprocess_frames(sub))       # [B, 1]
            scores.extend(out.squeeze(1).cpu().float().tolist())
            # Release MPS cache between sub-batches
            if DEVICE.type == "mps":
                torch.mps.empty_cache()
        return scores


# ─────────────────────────────────────────────────────────────────────────────
# Lip-Sync Verifier (MediaPipe FaceMesh + Librosa)
# ─────────────────────────────────────────────────────────────────────────────

class LipSyncVerifier:
    """
    Detects audio-visual desynchronisation by cross-correlating:
    - Lip aperture signal (MediaPipe FaceMesh landmarks)
    - Audio energy envelope (Librosa RMS)

    Cross-correlation lag > LIP_SYNC_THRESHOLD_MS → suspicious deepfake.
    """

    LIP_SYNC_THRESHOLD_MS: float = 80.0
    UPPER_LIP: int = 13
    LOWER_LIP: int = 14

    def __init__(self) -> None:
        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def extract_lip_aperture(
        self, frames: list[np.ndarray], fps: float  # noqa: ARG002
    ) -> np.ndarray:
        """Extract normalised lip aperture (0→1) per frame."""
        apertures: list[float] = []
        for frame in frames:
            results = self._face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.multi_face_landmarks:
                lm = results.multi_face_landmarks[0].landmark
                apertures.append(abs(lm[self.LOWER_LIP].y - lm[self.UPPER_LIP].y))
            else:
                apertures.append(0.0)
        return np.array(apertures, dtype=np.float32)

    def extract_audio_energy(
        self, audio_bytes: bytes, sample_rate: int = 16000  # noqa: ARG002
    ) -> np.ndarray:
        """Extract frame-level RMS energy from raw PCM bytes."""
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return librosa.feature.rms(
            y=audio, frame_length=512, hop_length=512
        )[0].astype(np.float32)

    def compute_sync_delay_ms(
        self, lip: np.ndarray, audio: np.ndarray, fps: float
    ) -> float:
        """Cross-correlate lip and audio signals; return delay in ms."""
        n = min(len(lip), len(audio))
        if n < 2:
            return 0.0
        lip_s = lip[:n]
        audio_s = audio[:n]
        lip_s = (lip_s - lip_s.mean()) / (lip_s.std() + 1e-8)
        audio_s = (audio_s - audio_s.mean()) / (audio_s.std() + 1e-8)
        lag = int(np.argmax(np.correlate(lip_s, audio_s, "full"))) - (n - 1)
        return abs(lag) * (1000.0 / fps)

    def verify(
        self,
        frames: list[np.ndarray],
        audio_bytes: bytes,
        fps: float = 25.0,
        sample_rate: int = 16000,
    ) -> tuple[float, bool]:
        """Returns (delay_ms, is_suspicious)."""
        lip = self.extract_lip_aperture(frames, fps)
        audio = self.extract_audio_energy(audio_bytes, sample_rate)
        delay = self.compute_sync_delay_ms(lip, audio, fps)
        return delay, delay > self.LIP_SYNC_THRESHOLD_MS


# ─────────────────────────────────────────────────────────────────────────────
# Blink Rate Detector (MediaPipe FaceMesh EAR)
# ─────────────────────────────────────────────────────────────────────────────

class BlinkRateDetector:
    """
    Computes blink rate using Eye Aspect Ratio (EAR) from FaceMesh.
    Abnormal rates (< 8 or > 30 bpm) indicate a possible deepfake.
    """

    EAR_THRESHOLD: float = 0.20
    MIN_BPM: float = 8.0
    MAX_BPM: float = 30.0

    def __init__(self) -> None:
        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        )

    def _ear(self, lm) -> float:
        """Compute Eye Aspect Ratio from landmark list."""
        def dist(a, b) -> float:
            return float(np.linalg.norm(np.array([a.x, a.y]) - np.array([b.x, b.y])))
        return (dist(lm[385], lm[380]) + dist(lm[386], lm[374])) / (
            2.0 * dist(lm[362], lm[263]) + 1e-8
        )

    def compute_blink_rate(
        self, frames: list[np.ndarray], fps: float = 25.0
    ) -> tuple[float, bool]:
        """Returns (blink_rate_bpm, is_suspicious)."""
        count, active = 0, False
        for frame in frames:
            results = self._face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.multi_face_landmarks:
                ear = self._ear(results.multi_face_landmarks[0].landmark)
                if ear < self.EAR_THRESHOLD and not active:
                    count += 1
                    active = True
                elif ear >= self.EAR_THRESHOLD:
                    active = False
        dur_min = len(frames) / (fps * 60.0)
        bpm = count / dur_min if dur_min > 0 else 0.0
        return bpm, not (self.MIN_BPM <= bpm <= self.MAX_BPM)


# ─────────────────────────────────────────────────────────────────────────────
# Cross-Modal Verification Engine (Orchestrator)
# ─────────────────────────────────────────────────────────────────────────────

class CrossModalVerificationEngine:
    """
    Orchestrates all three deepfake detection signal streams and aggregates
    them into a weighted confidence score with an ECDSA-signed verdict.

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

    WEIGHTS: dict[str, float] = {"visual": 0.40, "lip_sync": 0.35, "blink": 0.25}
    FAKE_THRESHOLD: float = 0.55

    def __init__(
        self,
        visual_weights_path: Optional[str] = None,
        ecdsa_private_key_pem: Optional[str] = None,
    ) -> None:
        self.visual = VisualArtifactDetector(visual_weights_path)
        self.lip_sync = LipSyncVerifier()
        self.blink = BlinkRateDetector()
        self.ecdsa = ECDSAService(private_key_pem=ecdsa_private_key_pem)
        logger.info(f"CrossModalVerificationEngine ready on {DEVICE}")

    def _confidence(self, v: float, lip_sus: bool, blink_sus: bool) -> float:
        """Compute weighted deepfake confidence in [0, 1]."""
        return float(np.clip(
            self.WEIGHTS["visual"] * v
            + self.WEIGHTS["lip_sync"] * (1.0 if lip_sus else 0.0)
            + self.WEIGHTS["blink"] * (1.0 if blink_sus else 0.0),
            0.0, 1.0,
        ))

    def analyze(
        self,
        session_id: str,
        frames: list[np.ndarray],
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

        # 1. Visual artifact detection
        scores = self.visual.score_batch(frames)
        mean_score = float(np.mean(scores))

        # 2. Lip-sync analysis
        lip_delay, lip_sus = self.lip_sync.verify(frames, audio_bytes, fps, sample_rate)

        # 3. Blink rate analysis
        blink_bpm, blink_sus = self.blink.compute_blink_rate(frames, fps)

        # 4. Confidence aggregation
        conf = self._confidence(mean_score, lip_sus, blink_sus)
        is_fake = conf >= self.FAKE_THRESHOLD

        # 5. ECDSA signing
        payload = (
            f"{session_id}|deepfake={is_fake}|"
            f"confidence={conf:.4f}|ts={int(time.time())}"
        )
        sig, pubkey = self.ecdsa.sign(payload)

        # 6. Memory cleanup
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
                    confidence=self._confidence(scores[i], lip_sus, blink_sus),
                )
                for i in range(len(frames))
            ],
            processing_time_ms=(time.perf_counter() - t0) * 1000,
            signed_verdict=sig,
            public_key_pem=pubkey,
        )

    def cleanup(self) -> None:
        """Release all GPU/MPS resources. Called by FastAPI lifespan on shutdown."""
        del self.visual
        if DEVICE.type == "mps":
            torch.mps.empty_cache()
        gc.collect()
        logger.info("CrossModalVerificationEngine resources released.")
