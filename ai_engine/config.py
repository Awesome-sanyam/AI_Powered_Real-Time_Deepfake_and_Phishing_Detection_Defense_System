"""
AI Engine configuration — centralised settings loaded from environment.
All services read from this module instead of accessing os.environ directly.
"""
from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ── Device ────────────────────────────────────────────────────────────────────
DEVICE = os.environ.get("TORCH_DEVICE", "mps")   # mps | cuda | cpu

# ── Vision model ──────────────────────────────────────────────────────────────
VISION_WEIGHTS_PATH = os.environ.get("VISION_WEIGHTS_PATH", "")
VISION_BATCH_SIZE = int(os.environ.get("VISION_BATCH_SIZE", 4))
VISION_INPUT_SIZE = int(os.environ.get("VISION_INPUT_SIZE", 224))

# ── LLM / GGUF ────────────────────────────────────────────────────────────────
GGUF_MODEL_PATH = os.environ.get(
    "GGUF_MODEL_PATH",
    "models/llama-3.2-3b-instruct-q4_k_m.gguf",
)
LLM_N_CTX = int(os.environ.get("LLM_N_CTX", 512))
LLM_N_THREADS = int(os.environ.get("LLM_N_THREADS", 4))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", 256))

# ── ECDSA ─────────────────────────────────────────────────────────────────────
ECDSA_PRIVATE_KEY_PEM = os.environ.get("ECDSA_PRIVATE_KEY_PEM", "")

# ── Deepfake thresholds ───────────────────────────────────────────────────────
LIP_SYNC_THRESHOLD_MS = float(os.environ.get("LIP_SYNC_THRESHOLD_MS", 80.0))
MIN_BLINK_BPM = float(os.environ.get("MIN_BLINK_BPM", 8.0))
MAX_BLINK_BPM = float(os.environ.get("MAX_BLINK_BPM", 30.0))
DEEPFAKE_CONFIDENCE_THRESHOLD = float(
    os.environ.get("DEEPFAKE_CONFIDENCE_THRESHOLD", 0.55)
)
