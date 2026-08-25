"""
Frame Preprocessor
==================
Converts raw JPEG bytes or BGR OpenCV frames into model-ready tensors.
Used by VisualArtifactDetector before inference.
"""
from __future__ import annotations

import cv2
import numpy as np
import torchvision.transforms as T


_IMAGENET_TRANSFORM = T.Compose([
    T.ToPILImage(),
    T.Resize((224, 224)),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def jpeg_bytes_to_bgr(jpeg_bytes: bytes) -> np.ndarray | None:
    """Decode a JPEG byte string to a BGR OpenCV frame."""
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    """Convert BGR frame (OpenCV default) to RGB."""
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def preprocess_frame(frame: np.ndarray) -> "torch.Tensor":  # noqa: F821
    """
    Apply ImageNet normalisation to a single BGR frame.

    Args:
        frame: BGR np.ndarray from OpenCV.

    Returns:
        Normalised float32 tensor of shape [3, 224, 224].
    """
    rgb = bgr_to_rgb(frame)
    return _IMAGENET_TRANSFORM(rgb)


def resize_frame(frame: np.ndarray, size: tuple[int, int] = (224, 224)) -> np.ndarray:
    """Resize a frame to the given (width, height)."""
    return cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)
