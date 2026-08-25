# 🛡️ AI-Powered Real-Time Deepfake & Phishing Detection — Defense System

> **Hackathon Project** | Zero-Trust Enterprise Security Platform | GenAI Threat Detection  
> **Target Hardware:** Apple Silicon M4 MacBook Air · 16GB Unified Memory  
> **Author:** Sanyam Gehlot

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Component Architecture Diagram](#component-architecture-diagram)
3. [Technology Stack](#technology-stack)
4. [Repository File Structure](#repository-file-structure)
5. [Phase-by-Phase Development Roadmap](#phase-by-phase-development-roadmap)
6. [Cross-Modal Verification Engine — Boilerplate](#cross-modal-verification-engine--boilerplate)
7. [Hardware & Memory Constraints](#hardware--memory-constraints)
8. [Dependency Manifest](#dependency-manifest)

---

## System Overview

This is a **zero-trust, real-time GenAI threat detection platform** with three primary defence vectors:

| Vector | Mechanism | Key Technology |
|---|---|---|
| 🎥 **Deepfake Detection** | Cross-modal video/audio analysis — lip-sync, blink rate, visual artifacts | PyTorch MPS · MediaPipe · Librosa |
| 🎣 **Phishing Detection** | LLM-powered intent & URL analysis, header forensics | Quantized LLaMA (4-bit GGUF) · llama-cpp-python |
| 🔐 **Identity Verification** | Cryptographic signing of all AI decisions | ECDSA · Python `cryptography` lib |
| 🕸️ **Threat Graph** | Entity-relationship mapping of attack campaigns | Neo4j · py2neo |

---

## Component Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                    AI DEEPFAKE & PHISHING DEFENCE SYSTEM                        ║
║                         Zero-Trust Security Platform                             ║
╚══════════════════════════════════════════════════════════════════════════════════╝

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         FLUTTER SOC DASHBOARD                               │
  │                          (Dart — Cross-Platform)                             │
  │                                                                              │
  │  ┌─────────────┐  ┌───────────────┐  ┌──────────────┐  ┌────────────────┐  │
  │  │ Live Video  │  │ Threat Graph  │  │  Alert Feed  │  │ Identity Vault │  │
  │  │   Monitor   │  │  Visualizer   │  │  (WebSocket) │  │  (ECDSA Keys)  │  │
  │  └──────┬──────┘  └───────┬───────┘  └──────┬───────┘  └───────┬────────┘  │
  └─────────┼─────────────────┼─────────────────┼──────────────────┼───────────┘
            │ WebSocket/REST  │ Cypher Queries   │ WS Push          │ REST
            ▼                 ▼                  ▼                  ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                     DJANGO BACKEND (Orchestration Layer)                     │
  │                  Django 4.x · DRF · Django Channels · Redis                 │
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
  │                      AI MICROSERVICES LAYER (Python)                         │
  │                                                                              │
  │  ┌────────────────────────────────┐   ┌───────────────────────────────────┐ │
  │  │   CROSS-MODAL VERIFICATION     │   │    PHISHING DETECTION ENGINE      │ │
  │  │         ENGINE                 │   │                                   │ │
  │  │                                │   │  ┌─────────────────────────────┐  │ │
  │  │  ┌──────────────────────────┐  │   │  │  URL & Header Forensics     │  │ │
  │  │  │  Visual Artifact Detector│  │   │  │  (regex + heuristics)       │  │ │
  │  │  │  (MobileNetV2 · MPS)     │  │   │  └─────────────────────────────┘  │ │
  │  │  └──────────────────────────┘  │   │  ┌─────────────────────────────┐  │ │
  │  │  ┌──────────────────────────┐  │   │  │  LLM Intent Analyser        │  │ │
  │  │  │  Lip-Sync Verifier       │  │   │  │  (Llama 4-bit GGUF / MPS)   │  │ │
  │  │  │  (MediaPipe · Librosa)   │  │   │  └─────────────────────────────┘  │ │
  │  │  └──────────────────────────┘  │   │  ┌─────────────────────────────┐  │ │
  │  │  ┌──────────────────────────┐  │   │  │  ECDSA Result Signing       │  │ │
  │  │  │  Blink & Gaze Detector   │  │   │  │  (Tamper-Proof Verdicts)    │  │ │
  │  │  │  (MediaPipe FaceMesh)    │  │   │  └─────────────────────────────┘  │ │
  │  │  └──────────────────────────┘  │   └───────────────────────────────────┘ │
  │  │  ┌──────────────────────────┐  │                                          │
  │  │  │  ECDSA Verdict Signer    │  │                                          │
  │  │  └──────────────────────────┘  │                                          │
  │  └────────────────────────────────┘                                          │
  └─────────────────────────────────────────────────────────────────────────────┘
            │  Verdicts + Entities                │  Threat Entities
            ▼                                     ▼
  ┌────────────────────────┐          ┌───────────────────────────────┐
  │     PostgreSQL          │          │           Neo4j               │
  │  (Relational Store)     │          │       (Threat Graph DB)       │
  │                         │          │                               │
  │  • Users & Sessions     │          │  (IP)──[SENT]──>(Email)      │
  │  • Scan Results         │          │    │                           │
  │  • Audit Logs           │          │  [PART_OF]                    │
  │  • ECDSA Keys           │          │    │                           │
  └────────────────────────┘          │  (Campaign)──[TARGETS]──>(Org)│
                                       └───────────────────────────────┘
```

---

## Technology Stack

### AI / ML Pipeline
| Package | Version | Purpose |
|---|---|---|
| `torch` | ≥2.3 (MPS) | Neural network inference on Apple Silicon |
| `torchvision` | ≥0.18 | MobileNetV2 pretrained models |
| `opencv-python` | ≥4.9 | Real-time frame decoding & preprocessing |
| `mediapipe` | ≥0.10 | FaceMesh, lip landmark extraction |
| `librosa` | ≥0.10 | Audio MFCC feature extraction |
| `llama-cpp-python` | ≥0.2 | 4-bit GGUF LLM for phishing analysis |
| `cryptography` | ≥42.0 | ECDSA key generation & signing |

### Backend & Orchestration
| Package | Version | Purpose |
|---|---|---|
| `django` | ≥4.2 (LTS) | Core web framework |
| `djangorestframework` | ≥3.15 | REST API serializers & views |
| `channels` | ≥4.0 | WebSocket streaming (ASGI) |
| `channels-redis` | ≥4.2 | Channel layer backend |
| `celery` | ≥5.4 | Async AI task dispatch |
| `psycopg2-binary` | ≥2.9 | PostgreSQL adapter |
| `py2neo` | ≥2021.2 | Neo4j graph driver |
| `redis` | ≥5.0 | Celery broker & Django cache |
| `daphne` | ≥4.1 | Production ASGI server |

### Frontend
| Tool | Purpose |
|---|---|
| Flutter 3.x | Cross-platform SOC Dashboard (Dart) |
| `web_socket_channel` | Real-time alert streaming |
| `fl_chart` | Threat analytics charts |
| `flutter_riverpod` | State management |
| `dio` | HTTP REST client |

### Infrastructure
| Service | Local Setup |
|---|---|
| PostgreSQL 16 | `brew install postgresql@16` |
| Neo4j 5 Community | Docker or `brew install neo4j` |
| Redis 7 | `brew install redis` |

---

## Repository File Structure

```
ai-defence-system/
│
├── About.md                          ← This document
├── .env.example                      ← Env var template
├── .gitignore
├── docker-compose.yml                ← Neo4j + Redis (optional local)
│
├── backend/                          ← Django Orchestration Layer
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/                       ← Project settings package
│   │   ├── __init__.py
│   │   ├── settings/
│   │   │   ├── base.py               ← Shared settings
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── asgi.py                   ← ASGI entry (Channels)
│   │   └── wsgi.py
│   │
│   ├── apps/
│   │   ├── core/                     ← Shared utilities, base models
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   └── utils.py
│   │   │
│   │   ├── deepfake/                 ← Deepfake scan API
│   │   │   ├── __init__.py
│   │   │   ├── consumers.py          ← Django Channels WebSocket consumer
│   │   │   ├── models.py             ← ScanSession, FrameAnalysis, AudioChunk
│   │   │   ├── serializers.py
│   │   │   ├── tasks.py              ← Celery tasks → AI microservice calls
│   │   │   ├── urls.py
│   │   │   └── views.py
│   │   │
│   │   ├── phishing/                 ← Phishing scan API
│   │   │   ├── __init__.py
│   │   │   ├── models.py             ← PhishingReport, EmailScan, URLAnalysis
│   │   │   ├── serializers.py
│   │   │   ├── tasks.py
│   │   │   ├── urls.py
│   │   │   └── views.py
│   │   │
│   │   ├── identity/                 ← ECDSA identity & token management
│   │   │   ├── __init__.py
│   │   │   ├── models.py             ← ECDSAKey, SignedVerdict
│   │   │   ├── serializers.py
│   │   │   ├── services.py           ← Key gen, sign, verify
│   │   │   ├── urls.py
│   │   │   └── views.py
│   │   │
│   │   └── threat_graph/             ← Neo4j integration
│   │       ├── __init__.py
│   │       ├── graph_client.py       ← py2neo connection & queries
│   │       ├── models.py             ← Graph entity definitions
│   │       ├── serializers.py
│   │       ├── urls.py
│   │       └── views.py
│   │
│   └── routing.py                    ← Channels URL routing
│
├── ai_engine/                        ← Python AI Microservices (standalone)
│   ├── requirements.txt
│   ├── config.py                     ← Device, model paths, thresholds
│   │
│   ├── deepfake/
│   │   ├── __init__.py
│   │   ├── cross_modal_engine.py     ← CORE: CrossModalVerificationEngine
│   │   ├── visual_detector.py        ← MobileNetV2 artifact detection
│   │   ├── audio_analyzer.py         ← Librosa MFCC extraction
│   │   ├── lip_sync_verifier.py      ← MediaPipe lip landmarks + audio sync
│   │   ├── blink_detector.py         ← FaceMesh blink rate analysis
│   │   └── frame_preprocessor.py     ← OpenCV frame pipeline (MPS-aware)
│   │
│   ├── phishing/
│   │   ├── __init__.py
│   │   ├── llm_analyzer.py           ← llama-cpp-python 4-bit GGUF inference
│   │   ├── url_forensics.py          ← URL parsing, entropy, homoglyph check
│   │   ├── header_analyzer.py        ← Email header SPF/DKIM forensics
│   │   └── verdict_signer.py         ← ECDSA signing of LLM output
│   │
│   ├── identity/
│   │   ├── __init__.py
│   │   └── ecdsa_service.py          ← Key lifecycle, sign, verify
│   │
│   └── server.py                     ← FastAPI/Uvicorn micro-server exposing AI endpoints
│
├── flutter_dashboard/                ← Flutter SOC Dashboard
│   ├── pubspec.yaml
│   ├── lib/
│   │   ├── main.dart
│   │   ├── app.dart                  ← MaterialApp, theme, routing
│   │   │
│   │   ├── core/
│   │   │   ├── constants.dart
│   │   │   ├── api_client.dart       ← Dio REST client
│   │   │   └── ws_client.dart        ← WebSocket channel client
│   │   │
│   │   ├── features/
│   │   │   ├── dashboard/
│   │   │   │   ├── dashboard_screen.dart
│   │   │   │   └── widgets/
│   │   │   │       ├── threat_summary_card.dart
│   │   │   │       └── live_alert_feed.dart
│   │   │   │
│   │   │   ├── deepfake_monitor/
│   │   │   │   ├── deepfake_screen.dart
│   │   │   │   └── widgets/
│   │   │   │       ├── video_stream_view.dart
│   │   │   │       └── analysis_overlay.dart
│   │   │   │
│   │   │   ├── phishing_scanner/
│   │   │   │   ├── phishing_screen.dart
│   │   │   │   └── widgets/
│   │   │   │       └── scan_result_card.dart
│   │   │   │
│   │   │   ├── threat_graph/
│   │   │   │   ├── graph_screen.dart
│   │   │   │   └── widgets/
│   │   │   │       └── neo4j_graph_view.dart
│   │   │   │
│   │   │   └── identity/
│   │   │       ├── identity_screen.dart
│   │   │       └── widgets/
│   │   │           └── key_vault_card.dart
│   │   │
│   │   ├── models/
│   │   │   ├── deepfake_result.dart
│   │   │   ├── phishing_report.dart
│   │   │   └── threat_node.dart
│   │   │
│   │   └── providers/
│   │       ├── deepfake_provider.dart
│   │       ├── phishing_provider.dart
│   │       └── threat_graph_provider.dart
│   │
│   └── test/
│       └── widget_test.dart
│
├── scripts/                          ← Dev/ops helper scripts
│   ├── setup_env.sh                  ← One-shot environment bootstrap
│   ├── download_models.sh            ← Pull GGUF models from HuggingFace
│   └── run_dev.sh                    ← Start all services concurrently
│
└── models/                           ← AI model weights (gitignored)
    ├── .gitkeep
    └── README.md                     ← Instructions to download models
```

---

## Phase-by-Phase Development Roadmap

### 🏁 Phase 1 — Foundation & Infrastructure (Days 1–2)
> **Goal:** Skeleton is running end-to-end. Data flows. No AI yet.

#### Backend Tasks
- [ ] Initialize Django project with `config/settings/` package pattern
- [ ] Configure PostgreSQL connection (`psycopg2`, `DATABASE_URL`)
- [ ] Configure Django Channels with Redis channel layer in `asgi.py`
- [ ] Scaffold `deepfake`, `phishing`, `identity`, `threat_graph` apps
- [ ] Create base models and run initial migrations
- [ ] Set up Celery worker with Redis broker
- [ ] Write a basic WebSocket consumer (`deepfake/consumers.py`) that echoes frames back
- [ ] Bootstrap Neo4j connection in `graph_client.py` (create test node)
- [ ] Implement ECDSA key generation and signing service (`identity/services.py`)

#### AI Engine Tasks
- [ ] Set up `ai_engine/` virtual environment (`python -m venv .venv`)
- [ ] Verify MPS device availability: `torch.backends.mps.is_available()`
- [ ] Create `config.py` with device selection (`mps` → `cpu` fallback)
- [ ] Implement `frame_preprocessor.py` with OpenCV → MPS tensor pipeline
- [ ] Stub out `CrossModalVerificationEngine` class (no model yet)
- [ ] Start minimal FastAPI `server.py` exposing `/health` and `/scan/frame`

#### Flutter Tasks
- [ ] Create Flutter project: `flutter create flutter_dashboard`
- [ ] Add dependencies to `pubspec.yaml` (`riverpod`, `dio`, `web_socket_channel`, `fl_chart`)
- [ ] Scaffold feature screens and navigation with `go_router`
- [ ] Implement `api_client.dart` and `ws_client.dart` core services
- [ ] Build a static mock SOC dashboard layout (no live data yet)

#### Infrastructure Tasks
- [ ] Write `docker-compose.yml` for Neo4j + Redis
- [ ] Create `.env.example` with all required variables
- [ ] Write `scripts/setup_env.sh` for one-command bootstrap

---

### 🤖 Phase 2 — AI Core Engine (Days 3–4)
> **Goal:** Real deepfake and phishing detection working in isolation.

#### Deepfake Detection
- [ ] Implement `visual_detector.py`:
  - Load pretrained MobileNetV2 on MPS
  - Binary classification head for artifact detection
  - Process frames in batches of 4 (memory constraint)
- [ ] Implement `audio_analyzer.py`:
  - Librosa MFCC extraction from raw audio bytes
  - Return 40-coefficient MFCC tensor
- [ ] Implement `lip_sync_verifier.py`:
  - MediaPipe FaceMesh → extract lip landmarks per frame
  - Compute lip aperture time-series
  - Cross-correlate with audio energy signal (Librosa)
  - Detect sync delay > 80ms threshold
- [ ] Implement `blink_detector.py`:
  - Eye aspect ratio (EAR) per frame via FaceMesh
  - Flag unnatural blink rate (< 8 or > 30 bpm)
- [ ] Wire all detectors into `CrossModalVerificationEngine.analyze()`
- [ ] Add ECDSA signing to each verdict in `cross_modal_engine.py`

#### Phishing Detection
- [ ] Download quantized Llama model (4-bit GGUF, ≤ 4GB)
- [ ] Implement `llm_analyzer.py` with `llama-cpp-python`
  - System prompt: phishing intent classifier
  - Parse structured JSON verdict from LLM output
- [ ] Implement `url_forensics.py`:
  - URL entropy scoring
  - Homoglyph character detection
  - Subdomain depth analysis
  - Known phishing TLD blocklist
- [ ] Implement `header_analyzer.py`:
  - SPF/DKIM/DMARC record validation
  - "Reply-To" vs "From" mismatch detection
- [ ] Aggregate all signals into final phishing verdict + ECDSA sign

#### Backend Integration
- [ ] Wire `deepfake/tasks.py` Celery task → AI engine HTTP calls
- [ ] Wire `phishing/tasks.py` → AI engine phishing endpoint
- [ ] Store verdicts in PostgreSQL
- [ ] Write threat entities to Neo4j via `graph_client.py`

---

### 🔗 Phase 3 — Integration & Real-Time Streaming (Day 5)
> **Goal:** Live end-to-end pipeline. Flutter talks to Django talks to AI.

- [ ] Upgrade WebSocket consumer to accept binary frame chunks and dispatch to Celery
- [ ] Implement server-sent verdicts back over WebSocket to Flutter
- [ ] Build Flutter `deepfake_screen.dart` with live camera feed + overlay
  - Use `camera` package to capture frames
  - Send encoded JPEGs via WebSocket
  - Render verdicts as overlay badges
- [ ] Build Flutter `phishing_screen.dart` with email/URL paste-and-scan UI
- [ ] Build Flutter `threat_graph_screen.dart` with Neo4j query results
  - Visualize as interactive node graph
- [ ] Implement JWT + ECDSA hybrid auth in Django
  - Flutter presents ECDSA public key; backend verifies
- [ ] Integrate threat graph: Neo4j data → Flutter graph widget
- [ ] Real-time alert feed via WebSocket → Flutter `dashboard_screen.dart`

---

### 🏆 Phase 4 — Polish, Demo & Hardening (Day 6)
> **Goal:** Demo-ready. Robust under failure. Visually impressive.

- [ ] **Memory Profiling:** Run `memory_profiler` on AI engine; ensure peak < 4GB
- [ ] **Graceful Degradation:** If MPS OOMs, fallback to CPU with reduced batch size
- [ ] **Model Caching:** Singleton pattern for models (load once, reuse across requests)
- [ ] **Error Handling:** Return structured JSON errors from AI engine FastAPI server
- [ ] **Demo Script:** Prepare sample deepfake video and phishing email for live demo
- [ ] **SOC Dashboard Polish:**
  - Dark theme with accent colors
  - Animated threat confidence meters
  - Real-time Neo4j graph updates
  - ECDSA verification badge on each verdict
- [ ] **README:** Write setup and demo instructions
- [ ] **Slide Deck:** Architecture diagram + live demo flow

---

## Cross-Modal Verification Engine — Boilerplate

> File: `ai_engine/deepfake/cross_modal_engine.py`

```python
"""
Cross-Modal Verification Engine
================================
Detects deepfakes by analysing the temporal coherence between visual
artifacts (MobileNetV2 on MPS) and audio-lip synchronisation (MediaPipe +
Librosa).

Hardware target: Apple Silicon M4 — uses torch.device("mps") with CPU fallback.
Memory budget  : ≤ 2 GB peak (batch_size=4, fp16 inference).

Author: Sanyam Gehlot
"""

from __future__ import annotations

import gc
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import librosa
import mediapipe as mp
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T

from ai_engine.identity.ecdsa_service import ECDSAService

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Device Configuration — MPS-first, CPU fallback
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_device() -> torch.device:
    """
    Resolve the best available compute device.
    Priority: MPS (Apple Silicon) → CUDA → CPU
    """
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        logger.info("✅ MPS device available — using Apple Metal GPU")
        return torch.device("mps")
    elif torch.cuda.is_available():
        logger.info("✅ CUDA device available")
        return torch.device("cuda")
    else:
        logger.warning("⚠️  Falling back to CPU — inference will be slow")
        return torch.device("cpu")


DEVICE: torch.device = _resolve_device()


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FrameAnalysisResult:
    """Result from analysing a single video frame."""
    frame_index: int
    visual_artifact_score: float        # 0.0 (real) → 1.0 (fake)
    lip_sync_delay_ms: float            # milliseconds; >80ms = suspicious
    blink_rate_bpm: float               # beats/min; <8 or >30 = suspicious
    is_suspicious: bool
    confidence: float                   # aggregated confidence [0, 1]


@dataclass
class DeepfakeVerdict:
    """Final verdict for a video segment."""
    session_id: str
    is_deepfake: bool
    confidence: float
    frame_results: list[FrameAnalysisResult] = field(default_factory=list)
    processing_time_ms: float = 0.0
    signed_verdict: Optional[str] = None   # ECDSA hex signature
    public_key_pem: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Visual Artifact Detector (MobileNetV2 on MPS)
# ─────────────────────────────────────────────────────────────────────────────

class VisualArtifactDetector(nn.Module):
    """
    Lightweight deepfake artifact classifier.
    Backbone: MobileNetV2 (pretrained on ImageNet).
    Head    : Binary classifier (real vs fake).
    
    Memory: ~14 MB weights, ~50 MB activations per batch of 4 @ fp16
    """

    _TRANSFORM = T.Compose([
        T.ToPILImage(),
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]),
    ])

    def __init__(self, weights_path: Optional[Path] = None) -> None:
        super().__init__()
        backbone = models.mobilenet_v2(
            weights=models.MobileNet_V2_Weights.IMAGENET1K_V1
        )
        # Freeze backbone to save memory & training time
        for param in backbone.features.parameters():
            param.requires_grad = False

        in_features = backbone.classifier[1].in_features
        backbone.classifier = nn.Sequential(
            nn.Dropout(0.2),
            nn.Linear(in_features, 1),
            nn.Sigmoid(),
        )
        self.model = backbone

        if weights_path and weights_path.exists():
            state = torch.load(weights_path, map_location="cpu")
            self.model.load_state_dict(state)
            logger.info(f"Loaded fine-tuned weights from {weights_path}")

        # Move to device in fp16 for memory efficiency on MPS
        self.model = self.model.to(DEVICE).half()
        self.model.eval()

    def preprocess_frames(self, frames: list[np.ndarray]) -> torch.Tensor:
        """
        Preprocess a list of BGR OpenCV frames into a batched MPS tensor.
        Frames are converted RGB → normalised → stacked.
        """
        tensors = []
        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            t = self._TRANSFORM(rgb)
            tensors.append(t)
        # Shape: [B, 3, 224, 224]
        batch = torch.stack(tensors).to(DEVICE).half()
        return batch

    @torch.no_grad()
    def score_batch(self, frames: list[np.ndarray]) -> list[float]:
        """
        Score a batch of frames. Returns artifact probability per frame.
        Processes in sub-batches of 4 to respect memory constraints.
        """
        SUB_BATCH = 4
        scores: list[float] = []

        for i in range(0, len(frames), SUB_BATCH):
            sub = frames[i : i + SUB_BATCH]
            batch_tensor = self.preprocess_frames(sub)
            output = self.model(batch_tensor)           # [B, 1]
            batch_scores = output.squeeze(1).cpu().float().tolist()
            scores.extend(batch_scores)
            # Explicit MPS cache release between sub-batches
            if DEVICE.type == "mps":
                torch.mps.empty_cache()

        return scores


# ─────────────────────────────────────────────────────────────────────────────
# Lip-Sync Verifier (MediaPipe + Librosa)
# ─────────────────────────────────────────────────────────────────────────────

class LipSyncVerifier:
    """
    Detects audio-visual desynchronisation by correlating:
    - Lip aperture signal (from MediaPipe FaceMesh landmarks)
    - Audio energy envelope (from Librosa RMS)
    
    A cross-correlation delay > LIP_SYNC_THRESHOLD_MS → suspicious
    """
    LIP_SYNC_THRESHOLD_MS: float = 80.0

    # Lip landmark indices (MediaPipe 468-point model)
    UPPER_LIP = 13
    LOWER_LIP = 14

    def __init__(self) -> None:
        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def extract_lip_aperture(
        self, frames: list[np.ndarray], fps: float
    ) -> np.ndarray:
        """Extract normalised lip aperture (0→1) per frame."""
        apertures: list[float] = []
        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._face_mesh.process(rgb)
            if results.multi_face_landmarks:
                lm = results.multi_face_landmarks[0].landmark
                upper_y = lm[self.UPPER_LIP].y
                lower_y = lm[self.LOWER_LIP].y
                apertures.append(abs(lower_y - upper_y))
            else:
                apertures.append(0.0)
        return np.array(apertures, dtype=np.float32)

    def extract_audio_energy(
        self, audio_bytes: bytes, sample_rate: int = 16000
    ) -> np.ndarray:
        """Extract frame-level RMS energy from raw audio bytes."""
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        audio_array /= 32768.0  # normalise to [-1, 1]
        rms = librosa.feature.rms(
            y=audio_array,
            frame_length=512,
            hop_length=512,
        )[0]
        return rms.astype(np.float32)

    def compute_sync_delay_ms(
        self,
        lip_signal: np.ndarray,
        audio_signal: np.ndarray,
        fps: float,
    ) -> float:
        """
        Cross-correlate lip and audio signals.
        Returns the estimated delay in milliseconds.
        """
        target_len = min(len(lip_signal), len(audio_signal))
        if target_len < 2:
            return 0.0

        lip = lip_signal[:target_len]
        audio = audio_signal[:target_len]

        # Zero-mean normalise
        lip = (lip - lip.mean()) / (lip.std() + 1e-8)
        audio = (audio - audio.mean()) / (audio.std() + 1e-8)

        # Full cross-correlation
        correlation = np.correlate(lip, audio, mode="full")
        lag_frames = int(np.argmax(correlation)) - (target_len - 1)
        delay_ms = abs(lag_frames) * (1000.0 / fps)
        return delay_ms

    def verify(
        self,
        frames: list[np.ndarray],
        audio_bytes: bytes,
        fps: float = 25.0,
        sample_rate: int = 16000,
    ) -> tuple[float, bool]:
        """Returns (delay_ms, is_suspicious)."""
        lip_signal = self.extract_lip_aperture(frames, fps)
        audio_signal = self.extract_audio_energy(audio_bytes, sample_rate)
        delay_ms = self.compute_sync_delay_ms(lip_signal, audio_signal, fps)
        is_suspicious = delay_ms > self.LIP_SYNC_THRESHOLD_MS
        return delay_ms, is_suspicious


# ─────────────────────────────────────────────────────────────────────────────
# Blink Rate Detector (MediaPipe FaceMesh)
# ─────────────────────────────────────────────────────────────────────────────

class BlinkRateDetector:
    """
    Computes blink rate using Eye Aspect Ratio (EAR).
    Abnormal rates (< 8 or > 30 bpm) indicate possible deepfake.
    """
    EAR_THRESHOLD: float = 0.20
    MIN_BLINK_BPM: float = 8.0
    MAX_BLINK_BPM: float = 30.0

    def __init__(self) -> None:
        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        )

    @staticmethod
    def _euclidean(a: tuple, b: tuple) -> float:
        return np.linalg.norm(np.array(a) - np.array(b))

    def _compute_ear(self, landmarks) -> float:
        """Compute Eye Aspect Ratio from MediaPipe landmarks."""
        lm = landmarks.landmark
        A = self._euclidean((lm[385].x, lm[385].y), (lm[380].x, lm[380].y))
        B = self._euclidean((lm[386].x, lm[386].y), (lm[374].x, lm[374].y))
        C = self._euclidean((lm[362].x, lm[362].y), (lm[263].x, lm[263].y))
        return (A + B) / (2.0 * C + 1e-8)

    def compute_blink_rate(
        self, frames: list[np.ndarray], fps: float = 25.0
    ) -> tuple[float, bool]:
        """Returns (blink_rate_bpm, is_suspicious)."""
        blink_count = 0
        blink_in_progress = False

        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._face_mesh.process(rgb)
            if results.multi_face_landmarks:
                ear = self._compute_ear(results.multi_face_landmarks[0])
                if ear < self.EAR_THRESHOLD and not blink_in_progress:
                    blink_count += 1
                    blink_in_progress = True
                elif ear >= self.EAR_THRESHOLD:
                    blink_in_progress = False

        duration_minutes = len(frames) / (fps * 60.0)
        blink_rate_bpm = (blink_count / duration_minutes) if duration_minutes > 0 else 0.0
        is_suspicious = not (self.MIN_BLINK_BPM <= blink_rate_bpm <= self.MAX_BLINK_BPM)
        return blink_rate_bpm, is_suspicious


# ─────────────────────────────────────────────────────────────────────────────
# Cross-Modal Verification Engine (Orchestrator)
# ─────────────────────────────────────────────────────────────────────────────

class CrossModalVerificationEngine:
    """
    Orchestrates all deepfake detection signals:
      1. Visual artifact scoring (MobileNetV2 on MPS)
      2. Lip-sync delay analysis (MediaPipe + Librosa)
      3. Blink rate anomaly detection (MediaPipe FaceMesh)

    All verdicts are cryptographically signed via ECDSA.

    Usage:
        engine = CrossModalVerificationEngine()
        verdict = engine.analyze(
            session_id="abc-123",
            frames=frame_list,          # list of BGR np.ndarray
            audio_bytes=raw_audio,      # raw PCM bytes
            fps=25.0,
        )
    """

    WEIGHTS = {"visual": 0.40, "lip_sync": 0.35, "blink": 0.25}
    FAKE_THRESHOLD: float = 0.55

    def __init__(
        self,
        visual_weights_path: Optional[Path] = None,
        ecdsa_private_key_pem: Optional[str] = None,
    ) -> None:
        logger.info("Initialising Cross-Modal Verification Engine...")
        self.visual_detector = VisualArtifactDetector(visual_weights_path)
        self.lip_sync_verifier = LipSyncVerifier()
        self.blink_detector = BlinkRateDetector()
        self.ecdsa_service = ECDSAService(private_key_pem=ecdsa_private_key_pem)
        logger.info(f"Engine ready on device: {DEVICE}")

    def _aggregate_confidence(
        self,
        visual_score: float,
        lip_sync_suspicious: bool,
        blink_suspicious: bool,
    ) -> float:
        lip_score = 1.0 if lip_sync_suspicious else 0.0
        blink_score = 1.0 if blink_suspicious else 0.0
        confidence = (
            self.WEIGHTS["visual"] * visual_score
            + self.WEIGHTS["lip_sync"] * lip_score
            + self.WEIGHTS["blink"] * blink_score
        )
        return float(np.clip(confidence, 0.0, 1.0))

    def analyze(
        self,
        session_id: str,
        frames: list[np.ndarray],
        audio_bytes: bytes,
        fps: float = 25.0,
        sample_rate: int = 16000,
    ) -> DeepfakeVerdict:
        """
        Run full cross-modal deepfake analysis on a video segment.

        Args:
            session_id:   Unique identifier for this scan session
            frames:       List of BGR OpenCV frames (np.ndarray)
            audio_bytes:  Raw 16-bit PCM audio bytes (mono)
            fps:          Frames per second of the video
            sample_rate:  Audio sample rate in Hz

        Returns:
            DeepfakeVerdict with signed result
        """
        if not frames:
            raise ValueError("frames list cannot be empty")

        start_time = time.perf_counter()
        logger.info(
            f"[{session_id}] Analysing {len(frames)} frames @ {fps}fps on {DEVICE}"
        )

        # 1. Visual Artifact Detection
        visual_scores = self.visual_detector.score_batch(frames)
        mean_visual_score = float(np.mean(visual_scores))

        # 2. Lip-Sync Analysis
        lip_delay_ms, lip_suspicious = self.lip_sync_verifier.verify(
            frames=frames, audio_bytes=audio_bytes, fps=fps, sample_rate=sample_rate,
        )

        # 3. Blink Rate Analysis
        blink_rate_bpm, blink_suspicious = self.blink_detector.compute_blink_rate(
            frames=frames, fps=fps
        )

        # 4. Confidence Aggregation
        overall_confidence = self._aggregate_confidence(
            mean_visual_score, lip_suspicious, blink_suspicious
        )
        is_deepfake = overall_confidence >= self.FAKE_THRESHOLD

        # 5. Per-frame results
        frame_results = [
            FrameAnalysisResult(
                frame_index=i,
                visual_artifact_score=visual_scores[i],
                lip_sync_delay_ms=lip_delay_ms,
                blink_rate_bpm=blink_rate_bpm,
                is_suspicious=(visual_scores[i] > 0.5 or lip_suspicious or blink_suspicious),
                confidence=self._aggregate_confidence(
                    visual_scores[i], lip_suspicious, blink_suspicious
                ),
            )
            for i in range(len(frames))
        ]

        processing_time_ms = (time.perf_counter() - start_time) * 1000.0

        # 6. ECDSA Signing
        verdict_payload = (
            f"{session_id}|deepfake={is_deepfake}|"
            f"confidence={overall_confidence:.4f}|"
            f"ts={int(time.time())}"
        )
        signed_verdict, public_key_pem = self.ecdsa_service.sign(verdict_payload)

        # 7. Memory Cleanup
        if DEVICE.type == "mps":
            torch.mps.empty_cache()
        gc.collect()

        verdict = DeepfakeVerdict(
            session_id=session_id,
            is_deepfake=is_deepfake,
            confidence=overall_confidence,
            frame_results=frame_results,
            processing_time_ms=processing_time_ms,
            signed_verdict=signed_verdict,
            public_key_pem=public_key_pem,
        )

        logger.info(
            f"[{session_id}] Result: deepfake={is_deepfake} "
            f"(confidence={overall_confidence:.3f}) in {processing_time_ms:.1f}ms"
        )
        return verdict

    def cleanup(self) -> None:
        """Release all GPU/MPS resources. Call on shutdown."""
        del self.visual_detector
        if DEVICE.type == "mps":
            torch.mps.empty_cache()
        gc.collect()
        logger.info("CrossModalVerificationEngine resources released.")
```

---

## Hardware & Memory Constraints

| Concern | Mitigation Strategy |
|---|---|
| MobileNetV2 on MPS OOM | Run in `fp16`, batch size ≤ 4, `torch.mps.empty_cache()` after each batch |
| LLM (4-bit GGUF) memory | `n_ctx=512`, `n_threads=4`, offload only necessary layers |
| MediaPipe RAM | Shared FaceMesh instance per engine (not per-frame init) |
| Django + Celery + AI simultaneously | AI engine runs as separate process (FastAPI); Celery dispatches via HTTP |
| PostgreSQL vs Neo4j | Run Neo4j in Docker (limited to 512MB heap via `NEO4J_JAVA_OPTS`) |
| Multiple services RAM budget | Django ≈ 200MB · AI Engine ≈ 2.5GB · Neo4j ≈ 512MB · Redis ≈ 50MB · Flutter ≈ 100MB |

### MPS Verification Snippet
```python
import torch

assert torch.backends.mps.is_available(), "MPS not available!"
assert torch.backends.mps.is_built(), "PyTorch not built with MPS support!"

x = torch.ones(3, 3, device="mps")
print(f"MPS tensor: {x.device}")  # → device(type='mps', index=0)
```

---

## Dependency Manifest

### `backend/requirements.txt`
```txt
django>=4.2,<5.0
djangorestframework>=3.15
django-cors-headers>=4.3
channels>=4.0
channels-redis>=4.2
daphne>=4.1
celery>=5.4
redis>=5.0
psycopg2-binary>=2.9
py2neo>=2021.2
cryptography>=42.0
python-dotenv>=1.0
gunicorn>=22.0
```

### `ai_engine/requirements.txt`
```txt
torch>=2.3.0
torchvision>=0.18.0
opencv-python>=4.9.0.80
mediapipe>=0.10.14
librosa>=0.10.2
numpy>=1.26
fastapi>=0.111
uvicorn[standard]>=0.30
llama-cpp-python>=0.2.85
cryptography>=42.0
python-dotenv>=1.0
memory-profiler>=0.61
```

### `flutter_dashboard/pubspec.yaml` (dependencies section)
```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_riverpod: ^2.5.1
  go_router: ^14.2.0
  dio: ^5.4.3
  web_socket_channel: ^3.0.0
  fl_chart: ^0.68.0
  camera: ^0.11.0+1
  permission_handler: ^11.3.1
  shared_preferences: ^2.3.0
  intl: ^0.19.0
```

---

*Generated by Antigravity IDE — Hackathon Edition 🚀*
