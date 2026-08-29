"""
Visual Artifact Detector
========================
Standalone MobileNetV2-based binary classifier for deepfake visual artifact
detection. Runs in fp16 on Apple MPS (Metal Performance Shaders) with CPU
fallback. Sub-batch size is strictly capped at 4 frames to stay within the
16 GB M4 memory budget.

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


# ── Model ──────────────────────────────────────────────────────────────────────

class VisualArtifactDetector(nn.Module):
    """
    Lightweight deepfake artifact classifier built on MobileNetV2.

    Architecture:
        - Backbone: MobileNetV2 pretrained on ImageNet (frozen)
        - Head: Dropout(0.2) → Linear(1280, 1) → Sigmoid
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

        Processes frames in sub-batches of exactly SUB_BATCH_SIZE (4) to
        respect the M4 memory budget. Calls torch.mps.empty_cache() and
        gc.collect() after each sub-batch to prevent MPS memory accumulation.

        Args:
            frames: list of BGR np.ndarray frames.

        Returns:
            list[float] — artifact probability per frame in [0.0, 1.0].
            0.0 = likely real, 1.0 = likely fake.
        """
        if not frames:
            return []

        scores: list[float] = []
        for i in range(0, len(frames), SUB_BATCH_SIZE):
            sub = frames[i : i + SUB_BATCH_SIZE]
            batch_tensor = self.preprocess_frames(sub)
            output = self.model(batch_tensor)           # [B, 1]
            batch_scores = output.squeeze(1).cpu().float().tolist()
            scores.extend(batch_scores)

            # Explicit memory release after every sub-batch
            if DEVICE.type == "mps":
                torch.mps.empty_cache()
            gc.collect()

        return scores

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass (used by score_batch internally)."""
        return self.model(x)


__all__ = ["VisualArtifactDetector", "DEVICE"]
