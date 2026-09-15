# 🛡️ AI-Powered Real-Time Deepfake & Phishing Detection — Defense System

> **Enterprise Platform** | Zero-Trust Cybersecurity Architecture | Real-Time GenAI Threat Detection  
> **Target Hardware:** Apple Silicon M-Series (M1/M2/M3/M4 with MPS) · NVIDIA CUDA (11.8/12.x) · Universal CPU Fallback  
> **Lead Architect:** Sanyam Gehlot · **Collaborator & Core Contributor:** [Alefiya](https://github.com/alefiya12)  
> **Status:** ✅ **Production / Launch Ready** (100% Test Suite Pass Rate: 26/26 Launch Checks · 22/22 UI/UX Audits)

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Component Architecture Diagram](#component-architecture-diagram)
3. [Technology Stack](#technology-stack)
4. [Repository File Structure](#repository-file-structure)
5. [Phase-by-Phase Development Roadmap (Completed)](#phase-by-phase-development-roadmap-completed)
6. [Cross-Modal Verification Engine — Core Pipeline](#cross-modal-verification-engine--core-pipeline)
7. [Hardware Acceleration & Memory Constraints](#hardware-acceleration--memory-constraints)
8. [Automated Verification & Launch Audit Results](#automated-verification--launch-audit-results)
9. [Dependency Manifest](#dependency-manifest)

---

## System Overview

DEFENCESYS is an **enterprise-grade, zero-trust, real-time GenAI threat defense platform** purpose-built to neutralize next-generation synthetic identity manipulation, social engineering, and targeted credential theft. The system features four synchronized defense vectors:

| Vector | Mechanism | Core Technology Stack |
|---|---|---|
| 🎥 **Deepfake Detection** | Real-time cross-modal video/audio coherence analysis — temporal lip-sync cross-correlation, Eye Aspect Ratio (EAR) blink dynamics, and deep visual artifact classification. Features live camera capture + canvas synthetic simulation feed. | PyTorch (Apple Metal MPS / CUDA) · MobileNetV2 · MediaPipe · dlib · Librosa |
| 🎣 **Phishing Defense** | Multilayered intent classification, Shannon URL entropy scoring, Cyrillic/homoglyph Punycode spoofing detection, and email header forensics (SPF, DKIM, DMARC, display-name spoofing). | Quantized LLaMA 3.2 3B (4-bit GGUF) · `llama-cpp-python` · Regex & Heuristics |
| 🔐 **Identity Vault & Attestation** | Hardware-grade cryptographic attestation for every AI-generated verdict. Every frame assessment, scan report, and risk score is signed using ECDSA P-256 for mathematical non-repudiation. | ECDSA P-256 · Python `cryptography` · SHA-256 |
| 🕸️ **Threat Graph Correlation** | Real-time graph correlation of threat actors, phishing domains, IP addresses, attacked mailboxes, and coordinated multi-vector campaigns. | Neo4j 5 Community · Cypher Query Language · `py2neo` · D3.js Force Simulation |

---

## Component Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                    AI DEEPFAKE & PHISHING DEFENCE SYSTEM                        ║
║                     Zero-Trust Enterprise Security Platform                      ║
╚══════════════════════════════════════════════════════════════════════════════════╝

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                   DJANGO SOC COMMAND DASHBOARD (PORT 8000)                  │
  │            (Pure Pitch-Black UI · HTML5 Canvas HUD · Vanilla JS WebSockets)  │
  │                                                                              │
  │  ┌─────────────┐  ┌───────────────┐  ┌──────────────┐  ┌────────────────┐  │
  │  │ Live Video  │  │ Threat Graph  │  │  Alert Feed  │  │ Identity Vault │  │
  │  │   Monitor   │  │  Visualizer   │  │  (WebSocket) │  │  (ECDSA Keys)  │  │
  │  └──────┬──────┘  └───────┬───────┘  └──────┬───────┘  └───────┬────────┘  │
  └─────────┼─────────────────┼─────────────────┼──────────────────┼───────────┘
            │ WebSocket/REST  │ REST / Graph     │ WS Alert Stream  │ REST Key Export
            ▼                 ▼                  ▼                  ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                     DJANGO ASGI ORCHESTRATION LAYER                          │
  │                  Daphne 4.x · Django Channels · Celery · Redis              │
  │                                                                              │
  │  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  ┌────────────────┐ │
  │  │  WebSocket   │  │  REST API     │  │  Task Queue  │  │   Auth &       │ │
  │  │  Consumer    │  │  (DRF Views)  │  │  (Celery +   │  │   ECDSA Token  │ │
  │  │  (Channels)  │  │               │  │   Redis)     │  │   Service      │ │
  │  └──────┬───────┘  └──────┬────────┘  └──────┬───────┘  └───────┬────────┘ │
  └─────────┼─────────────────┼─────────────────-┼──────────────────┼──────────┘
            │  Frame Chunks   │  Scan Requests    │  Async Jobs      │  Tokens
            ▼                 ▼                   ▼                  ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                   AI ENGINE MICROSERVICES LAYER (PORT 8001)                  │
  │                     FastAPI · Uvicorn · PyTorch MPS / CUDA                  │
  │                                                                              │
  │  ┌────────────────────────────────┐   ┌───────────────────────────────────┐ │
  │  │   CROSS-MODAL VERIFICATION     │   │    PHISHING DETECTION ENGINE      │ │
  │  │         ENGINE                 │   │                                   │ │
  │  │                                │   │  ┌─────────────────────────────┐  │ │
  │  │  ┌──────────────────────────┐  │   │  │  URL & Header Forensics     │  │ │
  │  │  │  Visual Artifact Detector│  │   │  │  (Entropy + Homoglyphs)     │  │ │
  │  │  │  (MobileNetV2 · MPS)     │  │   │  └─────────────────────────────┘  │ │
  │  │  └──────────────────────────┘  │   │  ┌─────────────────────────────┐  │ │
  │  │  ┌──────────────────────────┐  │   │  │  LLM Intent Analyser        │  │ │
  │  │  │  Lip-Sync Verifier       │  │   │  │  (Llama 3.2 3B Q4_K_M GGUF) │  │ │
  │  │  │  (MediaPipe · Librosa)   │  │   │  └─────────────────────────────┘  │ │
  │  │  └──────────────────────────┘  │   │  ┌─────────────────────────────┐  │ │
  │  │  ┌──────────────────────────┐  │   │  │  ECDSA Result Attestation   │  │ │
  │  │  │  Blink & Gaze Detector   │  │   │  │  (P-256 Tamper-Proof Hex)   │  │ │
  │  │  │  (EAR FaceMesh / dlib)   │  │   │  └─────────────────────────────┘  │ │
  │  │  └──────────────────────────┘  │   └───────────────────────────────────┘ │
  │  │  ┌──────────────────────────┐  │                                          │
  │  │  │  ECDSA Verdict Signer    │  │                                          │
  │  │  └──────────────────────────┘  │                                          │
  │  └────────────────────────────────┘                                          │
  └─────────────────────────────────────────────────────────────────────────────┘
            │  Verdicts + Audits                  │  Threat Campaigns
            ▼                                     ▼
  ┌────────────────────────┐          ┌───────────────────────────────┐
  │       PostgreSQL       │          │             Neo4j             │
  │   (Relational Store)   │          │       (Threat Graph DB)       │
  │                        │          │                               │
  │  • Users & RBAC        │          │  (Session)──[INVOLVES]──>(IP) │
  │  • Scan Telemetry      │          │       │                       │
  │  • Forensic Breakdowns │          │   [PART_OF]                   │
  │  • ECDSA Key Records   │          │       │                       │
  └────────────────────────┘          │  (Campaign)──[TARGETS]──>(Org)│
                                      └───────────────────────────────┘
```

---

## Technology Stack

### AI / ML Pipeline
| Package | Version | Purpose |
|---|---|---|
| `torch` | ≥2.3 (MPS & CUDA) | Hardware-accelerated tensor computation on Apple Silicon & NVIDIA |
| `torchvision` | ≥0.18 | MobileNetV2 pretrained backbone for visual artifact analysis |
| `opencv-python` | ≥4.9 | Frame decomposition, scaling, color conversions, and OpenCV stream pipeline |
| `mediapipe` | ≥0.10 | FaceMesh 468-point landmarks, lip contour tracking |
| `dlib` | ≥19.24 | Robust fallback 68-point facial landmark predictor |
| `librosa` | ≥0.10 | Audio energy RMS envelope, spectral analysis, MFCC extraction |
| `llama-cpp-python` | ≥0.2 | Quantized 4-bit LLaMA 3.2 3B Instruct local LLM inference |
| `cryptography` | ≥42.0 | ECDSA P-256 curve key generation, verification, and SHA-256 signatures |

### Backend & Orchestration
| Package | Version | Purpose |
|---|---|---|
| `django` | 4.2 (LTS) | Core enterprise web framework and ORM |
| `djangorestframework` | ≥3.15 | Secure REST API endpoints, serializers, authentication views |
| `channels` | ≥4.0 | Real-time bi-directional WebSocket streaming (ASGI) |
| `channels-redis` | ≥4.2 | Redis-backed Channel layer for high-throughput frame distribution |
| `celery` | ≥5.4 | Distributed asynchronous task queue for deep learning inference |
| `psycopg2-binary` | ≥2.9 | High-performance PostgreSQL database adapter |
| `py2neo` | ≥2021.2 | Neo4j graph database driver for Cypher query generation |
| `redis` | ≥5.0 | Celery message broker and distributed in-memory cache |
| `daphne` | ≥4.1 | Twisted-based ASGI production HTTP/WebSocket server |

### Frontend & SOC Dashboard
| Component | Implementation |
|---|---|
| Native Templates | Server-side rendered Django HTML5 templates with zero client framework bloat |
| Design System | Tailwind CSS with pure pitch-black theme (`dark:bg-black`, `dark:bg-zinc-950`) |
| Client Streaming | Vanilla JavaScript WebSocket client (`ws_client.js`) and webcam manager (`webcam_stream.js`) |
| Real-Time HUD | Dynamic HTML5 Canvas rendering face bounding box, landmark mesh, and live telemetry |
| Threat Graph UI | Interactive D3.js force-directed graph visualizer (`graph_visualizer.js`) |

---

## Repository File Structure

```
ai-defence-system/
│
├── README.md                          ← Comprehensive Enterprise Documentation & Quickstart
├── About.md                           ← Architecture & Engineering Blueprint (This file)
├── LICENSE                            ← MIT Open-Source License
├── SECURITY.md                        ← Responsible Disclosure & Security Policy
├── .env.example                       ← Environment variable template
├── .gitignore                         ← Production gitignore (weights, venvs, DBs, keys)
├── docker-compose.yml                 ← PostgreSQL 16 + Redis 7 + Neo4j 5 Infrastructure
│
├── backend/                           ← Django ASGI Orchestration Layer
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/                        ← Application Configuration Package
│   │   ├── __init__.py
│   │   ├── asgi.py                    ← ASGI Protocol Router (HTTP + WebSockets)
│   │   ├── wsgi.py                    ← WSGI Gateway
│   │   ├── celery.py                  ← Celery Configuration & Broker Setup
│   │   ├── urls.py                    ← Top-Level Route Dispatcher
│   │   └── settings/
│   │       ├── __init__.py
│   │       ├── base.py                ← Core Shared Settings
│   │       ├── development.py         ← Local Dev Settings (MPS/Docker defaults)
│   │       └── production.py          ← Hardened Production Settings
│   │
│   ├── apps/                          ← Modular Domain Applications
│   │   ├── core/                      ← Shared Utilities, Alert Channels, Base Models
│   │   │   ├── consumers.py           ← Global Alert WebSocket Feed
│   │   │   ├── models.py
│   │   │   └── utils.py
│   │   │
│   │   ├── deepfake/                  ← Deepfake Detection Application
│   │   │   ├── consumers.py           ← Real-Time Video Frame Stream WebSocket Consumer
│   │   │   ├── models.py              ← ScanSession, FrameAnalysis, AudioChunk Models
│   │   │   ├── serializers.py
│   │   │   ├── tasks.py               ← Async Celery Dispatcher to AI Engine
│   │   │   ├── urls.py
│   │   │   └── views.py               ← Video Upload & Monitor Views
│   │   │
│   │   ├── phishing/                  ← Phishing Analysis Application
│   │   │   ├── models.py              ← PhishingScan, URLAnalysis Models
│   │   │   ├── serializers.py
│   │   │   ├── tasks.py               ← Async Phishing Assessment Dispatcher
│   │   │   ├── urls.py
│   │   │   └── views.py               ← Scanner Form & REST APIs
│   │   │
│   │   ├── identity/                  ← Cryptographic Identity Vault
│   │   │   ├── models.py              ← ECDSAKey, SignedVerdict
│   │   │   ├── services.py            ← Key Management, P-256 Signatures, Verification
│   │   │   ├── urls.py
│   │   │   └── views.py               ← Key Management & Verification Views
│   │   │
│   │   └── threat_graph/              ← Neo4j Intelligence Integration
│   │       ├── graph_client.py        ← Neo4j Connection, Cypher Queries, Entity Creation
│   │       ├── models.py
│   │       ├── serializers.py
│   │       ├── urls.py
│   │       └── views.py               ← Interactive Graph REST API
│   │
│   ├── templates/                     ← Django Native Templates
│   │   ├── base.html                  ← Master Layout with Theme Toggle & Navigation
│   │   ├── dashboard/
│   │   │   └── index.html             ← Central SOC Command Dashboard
│   │   ├── deepfake/
│   │   │   └── monitor.html           ← Dual-Mode Deepfake Monitor (Live + Upload)
│   │   ├── phishing/
│   │   │   └── scanner.html           ← Phishing Forensics & URL Analyzer
│   │   ├── threat_graph/
│   │   │   └── view.html              ← Interactive Neo4j D3.js Graph Visualizer
│   │   └── identity/
│   │       ├── login.html             ← Secure SOC Login
│   │       ├── register.html          ← Analyst Registration
│   │       └── vault.html             ← ECDSA Cryptographic Identity Vault
│   │
│   └── static/                        ← Production Static Assets
│       ├── css/
│       │   └── custom.css             ← Custom HUD and Glassmorphism Styles
│       └── js/
│           ├── theme_toggle.js        ← Pitch-Black Theme Controller (Zero Blue Tint)
│           ├── ws_client.js           ← Resilient Channels WebSocket Client
│           ├── webcam_stream.js       ← Live Camera & Synthetic Feed HUD Controller
│           └── graph_visualizer.js    ← D3.js Force Simulation Engine
│
├── ai_engine/                         ← Standalone High-Throughput AI Microservice
│   ├── server.py                      ← FastAPI Uvicorn Server (Ports & Endpoints)
│   ├── config.py                      ← Hardware Accelerator, Model Paths, Thresholds
│   ├── requirements.txt
│   │
│   ├── deepfake/
│   │   ├── cross_modal_engine.py      ← Orchestrator (Visual + Lip-Sync + Blink + ECDSA)
│   │   ├── visual_detector.py         ← MobileNetV2 Binary Classifier (MPS/CUDA)
│   │   ├── audio_analyzer.py          ← Librosa RMS Energy & MFCC Feature Extractor
│   │   ├── lip_sync_verifier.py       ← Cross-Correlation of Lip Motion & Audio Waveforms
│   │   ├── blink_detector.py          ← Eye Aspect Ratio (EAR) Anomaly Scoring
│   │   └── frame_preprocessor.py      ← High-Speed OpenCV Frame Normalization
│   │
│   ├── phishing/
│   │   ├── llm_analyzer.py            ← LLaMA 3.2 3B 4-bit GGUF Classifier
│   │   ├── url_forensics.py           ← Shannon Entropy & Homoglyph Engine
│   │   ├── header_analyzer.py         ← SPF, DKIM, DMARC, Header Discrepancy Verifier
│   │   └── verdict_signer.py          ← Cryptographic Attestation Generator
│   │
│   └── identity/
│       └── ecdsa_service.py           ← P-256 Key Pair Lifecycle & Signature Verifier
│
├── models/                            ← AI Model Weights Directory
│   ├── README.md                      ← Download Instructions & Fallback Specs
│   ├── face_landmarker.task           ← MediaPipe Face Landmark Model
│   ├── shape_predictor_68_face_landmarks.dat ← dlib 68-Point Landmark Model
│   └── Llama-3.2-3B-Instruct-Q4_K_M.gguf   ← 4-Bit Quantized Local LLM
│
└── scripts/                           ← Automation & Verification Suite
    ├── run_dev.sh                     ← Unified Local Development Server Launcher
    ├── setup_env.sh                   ← One-Shot Environment Bootstrap Script
    ├── download_models.sh             ← HuggingFace GGUF Model Downloader
    ├── verify_full_ui.py              ← Full 22-Point End-to-End Test Suite
    ├── verify_ui_launch.py            ← 26-Point Commercial Launch Readiness Audit
    └── audit_system.py                ← Deep Architecture & Dependency Inspector
```

---

## Phase-by-Phase Development Roadmap (Completed)

### 🏁 Phase 1 — Foundation & Infrastructure
- [x] Initialized Django architecture with clean `config/settings/` split (`base`, `development`, `production`).
- [x] Implemented PostgreSQL schema and relational models across all apps (`core`, `deepfake`, `phishing`, `identity`, `threat_graph`).
- [x] Configured Django Channels 4.x ASGI protocol router backed by Redis channel layer.
- [x] Configured Celery 5.4 worker pool with distributed Redis broker.
- [x] Built Neo4j graph integration client (`graph_client.py`) for threat topology correlation.
- [x] Implemented ECDSA P-256 key generation, export, and verification services.
- [x] Packaged containerized PostgreSQL 16, Redis 7, and Neo4j 5 Community in `docker-compose.yml`.

### 🤖 Phase 2 — AI Core Engines
- [x] Built `VisualArtifactDetector` using MobileNetV2 with MPS / CUDA / CPU automatic hardware selection.
- [x] Built `AudioAnalyzer` with Librosa RMS energy and MFCC feature extraction.
- [x] Built `LipSyncVerifier` calculating cross-correlation delay between visual aperture and acoustic energy (threshold > 80ms).
- [x] Built `BlinkRateDetector` with Eye Aspect Ratio (EAR) tracking (physiological normal: 8–30 BPM).
- [x] Integrated `CrossModalVerificationEngine` aggregating multi-modal signals into a unified confidence metric with cryptographic ECDSA signatures.
- [x] Implemented `LLMAnalyzer` executing local quantized LLaMA 3.2 3B (4-bit GGUF) via `llama-cpp-python`.
- [x] Implemented `URLForensics` assessing Shannon entropy, Punycode/homoglyph spoofing (`xn--...`), and subdomain hierarchy.
- [x] Built `HeaderAnalyzer` detecting SPF, DKIM, and Display Name spoofing discrepancies.
- [x] Exposed FastAPI microservice on Port 8001 with health checks, stream buffers, and file scan endpoints.

### 🔗 Phase 3 — Integration & Real-Time Streaming
- [x] Connected Daphne ASGI WebSocket consumer (`/ws/deepfake/<session_id>/`) with Celery async inference pipeline.
- [x] Built `deepfake/monitor.html` with dual-mode operational views (Live Camera Stream + Media File Upload).
- [x] Implemented dynamic HTML5 Canvas HUD rendering facial bounding boxes, real-time FPS, and ECDSA verification badges.
- [x] Added **Synthetic Simulation Feed** (`startSyntheticStream`) generating an animated 12 FPS test pattern for camera-less testing environments.
- [x] Implemented graceful audio fallback when microphone permissions are denied.
- [x] Built `phishing/scanner.html` supporting raw email text, URL inspection, and full threat breakdown metrics.
- [x] Built `threat_graph/view.html` featuring interactive D3.js force simulation of attack infrastructure.
- [x] Built `identity/vault.html` for cryptographic key lifecycle management and PEM certificate inspection.

### 🏆 Phase 4 — Polish, Security Hardening & Commercial Launch
- [x] Overhauled UI design system to pure pitch-black (`dark:bg-black`, `dark:bg-zinc-950`) eliminating all blue background bleeding.
- [x] Built bulletproof, flash-free theme toggle engine with inline script execution and `localStorage` state persistence.
- [x] Optimized Celery frame buffer from 25 to 12 frames, cutting real-time AI dispatch latency down to ~1.0 second.
- [x] Validated Apple Silicon Metal Performance Shaders (MPS) memory footprint (< 3.2 GB peak).
- [x] Created full automated test suite: `scripts/verify_full_ui.py` (22/22 passed).
- [x] Created launch readiness audit suite: `scripts/verify_ui_launch.py` (26/26 passed).
- [x] Cleaned repository structure, added enterprise CI workflows, security policies, and documentation.

---

## Cross-Modal Verification Engine — Core Pipeline

The deepfake detection pipeline evaluates the temporal and physical coherence across three distinct sensory layers:

```
Video Stream / File Chunk
         │
         ├───▶ Visual Artifact Detector (MobileNetV2 @ fp16 MPS) ────▶ Visual Artifact Score (0.0 - 1.0)
         │
         ├───▶ Face Landmark Extractor (MediaPipe / dlib)
         │         │
         │         ├───▶ Lip Aperture Signal ────────┐
         │         │                                 ▼
         │         │                        Cross-Correlation ───────▶ Lip-Sync Lag (ms)
         │         │                                 ▲
         ├───▶ Audio Feature Extractor (Librosa) ────┘
         │
         └───▶ Eye Aspect Ratio (EAR) Signal ────────────────────────▶ Blink Frequency (BPM)
                                                                               │
                                                                               ▼
                                                            Multi-Modal Confidence Aggregator
                                                                               │
                                                                               ▼
                                                            ECDSA P-256 Cryptographic Signature
```

### Signal Weighting & Decision Boundary
The multi-modal aggregator calculates the overall threat confidence score $C \in [0.0, 1.0]$ using empirical forensic weights:

$$C = (0.40 \times S_{\text{visual}}) + (0.35 \times S_{\text{lip\_sync}}) + (0.25 \times S_{\text{blink}})$$

Where:
- $S_{\text{visual}}$: Probability of visual artifacts generated by MobileNetV2.
- $S_{\text{lip\_sync}}$: Binary flag triggered when cross-correlation delay exceeds the $80\text{ ms}$ threshold.
- $S_{\text{blink}}$: Binary flag triggered when blink frequency falls outside the physiological range ($8.0 \le \text{BPM} \le 30.0$).
- **Verdict Rule:** If $C \ge 0.55$, the media is classified as `SUSPICIOUS / DEEPFAKE`; otherwise, it is authenticated as `AUTHENTIC MEDIA`.

### Programmatic Usage Example
```python
from pathlib import Path
import numpy as np
from ai_engine.deepfake.cross_modal_engine import CrossModalVerificationEngine

# Initialize the engine (auto-detects MPS -> CUDA -> CPU)
engine = CrossModalVerificationEngine()

# Analyze frame sequence and audio chunk
verdict = engine.analyze(
    session_id="soc-stream-4412",
    frames=[...],             # list of BGR OpenCV frames
    audio_bytes=b"...",       # 16-bit mono PCM bytes
    fps=25.0,
    sample_rate=16000,
)

print(f"Verdict: {'DEEPFAKE' if verdict.is_deepfake else 'AUTHENTIC'}")
print(f"Confidence: {verdict.confidence:.2%}")
print(f"ECDSA Signature: {verdict.signed_verdict}")
```

---

## Hardware Acceleration & Memory Constraints

DEFENCESYS is engineered to run seamlessly across heterogeneous compute environments while respecting strict memory limits:

| Environment | Primary Accelerator | Memory Profile | Optimizations Applied |
|---|---|---|---|
| **Apple Silicon (M1/M2/M3/M4)** | Metal Performance Shaders (`mps`) | ≤ 3.5 GB Unified Memory | `fp16` half-precision, sub-batches of 4, aggressive `torch.mps.empty_cache()` |
| **NVIDIA GPU (Linux/Windows)** | CUDA 11.8 / 12.x | ≤ 4.0 GB VRAM | `torch.cuda.amp.autocast`, pinned host memory, non-blocking transfers |
| **Universal CPU Fallback** | Multi-threaded AVX2/AVX-512 | ≤ 2.0 GB RAM | Downscaled frame resolution (224x224), quantized 4-bit GGUF LLM |

---

## Automated Verification & Launch Audit Results

Every core feature, endpoint, security barrier, and user interface component has been verified through automated test suites:

### 1. Launch Readiness Audit (`scripts/verify_ui_launch.py`) — 26/26 PASS (100%)
- **Template Rendering:** `base.html`, `dashboard/index.html`, `deepfake/monitor.html`, `phishing/scanner.html`, `threat_graph/view.html`, `identity/login.html`, `identity/register.html`.
- **RBAC & Route Protection:** 302 redirects for unauthenticated requests, 200 OK for authenticated security analysts.
- **Static Assets & Scripts:** `theme_toggle.js`, `ws_client.js`, `webcam_stream.js`, `graph_visualizer.js`.
- **WebSocket Protocol Handshakes:** ASGI routing verified for `ws/alerts/` and `ws/deepfake/<session_id>/`.
- **REST Telemetry Endpoints:** AI Engine proxy, Threat Graph query API, Neo4j health check, Deepfake sessions, Phishing scan logs.

### 2. Full UI/UX Verification Suite (`scripts/verify_full_ui.py`) — 22/22 PASS (100%)
- **Cross-Modal Attention:** Lip-sync offset correlation, Eye Aspect Ratio blink calculations.
- **Cryptographic Attestation:** ECDSA P-256 signing and tamper-proof verification.
- **Phishing Engine:** URL homoglyph detection, Shannon entropy calculations, header anomaly detection.

---

## Dependency Manifest

The complete dependency manifest is version-pinned and split across the orchestration backend and the AI compute engine:
- Backend: [`backend/requirements.txt`](file:///Users/sanyamgehlot/Desktop/Main/My%20Projects/AI%20Deepfake%20and%20Phishing%20Defence%20System/backend/requirements.txt)
- AI Microservice: [`ai_engine/requirements.txt`](file:///Users/sanyamgehlot/Desktop/Main/My%20Projects/AI%20Deepfake%20and%20Phishing%20Defence%20System/ai_engine/requirements.txt)

---

*Authored by Sanyam Gehlot & [Alefiya](https://github.com/alefiya12) · Enterprise AI & Cybersecurity Architecture*
