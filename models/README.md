# AI Model Weights

This directory stores large binary model files that are **excluded from git** via `.gitignore`.

## Required Models

### LLM (Phishing Detection)
**Llama-3.2-3B-Instruct Q4_K_M** (~2.0 GB)
```bash
./scripts/download_models.sh
```
Or manually from: https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF

### Vision Model (Deepfake Detection)
MobileNetV2 weights are **downloaded automatically** by torchvision on first run.
No manual download required.

## Memory Budget on M4 16GB

| Component | RAM Usage |
|---|---|
| Llama-3.2-3B Q4_K_M | ~2.0 GB |
| MobileNetV2 (MPS fp16) | ~50 MB |
| MediaPipe FaceMesh | ~30 MB |
| Django + Celery | ~200 MB |
| Neo4j (Docker) | ~512 MB |
| Redis (Docker) | ~50 MB |
| Flutter Desktop | ~100 MB |
| **Total Peak** | **~3.0 GB** |
| M4 Available | **16 GB** |
| **Headroom** | **~13 GB** ✅ |
