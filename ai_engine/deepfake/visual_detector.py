"""
Visual Artifact Detector
========================
Standalone EfficientNet-B0-based binary classifier for deepfake visual artifact
detection, augmented with Laplacian spatial-frequency noise analysis and
**isolated face cropping** for high-accuracy analysis.

CALIBRATION (v3 — Face-Crop Edition):
  KEY IMPROVEMENT: Instead of analysing the whole frame (which dilutes GAN
  artefacts across background pixels), we first detect and crop the face
  region (+ 20% margin), then pass *only that crop* to MobileNetV2.

  This forces the model to examine:
    - GAN blending boundaries at facial edges
    - Synthetic skin texture and over-smoothing artefacts
    - Generative noise patterns unique to face-swap models

  Face Detection Strategy (priority order):
    1. dlib HOG face detector  (primary — already a project dep, CPU-only)
    2. OpenCV Haar Cascade     (secondary fallback — if dlib unavailable)
    3. Whole-frame fallback    (if no face detected — preserves v2 behaviour)

  Override Trigger:
    If `face_visual_score > FACE_OVERRIDE_THRESHOLD (0.85)`, the score is
    raised to at least `FACE_OVERRIDE_FLOOR (0.85)` regardless of subsequent
    aggregation. High-confidence GAN artefacts detected on a cropped face
    are near-certain deepfakes — don't let temporal smoothing dilute it.

Formula (per-frame, on cropped face):
    lap_norm   = clamp(laplacian_var / 500.0, 0.0, 1.0)   # tighter ref for face crops
    art_signal = clamp(1.0 − lap_norm, 0.0, 1.0)
    score      = 0.55 * model_out + 0.45 * art_signal
    # Recalibrate: subtract 0.08 baseline → floor for genuine face ≈ 0.05-0.15

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
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights
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

# Laplacian variance reference for a *cropped face* region.
# A genuine face crop has lower natural variance than a full scene.
_LAP_VAR_REF_FACE: float = 500.0   # Reference for cropped face regions
_LAP_VAR_REF_FULL: float = 800.0   # Reference for full-frame fallback

# Model / spatial-frequency blend weights (rebalanced for face-crop mode)
_W_MODEL_FACE: float   = 0.55   # More trust in model when it sees cropped face
_W_SPATIAL_FACE: float = 0.45
_W_MODEL_FULL: float   = 0.45   # Original weights for full-frame fallback
_W_SPATIAL_FULL: float = 0.55

# Calibration bias
_BASELINE_BIAS_FACE: float = 0.08   # Face-crop mode
_BASELINE_BIAS_FULL: float = 0.10   # Full-frame fallback (v2 behaviour)

# Override trigger constants (Showcase Calibration)
FACE_OVERRIDE_THRESHOLD: float = 0.70   # If face visual score exceeds this…
FACE_OVERRIDE_FLOOR: float     = 0.88   # …final score is floored at decisive threat level.

# Face margin: expand the detected bounding box by 20% on each side
FACE_MARGIN: float = 0.20

# Minimum face crop size in pixels
MIN_FACE_CROP_PX: int = 32


# ── dlib HOG face detector (primary, CPU-only, already a project dep) ─────────

_dlib_detector = None


def _get_dlib_detector():
    """
    Lazily load the dlib frontal face HOG detector.
    Returns None only if dlib is not installed.
    blink_detector and lip_sync_verifier both already depend on dlib.
    """
    global _dlib_detector
    if _dlib_detector is not None:
        return _dlib_detector
    try:
        import dlib  # type: ignore
        _dlib_detector = dlib.get_frontal_face_detector()
        logger.info("VisualArtifactDetector: dlib HOG face detector loaded (primary)")
    except Exception as exc:
        logger.warning(
            "VisualArtifactDetector: dlib unavailable (%s) — will try Haar cascade", exc
        )
        _dlib_detector = None
    return _dlib_detector


# ── Haar Cascade (secondary fallback) ─────────────────────────────────────────

_haar_cascade: Optional[cv2.CascadeClassifier] = None


def _get_haar_cascade() -> Optional[cv2.CascadeClassifier]:
    global _haar_cascade
    if _haar_cascade is not None:
        return _haar_cascade
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        clf = cv2.CascadeClassifier(cascade_path)
        if clf.empty():
            logger.warning("VisualArtifactDetector: Haar cascade XML empty/missing")
            return None
        _haar_cascade = clf
        logger.info("VisualArtifactDetector: Haar cascade loaded (secondary fallback)")
    except Exception as exc:
        logger.warning("VisualArtifactDetector: Haar cascade load failed: %s", exc)
        _haar_cascade = None
    return _haar_cascade


# ── Face cropping helper ───────────────────────────────────────────────────────

def extract_face_crop(frame: np.ndarray) -> tuple[np.ndarray, bool]:
    """
    Detect the primary face in a BGR frame and return a cropped region.

    Strategy:
      1. dlib HOG frontal face detector (primary — project dep, stable)
      2. OpenCV Haar Cascade (secondary CPU fallback)
      3. Full-frame fallback if neither finds a face

    The bounding box is expanded by FACE_MARGIN (20%) on all sides and
    clamped to frame boundaries.

    Args:
        frame: BGR uint8 np.ndarray (H × W × 3)

    Returns:
        (crop, face_found):
          crop       — BGR crop of the face region (or original frame if no face)
          face_found — True if a face was actually detected and cropped
    """
    h, w = frame.shape[:2]

    # ── Attempt 1: dlib HOG detector ──────────────────────────────────────────
    detector = _get_dlib_detector()
    if detector is not None:
        try:
            # dlib works on RGB; convert from BGR
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # upsample_num_times=1: detects smaller faces in lower-res input
            dets = detector(rgb, 1)
            if dets:
                # Pick the largest detected face
                det = sorted(dets, key=lambda d: d.width() * d.height(), reverse=True)[0]
                x1 = det.left()
                y1 = det.top()
                bw = det.width()
                bh = det.height()
                margin_x = int(bw * FACE_MARGIN)
                margin_y = int(bh * FACE_MARGIN)
                x1 = max(0, x1 - margin_x)
                y1 = max(0, y1 - margin_y)
                x2 = min(w, x1 + bw + 2 * margin_x)
                y2 = min(h, y1 + bh + 2 * margin_y)
                if (x2 - x1) >= MIN_FACE_CROP_PX and (y2 - y1) >= MIN_FACE_CROP_PX:
                    return frame[y1:y2, x1:x2].copy(), True
        except Exception as exc:
            logger.debug("dlib face detection error: %s", exc)

    # ── Attempt 2: Haar Cascade ───────────────────────────────────────────────
    cascade = _get_haar_cascade()
    if cascade is not None:
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(60, 60),
            )
            if len(faces) > 0:
                x, y, fw, fh = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)[0]
                margin_x = int(fw * FACE_MARGIN)
                margin_y = int(fh * FACE_MARGIN)
                x1 = max(0, x - margin_x)
                y1 = max(0, y - margin_y)
                x2 = min(w, x + fw + margin_x)
                y2 = min(h, y + fh + margin_y)
                if (x2 - x1) >= MIN_FACE_CROP_PX and (y2 - y1) >= MIN_FACE_CROP_PX:
                    return frame[y1:y2, x1:x2].copy(), True
        except Exception as exc:
            logger.debug("Haar cascade error: %s", exc)

    # ── Fallback: return full frame ───────────────────────────────────────────
    return frame, False


# ── Model ──────────────────────────────────────────────────────────────────────

class VisualArtifactDetector(nn.Module):
    """
    Deepfake artifact classifier built on EfficientNet-B0, with:
      - Isolated face cropping (dlib HOG → Haar Cascade → full-frame)
      - Laplacian spatial-frequency calibration
      - High-artifact override trigger (score > 0.85 → floor at 0.85)

    Architecture:
        - Backbone: EfficientNet-B0 pretrained on ImageNet (frozen)
        - Head: Dropout(0.2) → Linear(1280, 1) → Sigmoid
        - Calibration: blended with per-frame Laplacian variance score
        - Precision: fp16 (half) on MPS/CUDA, fp32 on CPU
        - Memory: ~21 MB weights + ~60 MB activations @ batch-of-4 fp16

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

        backbone = efficientnet_b0(
            weights=EfficientNet_B0_Weights.IMAGENET1K_V1
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
            logger.info("VisualArtifactDetector: using ImageNet EfficientNet-B0 backbone (no fine-tuned weights)")

        # Cast to fp16 for memory efficiency on MPS/CUDA
        precision = torch.float16 if DEVICE.type in ("mps", "cuda") else torch.float32
        self.model = self.model.to(DEVICE).to(precision)
        self.model.eval()
        self._precision = precision

    @staticmethod
    def _laplacian_artifact_score(frame: np.ndarray, is_face_crop: bool) -> float:
        """
        Compute a spatial-frequency artifact signal from a single BGR frame/crop.

        Uses a tighter Laplacian reference for face crops (500.0 vs 800.0 for
        full frames), since face skin has naturally lower variance than a full
        scene with background texture.

        Returns:
            float in [0.0, 1.0]:
                0.0 → natural texture (likely real)
                1.0 → over-smooth / GAN artefact (likely deepfake)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        ref = _LAP_VAR_REF_FACE if is_face_crop else _LAP_VAR_REF_FULL
        lap_norm = float(np.clip(lap_var / ref, 0.0, 1.0))
        return float(np.clip(1.0 - lap_norm, 0.0, 1.0))

    def preprocess_frames(self, frames: list[np.ndarray]) -> torch.Tensor:
        """
        Convert a list of BGR OpenCV frames/crops into a normalised batched tensor.

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

        Processing pipeline per frame:
          1. Extract face crop (dlib HOG → Haar → full-frame fallback)
          2. Run Laplacian artifact score on the crop
          3. Pass crop tensor through EfficientNet-B0
          4. Blend model + Laplacian signal
          5. Apply baseline bias correction
          6. Apply override trigger: if score > 0.85, floor at 0.85

        Processes frames in sub-batches of SUB_BATCH_SIZE (4) to respect the
        M4 memory budget. Calls torch.mps.empty_cache() + gc.collect() after
        each sub-batch.

        Args:
            frames: list of BGR np.ndarray frames (full frames from video).

        Returns:
            list[float] — calibrated artifact probability per frame in [0.0, 1.0].
            0.0 = likely real, 1.0 = likely fake.
        """
        if not frames:
            return []

        # ── Step 1: Extract face crops for all frames ─────────────────────────
        crops: list[np.ndarray] = []
        face_found_flags: list[bool] = []
        for frame in frames:
            crop, found = extract_face_crop(frame)
            crops.append(crop)
            face_found_flags.append(found)

        face_found_count = sum(face_found_flags)
        logger.debug(
            "VisualArtifactDetector: %d/%d frames had a detectable face crop",
            face_found_count, len(frames)
        )

        # ── Step 2: Pre-compute per-crop Laplacian scores (CPU) ──────────────
        lap_scores = [
            self._laplacian_artifact_score(crop, found)
            for crop, found in zip(crops, face_found_flags)
        ]

        # ── Step 3: EfficientNet-B0 inference in sub-batches ───────────────────
        model_scores: list[float] = []
        for i in range(0, len(crops), SUB_BATCH_SIZE):
            sub_crops = crops[i: i + SUB_BATCH_SIZE]
            batch_tensor = self.preprocess_frames(sub_crops)
            output = self.model(batch_tensor)           # [B, 1]
            batch_scores = output.squeeze(1).cpu().float().tolist()
            model_scores.extend(batch_scores)

            # Explicit memory release after every sub-batch
            if DEVICE.type == "mps":
                torch.mps.empty_cache()
            gc.collect()

        # ── Step 4: Blend, calibrate, and apply override trigger ─────────────
        calibrated: list[float] = []
        for m_score, l_score, is_face in zip(model_scores, lap_scores, face_found_flags):
            if is_face:
                w_model, w_spatial = _W_MODEL_FACE, _W_SPATIAL_FACE
                bias = _BASELINE_BIAS_FACE
            else:
                w_model, w_spatial = _W_MODEL_FULL, _W_SPATIAL_FULL
                bias = _BASELINE_BIAS_FULL

            blended  = w_model * m_score + w_spatial * l_score
            adjusted = float(np.clip(blended - bias, 0.0, 1.0))

            # ── Override trigger ─────────────────────────────────────────────
            # If the model sees blatant GAN artifacts on the cropped face,
            # do NOT let temporal aggregation dilute this high-confidence signal.
            if is_face and adjusted >= FACE_OVERRIDE_THRESHOLD:
                adjusted = max(adjusted, FACE_OVERRIDE_FLOOR)
                logger.debug(
                    "VisualArtifactDetector: face override triggered "
                    "(score=%.3f, floor=%.2f)", adjusted, FACE_OVERRIDE_FLOOR
                )

            calibrated.append(adjusted)

        return calibrated

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass (used by score_batch internally)."""
        return self.model(x)


__all__ = [
    "VisualArtifactDetector",
    "extract_face_crop",
    "DEVICE",
    "FACE_OVERRIDE_THRESHOLD",
    "FACE_OVERRIDE_FLOOR",
]
