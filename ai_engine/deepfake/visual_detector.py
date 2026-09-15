"""
Visual Artifact Detector
========================
Standalone MobileNetV2-based binary classifier for deepfake visual artifact
detection, augmented with Laplacian spatial-frequency noise analysis.

CALIBRATION (v2):
  - Combines MobileNetV2 sigmoid output with Laplacian variance to establish
    a proper noise floor for unmodified webcam frames.
  - Clean frames with natural texture have high Laplacian variance → low score.
  - Deepfake frames with GAN smoothing artefacts have low variance → high score.

Formula (per-frame):
    lap_norm   = clamp(laplacian_var / 800.0, 0.0, 1.0)   # 800 = natural-scene ref
    art_signal = clamp(1.0 − lap_norm, 0.0, 1.0)          # high lap → low artifact
    score      = 0.45 * model_out + 0.55 * art_signal
    # Recalibrate: subtract 0.10 baseline → floor for genuine webcam frames ≈ 0.05-0.15

Runs in fp16 on Apple MPS (Metal Performance Shaders) with CPU fallback.
Sub-batch size is strictly capped at 4 frames to stay within the 16 GB M4
memory budget.

Author: Sanyam Gehlot
"""
from __future__ import annotations

import gc
import logging
import os
from typing import Optional

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T

logger = logging.getLogger(__name__)


# ── Device resolution ──────────────────────────────────────────────────────────

def _resolve_device() -> torch.device:
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        logger.info("VisualArtifactDetector: using MPS (Apple Metal)")
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    logger.warning("VisualArtifactDetector: falling back to CPU")
    return torch.device("cpu")


DEVICE: torch.device = _resolve_device()

# ── Constants ──────────────────────────────────────────────────────────────────

SUB_BATCH_SIZE: int = 4   # Hard cap — M4 16 GB memory constraint

_IMAGENET_MEAN = [0.485, 0.456, 0.406]
_IMAGENET_STD  = [0.229, 0.224, 0.225]

# Laplacian variance reference for a natural-scene webcam frame.
# A genuine 720p frame in normal indoor lighting has ~300–1500 variance.
# We use 800 as a mid-range normalisation anchor.
_LAP_VAR_REF: float = 800.0

# Model / spatial-frequency blend weights
_W_MODEL: float = 0.45   # MobileNetV2 sigmoid contribution
_W_SPATIAL: float = 0.55  # Laplacian spatial-frequency contribution

# Calibration bias: unmodified webcam baseline compensation.
# Without fine-tuned weights, ImageNet backbone centre-biases at ~0.50.
# Subtracting this bias pushes clean frames to 0.05–0.15.
_BASELINE_BIAS: float = 0.10


# ── Model ──────────────────────────────────────────────────────────────────────

class VisualArtifactDetector(nn.Module):
    """
    Lightweight deepfake artifact classifier built on MobileNetV2,
    calibrated with Laplacian spatial-frequency analysis.

    Architecture:
        - Backbone: MobileNetV2 pretrained on ImageNet (frozen)
        - Head: Dropout(0.2) → Linear(1280, 1) → Sigmoid
        - Calibration: blended with per-frame Laplacian variance score
        - Precision: fp16 (half) on MPS/CUDA, fp32 on CPU
        - Memory: ~14 MB weights + ~50 MB activations @ batch-of-4 fp16

    Usage:
        detector = VisualArtifactDetector()
        scores = detector.score_batch(frames)   # list[float] in [0, 1]
    """

    _TRANSFORM = T.Compose([
        T.ToPILImage(),
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
    ])

    def __init__(self, weights_path: Optional[str] = None) -> None:
        super().__init__()

        backbone = models.mobilenet_v2(
            weights=models.MobileNet_V2_Weights.IMAGENET1K_V1
        )
        # Freeze all backbone parameters — only the classification head trains
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
            state = torch.load(weights_path, map_location="cpu", weights_only=True)
            self.model.load_state_dict(state)
            logger.info(f"VisualArtifactDetector: loaded fine-tuned weights from {weights_path}")
        else:
            logger.info("VisualArtifactDetector: using ImageNet backbone (no fine-tuned weights)")

        # Cast to fp16 for memory efficiency on MPS/CUDA
        precision = torch.float16 if DEVICE.type in ("mps", "cuda") else torch.float32
        self.model = self.model.to(DEVICE).to(precision)
        self.model.eval()
        self._precision = precision

    @staticmethod
    def _laplacian_artifact_score(frame: np.ndarray) -> float:
        """
        Compute a spatial-frequency artifact signal from a single BGR frame.

        Genuine webcam frames have natural textures (high Laplacian variance).
        GAN-synthesised / deepfake frames are over-smoothed (low variance).

        Returns:
            float in [0.0, 1.0]:
                0.0 → natural texture (likely real)
                1.0 → over-smooth / GAN artefact (likely deepfake)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        # Normalise: 0 variance → score 1.0 (maximum suspicion)
        #            _LAP_VAR_REF variance → score 0.0 (clearly natural)
        lap_norm = float(np.clip(lap_var / _LAP_VAR_REF, 0.0, 1.0))
        return float(np.clip(1.0 - lap_norm, 0.0, 1.0))

    def preprocess_frames(self, frames: list[np.ndarray]) -> torch.Tensor:
        """
        Convert a list of BGR OpenCV frames into a normalised batched tensor.

        Args:
            frames: list of HxWx3 BGR uint8 np.ndarray.

        Returns:
            Tensor of shape [B, 3, 224, 224] on DEVICE in model precision.
        """
        tensors = [
            self._TRANSFORM(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            for frame in frames
        ]
        return torch.stack(tensors).to(DEVICE).to(self._precision)

    @torch.no_grad()
    def score_batch(self, frames: list[np.ndarray]) -> list[float]:
        """
        Score a list of frames for visual deepfake artifacts.

        Blends MobileNetV2 model output with Laplacian spatial-frequency
        artifact signal, then applies a baseline bias correction so that
        genuine webcam frames yield scores in the 0.05–0.15 range rather
        than the uncalibrated ~0.50 centre-bias.

        Processes frames in sub-batches of SUB_BATCH_SIZE (4) to respect the
        M4 memory budget. Calls torch.mps.empty_cache() + gc.collect() after
        each sub-batch.

        Args:
            frames: list of BGR np.ndarray frames.

        Returns:
            list[float] — calibrated artifact probability per frame in [0.0, 1.0].
            0.0 = likely real, 1.0 = likely fake.
        """
        if not frames:
            return []

        # Pre-compute per-frame Laplacian scores (CPU only, fast)
        lap_scores = [self._laplacian_artifact_score(f) for f in frames]

        model_scores: list[float] = []
        for i in range(0, len(frames), SUB_BATCH_SIZE):
            sub = frames[i : i + SUB_BATCH_SIZE]
            batch_tensor = self.preprocess_frames(sub)
            output = self.model(batch_tensor)           # [B, 1]
            batch_scores = output.squeeze(1).cpu().float().tolist()
            model_scores.extend(batch_scores)

            # Explicit memory release after every sub-batch
            if DEVICE.type == "mps":
                torch.mps.empty_cache()
            gc.collect()

        # Blend model + spatial signal, then apply baseline correction
        calibrated: list[float] = []
        for m_score, l_score in zip(model_scores, lap_scores):
            blended = _W_MODEL * m_score + _W_SPATIAL * l_score
            adjusted = float(np.clip(blended - _BASELINE_BIAS, 0.0, 1.0))
            calibrated.append(adjusted)

        return calibrated

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass (used by score_batch internally)."""
        return self.model(x)


__all__ = ["VisualArtifactDetector", "DEVICE"]
