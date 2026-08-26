"""
AI Engine — Centralised Configuration
======================================
Single source of truth for device selection, model paths, and all
runtime thresholds.

Device priority: MPS (Apple Silicon) → CUDA → CPU
All modules import `DEVICE`, `IS_MPS`, `DEVICE_NAME` from here.

Author: Sanyam Gehlot
"""
from __future__ import annotations

import logging
import os
import sys
from typing import NamedTuple

import torch

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


# ── Device Detection ──────────────────────────────────────────────────────────

class DeviceInfo(NamedTuple):
    device: torch.device
    name: str
    is_mps: bool
    is_cuda: bool
    is_cpu: bool


def detect_device() -> DeviceInfo:
    """
    Auto-detect the best available compute device.

    Priority: MPS (Apple Silicon Metal) → CUDA → CPU

    Performs two-step MPS check:
      1. torch.backends.mps.is_available()  — OS + hardware support
      2. torch.backends.mps.is_built()      — PyTorch compiled with MPS

    Returns:
        DeviceInfo named tuple with device, name string, and bool flags.
    """
    # Allow explicit override via environment
    override = os.environ.get("TORCH_DEVICE", "").lower().strip()
    if override in ("mps", "cuda", "cpu"):
        device = torch.device(override)
        logger.info(f"Device overridden via TORCH_DEVICE={override}")
        return DeviceInfo(
            device=device,
            name=override,
            is_mps=(override == "mps"),
            is_cuda=(override == "cuda"),
            is_cpu=(override == "cpu"),
        )

    # Auto-detect
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        # Smoke-test MPS with a tiny tensor to confirm it's functional
        try:
            _test = torch.ones(1, device="mps")
            del _test
            device = torch.device("mps")
            logger.info("✅ MPS (Apple Metal) device ACTIVE — using Apple Silicon GPU")
            return DeviceInfo(device=device, name="mps", is_mps=True, is_cuda=False, is_cpu=False)
        except Exception as exc:
            logger.warning(f"MPS reported available but smoke-test failed ({exc}) — falling back")

    if torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"✅ CUDA device ACTIVE — {gpu_name}")
        return DeviceInfo(device=device, name=f"cuda:{gpu_name}", is_mps=False, is_cuda=True, is_cpu=False)

    logger.warning("⚠️  No GPU found — running on CPU. Inference will be significantly slower.")
    return DeviceInfo(device=torch.device("cpu"), name="cpu", is_mps=False, is_cuda=False, is_cpu=True)


# Resolve device at import time — singleton used by all AI modules
_DEVICE_INFO: DeviceInfo = detect_device()

DEVICE: torch.device = _DEVICE_INFO.device
DEVICE_NAME: str = _DEVICE_INFO.name
IS_MPS: bool = _DEVICE_INFO.is_mps
IS_CUDA: bool = _DEVICE_INFO.is_cuda
IS_CPU: bool = _DEVICE_INFO.is_cpu


def get_device_report() -> dict:
    """Return a JSON-serialisable dict describing the current device state."""
    mps_available = torch.backends.mps.is_available()
    mps_built = torch.backends.mps.is_built()
    return {
        "device": DEVICE_NAME,
        "mps_available": mps_available,
        "mps_built": mps_built,
        "mps_active": IS_MPS,
        "cuda_available": torch.cuda.is_available(),
        "cuda_active": IS_CUDA,
        "python_version": sys.version.split()[0],
        "torch_version": torch.__version__,
    }


# ── Model Paths ────────────────────────────────────────────────────────────────

GGUF_MODEL_PATH: str = os.environ.get(
    "GGUF_MODEL_PATH",
    "models/llama-3.2-3b-instruct-q4_k_m.gguf",
)
VISION_WEIGHTS_PATH: str = os.environ.get("VISION_WEIGHTS_PATH", "")

# ── Inference Hyper-params ─────────────────────────────────────────────────────

VISION_BATCH_SIZE: int = int(os.environ.get("VISION_BATCH_SIZE", 4))  # max 4 on 16 GB
VISION_INPUT_SIZE: int = int(os.environ.get("VISION_INPUT_SIZE", 224))

LLM_N_CTX: int = int(os.environ.get("LLM_N_CTX", 512))        # context window
LLM_N_THREADS: int = int(os.environ.get("LLM_N_THREADS", 4))  # performance threads
LLM_MAX_TOKENS: int = int(os.environ.get("LLM_MAX_TOKENS", 256))

# ── ECDSA ─────────────────────────────────────────────────────────────────────

ECDSA_PRIVATE_KEY_PEM: str = os.environ.get("ECDSA_PRIVATE_KEY_PEM", "")

# ── Deepfake Thresholds ───────────────────────────────────────────────────────

LIP_SYNC_THRESHOLD_MS: float = float(os.environ.get("LIP_SYNC_THRESHOLD_MS", 80.0))
MIN_BLINK_BPM: float = float(os.environ.get("MIN_BLINK_BPM", 8.0))
MAX_BLINK_BPM: float = float(os.environ.get("MAX_BLINK_BPM", 30.0))
DEEPFAKE_CONFIDENCE_THRESHOLD: float = float(os.environ.get("DEEPFAKE_CONFIDENCE_THRESHOLD", 0.55))
