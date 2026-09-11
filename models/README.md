# AI Model Assets

This directory holds binary model files that are **not tracked by git** (see `.gitignore`).

## Required Files

### 1. `face_landmarker.task` — MediaPipe Face Landmark Detection
Used by: `ai_engine/deepfake/lip_sync_verifier.py`, `ai_engine/deepfake/blink_detector.py`

**Download (3.6 MB):**
```bash
curl -L "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" \
     -o models/face_landmarker.task
```

### 2. `shape_predictor_68_face_landmarks.dat` — dlib 68-point Face Landmark Predictor
Used by: `ai_engine/deepfake/lip_sync_verifier.py`, `ai_engine/deepfake/blink_detector.py`

> ⚠️ **Note:** MediaPipe ≥ 0.10.30 crashes on macOS arm64 (known DrishtiMetal bug). dlib is used as the stable CPU-only replacement.

**Download (95 MB):**
```bash
# Official dlib model from the project author's Dropbox
curl -L "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2" \
     -o models/shape_predictor_68_face_landmarks.dat.bz2 && \
     bzip2 -d models/shape_predictor_68_face_landmarks.dat.bz2
```

### 3. `llama-3.2-3b-instruct-q4_k_m.gguf` — LLaMA 3.2 3B Instruct (4-bit)
Used by: `ai_engine/phishing/llm_analyzer.py` — LLM-powered phishing intent classification.

**Download (~2 GB):**
```bash
# Option A: Hugging Face CLI (recommended)
pip install huggingface_hub
huggingface-cli download bartowski/Llama-3.2-3B-Instruct-GGUF \
    Llama-3.2-3B-Instruct-Q4_K_M.gguf \
    --local-dir models/

# Option B: Direct curl (may be slow)
curl -L "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf" \
     -o "models/llama-3.2-3b-instruct-q4_k_m.gguf"
```

Set the env variable to match your filename:
```bash
export GGUF_MODEL_PATH="models/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
```

## Fallback Behaviour

| Model | Missing Behaviour |
|---|---|
| `face_landmarker.task` | Lip-sync and blink detectors return 0 / suspicious=True. Visual detector still works. |
| `*.gguf` | Phishing analysis falls back to URL heuristics + header analysis only (no LLM intent scoring). |

> [!NOTE]
> The system is designed to degrade gracefully. All endpoints remain reachable even without model files.
