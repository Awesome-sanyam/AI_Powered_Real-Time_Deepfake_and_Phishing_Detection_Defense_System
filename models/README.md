# 🧠 AI Model Assets & Neural Weights Specification

This directory holds the pre-trained neural network weights, task graphs, and quantized language model binaries utilized by the **DEFENCESYS AI Microservice**.

> [!IMPORTANT]
> Binary weight files are deliberately excluded from Git tracking via `.gitignore` to keep repository size lean and prevent Git LFS bandwidth limits. Ensure all required models are downloaded before starting the AI microservice.

---

## 📋 Model Inventory & Technical Specifications

| Asset File | Architecture / Backbone | Parameters / Precision | Size | Primary Subsystem | Hardware Accelerator |
|---|---|---|---|---|---|
| **`face_landmarker.task`** | MediaPipe Face Mesh | 468 3D Landmarks (`fp16`) | 3.6 MB | `lip_sync_verifier.py`, `blink_detector.py` | CPU / GPU delegate |
| **`shape_predictor_68_face_landmarks.dat`** | Ensemble of Regression Trees (dlib) | 68 Facial Landmarks | 99.7 MB | Fallback Landmark Extractor | Multi-threaded CPU |
| **`Llama-3.2-3B-Instruct-Q4_K_M.gguf`** | LLaMA 3.2 Dense Transformer | 3.21B Params (`Q4_K_M` Quantized) | 2.02 GB | `llm_analyzer.py` (Phishing Intent) | Apple Metal (MPS) / CUDA / CPU |

---

## 📥 Download Instructions

### 1. MediaPipe Face Landmarker (`face_landmarker.task`)
Used for real-time extraction of 468 facial landmark coordinates, oral aperture calculation, and 3D eye aspect ratio measurement.

```bash
# Execute from repository root
curl -L "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" \
     -o models/face_landmarker.task
```

### 2. dlib 68-Point Face Landmark Predictor (`shape_predictor_68_face_landmarks.dat`)
Used as an ultra-reliable, POSIX-stable facial landmark predictor when MediaPipe experiences native driver conflicts on certain operating system builds.

```bash
# Execute from repository root
curl -L "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2" \
     -o models/shape_predictor_68_face_landmarks.dat.bz2 && \
     bzip2 -d models/shape_predictor_68_face_landmarks.dat.bz2
```

### 3. Meta LLaMA 3.2 3B Instruct — 4-bit Quantized (`Llama-3.2-3B-Instruct-Q4_K_M.gguf`)
Used by the Phishing Detection Engine for local, zero-leakage semantic analysis of suspicious emails, executive impersonation lures, and credential extortion attempts.

#### Option A: Hugging Face CLI (Recommended — Fast & Resumable)
```bash
pip install huggingface_hub
hf download bartowski/Llama-3.2-3B-Instruct-GGUF \
    Llama-3.2-3B-Instruct-Q4_K_M.gguf \
    --local-dir models/
```

#### Option B: Direct cURL Download
```bash
curl -L "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf" \
     -o "models/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
```

#### Option C: Automated Script
```bash
bash scripts/download_models.sh
```

---

## 🛡️ Model Integrity Verification (SHA-256)

Validate downloaded binaries against reference SHA-256 cryptographic checksums:

```bash
# macOS (shasum)
shasum -a 256 models/*

# Linux (sha256sum)
sha256sum models/*
```

---

## ⚙️ Memory Budgets & Runtime Allocation

| Asset | RAM / VRAM Footprint | Context Size (`n_ctx`) | Batch Limit | MPS / CUDA Offloading |
|---|---|---|---|---|
| `face_landmarker.task` | ~85 MB | N/A | 1 frame/pass | Automatic delegate |
| `shape_predictor_68_face_landmarks.dat` | ~120 MB | N/A | 1 frame/pass | Multi-threaded CPU |
| `Llama-3.2-3B-Instruct-Q4_K_M.gguf` | ~2.2 GB | 512 tokens | 1 prompt | Fully offloaded to GPU layers (`n_gpu_layers=-1`) |

---

## 🔄 Graceful Fallback Matrix

The DEFENCESYS architecture is designed with **defense-in-depth fault tolerance**. The system will never crash or return unhandled 500 exceptions if a model file is missing:

| Missing Model | Degraded Behavior | End-to-End Status |
|---|---|:---:|
| **`face_landmarker.task` missing** | Automatically routes landmark tracking to `shape_predictor_68_face_landmarks.dat` (dlib). If both are absent, lip-sync delay is marked as `suspicious=True` and visual artifact detection (MobileNetV2) proceeds normally. | ⚠️ **Degraded (Operational)** |
| **`Llama-3.2-3B-Instruct-Q4_K_M.gguf` missing** | Phishing scanner seamlessly bypasses LLM intent scoring and evaluates threats using regex heuristics, Shannon URL entropy, homoglyph mapping, and SPF/DKIM header forensics. | ⚠️ **Degraded (Operational)** |
| **All models present** | Full multi-modal temporal cross-correlation, biological blink tracking, and neural intent analysis. | ✅ **Optimal (100% Functionality)** |

---

## 🔧 Environment Configuration

Ensure your `.env` configuration file points to the correct paths:

```dotenv
# Models configuration
GGUF_MODEL_PATH=models/Llama-3.2-3B-Instruct-Q4_K_M.gguf
LLM_N_CTX=512
LLM_N_THREADS=4
LLM_MAX_TOKENS=256
```
