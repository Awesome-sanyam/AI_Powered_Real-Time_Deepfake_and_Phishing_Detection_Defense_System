"""
Frame Preprocessor — MPS-Optimised Pipeline
=============================================
Converts raw OpenCV BGR frames into model-ready float16 tensors
pushed directly to the configured compute device (MPS / CUDA / CPU).

Key design decisions:
  - float16 (half precision) reduces MPS memory footprint by 50%
  - torch.mps.empty_cache() called after every batch to prevent OOM
  - Returns CPU-side float32 to avoid MPS→CPU copy bottleneck in callers

Author: Sanyam Gehlot
"""
from __future__ import annotations

import logging

import cv2
import numpy as np
import torch
import torchvision.transforms as T

from ai_engine.config import DEVICE, IS_MPS, VISION_INPUT_SIZE

logger = logging.getLogger(__name__)

# ── ImageNet normalisation constants ──────────────────────────────────────────
_IMAGENET_MEAN = [0.485, 0.456, 0.406]
_IMAGENET_STD = [0.229, 0.224, 0.225]

_TRANSFORM = T.Compose([
    T.ToPILImage(),
    T.Resize((VISION_INPUT_SIZE, VISION_INPUT_SIZE)),
    T.ToTensor(),                          # → float32 [0, 1] on CPU
    T.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
])


# ── Core public API ────────────────────────────────────────────────────────────

def preprocess_frame(frame: np.ndarray) -> torch.Tensor:
    """
    Preprocess a single BGR OpenCV frame for model inference.

    Pipeline:
        BGR np.ndarray  →  RGB  →  resize 224×224  →  ImageNet normalise
        →  float16  →  push to DEVICE (MPS/CUDA/CPU)
        →  inference-ready tensor [1, 3, 224, 224]

    After processing, calls torch.mps.empty_cache() if on MPS device
    to immediately reclaim Metal GPU memory.

    Args:
        frame: BGR np.ndarray from OpenCV (H × W × 3, uint8).

    Returns:
        float32 CPU tensor of shape [1, 3, 224, 224].
        Returned as float32 on CPU regardless of inference device to
        avoid downstream MPS-to-CPU copy overhead.

    Raises:
        ValueError: If frame is None or has unexpected shape.
    """
    if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError(f"Invalid frame: expected (H, W, 3) BGR array, got {frame.shape if frame is not None else None}")

    # BGR → RGB
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Apply transforms: PIL resize + ToTensor + Normalize → CPU float32
    tensor_cpu: torch.Tensor = _TRANSFORM(rgb)          # [3, 224, 224]

    # Add batch dimension and push to device in float16
    tensor_device = tensor_cpu.unsqueeze(0).to(DEVICE).half()  # [1, 3, 224, 224] fp16

    # Pull result back to CPU as float32 for safe downstream use
    result = tensor_device.float().cpu()

    # Release MPS Metal cache immediately after use
    if IS_MPS:
        torch.mps.empty_cache()
        logger.debug("MPS cache flushed after frame preprocessing")

    return result  # [1, 3, 224, 224] float32 CPU


def preprocess_batch(frames: list[np.ndarray]) -> torch.Tensor:
    """
    Preprocess a list of BGR frames into a batched tensor.

    Processes in sub-batches of VISION_BATCH_SIZE (default 4) to respect
    the 16 GB unified memory budget on M4 MacBook Air.

    Args:
        frames: List of BGR np.ndarray frames.

    Returns:
        Stacked float32 CPU tensor of shape [N, 3, 224, 224].
    """
    from ai_engine.config import VISION_BATCH_SIZE

    if not frames:
        raise ValueError("frames list is empty")

    results: list[torch.Tensor] = []

    for i in range(0, len(frames), VISION_BATCH_SIZE):
        sub_batch = frames[i : i + VISION_BATCH_SIZE]
        sub_tensors = []

        for frame in sub_batch:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            t = _TRANSFORM(rgb)           # [3, 224, 224] float32 CPU
            sub_tensors.append(t)

        # Stack → push to device as fp16
        batch_device = torch.stack(sub_tensors).to(DEVICE).half()  # [B, 3, 224, 224]

        # Back to CPU float32
        results.append(batch_device.float().cpu())

        # MPS memory cleanup after every sub-batch
        if IS_MPS:
            torch.mps.empty_cache()

    return torch.cat(results, dim=0)  # [N, 3, 224, 224]


def jpeg_bytes_to_bgr(jpeg_bytes: bytes) -> np.ndarray | None:
    """
    Decode raw JPEG bytes to an OpenCV BGR frame.

    Returns:
        BGR np.ndarray or None if decoding fails.
    """
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        logger.warning("cv2.imdecode returned None — invalid JPEG bytes")
    return frame
