#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# download_models.sh — Download quantized GGUF LLM from Hugging Face
# Model: Llama-3.2-3B-Instruct (Q4_K_M) — ~2.0GB — fits in M4 memory budget
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="$PROJECT_ROOT/models"

echo "📥 Downloading quantized GGUF model..."
echo "   Target: $MODELS_DIR"
echo ""

MODEL_URL="https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
MODEL_FILE="$MODELS_DIR/llama-3.2-3b-instruct-q4_k_m.gguf"

if [ -f "$MODEL_FILE" ]; then
    echo "✅ Model already exists at $MODEL_FILE"
    exit 0
fi

if command -v wget >/dev/null; then
    wget -c "$MODEL_URL" -O "$MODEL_FILE" --progress=bar:force
elif command -v curl >/dev/null; then
    curl -L --progress-bar "$MODEL_URL" -o "$MODEL_FILE"
else
    echo "❌ Neither wget nor curl found. Install one and retry."
    exit 1
fi

echo ""
echo "✅ Model downloaded: $(du -sh "$MODEL_FILE" | cut -f1)"
echo ""
echo "Update .env:"
echo "  GGUF_MODEL_PATH=models/llama-3.2-3b-instruct-q4_k_m.gguf"
