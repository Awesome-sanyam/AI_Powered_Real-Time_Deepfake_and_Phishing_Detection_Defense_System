# 🛡️ DEFENCESYS — AI-Powered Real-Time Deepfake & Phishing Defense Platform

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2%20LTS-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.3%2B%20(MPS%20%7C%20CUDA)-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5%20Community-008CC1?logo=neo4j&logoColor=white)](https://neo4j.com/)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Audit](https://img.shields.io/badge/Launch%20Audit-26%2F26%20Passing%20(100%25)-brightgreen)](#automated-testing--verification)

**A high-performance, zero-trust cybersecurity platform providing real-time multi-modal deepfake detection, LLM-powered phishing intent analysis, graph-based campaign correlation, and hardware-attested cryptographic verdict signing.**

[Key Features](#-key-features) • [Architecture](#-system-architecture) • [Cross-Platform Setup](#-cross-platform-setup-guide) • [Quickstart](#-quickstart-guide) • [Operational Guide](#-operational-modules--user-guide) • [API & WebSockets](#-api--websocket-specifications) • [Verification](#-automated-testing--verification)

</div>

---

## 🌟 Executive Summary

**DEFENCESYS** is an enterprise-grade defense platform built to counter modern generative AI attack vectors, including synthetic executive impersonation, biometric bypasses, and targeted phishing campaigns.

Unlike traditional static security tools, DEFENCESYS merges:
1. **Physical & Temporal Coherence Analysis:** Combines neural visual artifact detection with physiological signals (Eye Aspect Ratio blink rate) and acoustic-visual cross-correlation (lip-sync aperture lag).
2. **Local Quantized LLM Intelligence:** Evaluates linguistic social engineering and homoglyph/Punycode domain spoofing using local 4-bit LLaMA models—with zero cloud telemetry leakage.
3. **Cryptographic Non-Repudiation:** Signs every AI-derived verdict using **ECDSA P-256**, ensuring forensic reports cannot be tampered with or repudiated in legal or compliance proceedings.
4. **Graph-Correlated Threat Topologies:** Correlates disparate attack indicators into cohesive campaign graphs in Neo4j, exposing shared threat actor infrastructure in real time.

---

## 🚀 Key Features

### 1. 🎥 Dual-Mode Real-Time Deepfake Detection (`/deepfake/monitor/`)
* **Live Webcam Stream Analysis:**
  * Real-time streaming over **Django Channels WebSockets** at 12–25 FPS with sub-second Celery dispatch.
  * Interactive HTML5 Canvas HUD dynamically rendering facial bounding boxes, landmark contours, and real-time telemetry.
  * Graceful fallback to video-only analysis if microphone permissions are restricted or absent.
* **Synthetic Live Simulation Feed:**
  * Built-in dynamic canvas stream generator (`startSyntheticStream`) simulating real-time video, speech motion, and eye blinks at 12 FPS for instant testing on headless servers or devices without physical webcams.
* **Media File Upload Forensics:**
  * Supports MP4, AVI, MOV, and WebM file uploads with OpenCV frame decomposition at 5 FPS.
  * Comprehensive frame-by-frame forensic breakdown table displaying visual artifact scores, lip-sync latency, and blink dynamics.
  * Visual threat distribution charts and tamper-proof verification badges.

### 2. 🎣 GenAI Phishing Defense & Header Forensics (`/phishing/scanner/`)
* **Local Quantized LLM Inference:** Powered by **LLaMA 3.2 3B Instruct (4-bit GGUF)** via `llama-cpp-python` for deep semantic intent classification.
* **Homoglyph & Punycode Detection:** Identifies Cyrillic/Unicode domain spoofing (e.g., `xn--pypal-4ve.tk` masquerading as `paypal.com`).
* **Shannon URL Entropy Scoring:** Mathematical entropy profiling to catch algorithmic DGA domains and high-entropy tracking redirects.
* **Email Header Verification:** Automated checks for SPF, DKIM, DMARC alignment, Display Name deception, and suspicious `Reply-To` / `From` mismatches.
* **Zero Cloud Dependency:** Runs 100% locally on your hardware; no external API keys or third-party data sharing required.

### 3. 🕸️ Threat Graph Campaign Intelligence (`/threat-graph/view/`)
* **Neo4j Graph Database:** Links Attackers, IPs, Domains, Email Addresses, and Target Organizations into an interconnected knowledge graph.
* **Interactive D3.js Visualization:** Force-directed graph explorer supporting zoom, pan, node dragging, degree filtering, and threat score badges.
* **Automated Campaign Clustering:** Automatically aggregates isolated attacks sharing common infrastructure into identified attack campaigns.

### 4. 🔐 Cryptographic Identity Vault & Attestation (`/identity/vault/`)
* **ECDSA P-256 Hardware Attestation:** Every AI verdict is cryptographically signed using private keys managed within the secure Identity Vault.
* **Public Key PEM Export:** Allows external systems, SOC analysts, and audit teams to independently verify verdict integrity using standard cryptography tools.
* **Tamper-Proof Verification:** Validates that threat scores, frame results, and timestamp hashes have not been modified after generation.

### 5. 🖥️ Enterprise SOC Command Dashboard (`/`)
* **Pitch-Black Dark Mode:** Built with pure pitch-black styling (`dark:bg-black`, `dark:bg-zinc-950`) specifically engineered for high-contrast SOC monitoring rooms with zero blue background bleeding.
* **Flash-Free Theme Toggle:** Zero-latency, flicker-free light and dark mode switching with inline script execution and `localStorage` persistence.
* **Live Incident Feed:** Real-time push alerts streamed via WebSockets as threats are detected across the network.

---

## 🏗️ System Architecture

```
                                  CLIENT TIER
                 ┌───────────────────────────────────────────┐
                 │          SOC Web Dashboard & HUD          │
                 │   (HTML5 Canvas · Vanilla JS WebSockets)  │
                 └─────────────────────┬─────────────────────┘
                                       │ HTTP / WebSocket (Port 8000)
                                       ▼
                             ORCHESTRATION TIER
                 ┌───────────────────────────────────────────┐
                 │       Daphne ASGI Server (Port 8000)      │
                 │       Django 4.2 LTS · Channels 4.x       │
                 └───────┬─────────────┬─────────────┬───────┘
                         │             │             │
              WebSocket  │             │ Async Tasks │ REST Queries
              Frames     │             │             │
                         ▼             ▼             ▼
                 ┌───────────────┐ ┌─────────┐ ┌───────────────┐
                 │ Redis 7       │ │ Celery  │ │ PostgreSQL 16 │
                 │ Channel Layer │ │ Worker  │ │ Relational DB │
                 └───────┬───────┘ └────┬────┘ └───────────────┘
                         │              │
                         │ HTTP Stream  │ HTTP Jobs
                         ▼              ▼
                              AI COMPUTE TIER
                 ┌───────────────────────────────────────────┐
                 │        FastAPI Microservice (Port 8001)   │
                 │        Uvicorn Worker · PyTorch MPS/CUDA  │
                 ├───────────────────────────────────────────┤
                 │ • Visual Artifacts: MobileNetV2 (fp16)    │
                 │ • Audio-Visual Sync: MediaPipe + Librosa  │
                 │ • Blink & Gaze Dynamics: FaceMesh / dlib  │
                 │ • Phishing LLM: LLaMA 3.2 3B (4-bit GGUF) │
                 │ • Cryptographic Signer: ECDSA P-256       │
                 └─────────────────────┬─────────────────────┘
                                       │ Threat Correlations
                                       ▼
                 ┌───────────────────────────────────────────┐
                 │          Neo4j 5 Threat Graph DB          │
                 │     (Attackers · Domains · Campaigns)     │
                 └───────────────────────────────────────────┘
```

---

## ⚡ Hardware Acceleration & Compute Engines

DEFENCESYS features automatic hardware detection and adapts dynamically to available compute resources:

| Accelerator | Target Platforms | Precision | Memory Profile | Performance |
|---|---|---|---|---|
| **Apple Metal (MPS)** | Apple Silicon M1 / M2 / M3 / M4 (macOS 13+) | FP16 Half | ~2.8 GB Unified | ~15–25 FPS Live Stream |
| **NVIDIA CUDA** | Linux / Windows (RTX 3060+, T4, A10G, etc.) | FP16 / AMP | ~3.5 GB VRAM | ~20–30 FPS Live Stream |
| **Universal CPU** | x86_64 / arm64 (Intel, AMD, Graviton) | INT8 / FP32 | ~1.8 GB RAM | ~5–10 FPS (Sub-sampled) |

---

## 💻 Cross-Platform Setup Guide

Choose your operating system below for tailored installation instructions.

<details>
<summary><b>🍎 Option 1: macOS (Apple Silicon M1 / M2 / M3 / M4) — Recommended</b></summary>

### 1. Install System Dependencies
Install Homebrew (if not already installed) and the required native tools:
```bash
# Install Homebrew packages
brew install python@3.11 postgresql@16 redis docker cmake pkg-config
brew services start postgresql@16
brew services start redis
```

### 2. Clone the Repository
```bash
git clone https://github.com/Awesome-sanyam/AI_Powered_Real-Time_Deepfake_and_Phishing_Detection_Defense_System.git
cd "AI Deepfake and Phishing Defence System"
```

### 3. Automated One-Command Bootstrap
Run the included setup script:
```bash
bash scripts/setup_env.sh
```
This script will:
* Verify Python, Homebrew, and Docker.
* Create and populate `.env` with a secure random key.
* Create the backend virtual environment and install dependencies.
* Provision the PostgreSQL database and user.
* Install PyTorch with native Apple Metal (`mps`) support.
* Spin up Neo4j and Redis containers via Docker.

### 4. Download AI Model Weights
```bash
bash scripts/download_models.sh
```
</details>

<details>
<summary><b>🐧 Option 2: Linux (Ubuntu 22.04 / 24.04 LTS / Debian)</b></summary>

### 1. Install System Dependencies
```bash
sudo apt update && sudo apt install -y \
    python3 python3-pip python3-venv \
    build-essential cmake pkg-config \
    libopencv-dev libsndfile1-dev \
    postgresql postgresql-contrib \
    redis-server curl git docker.io docker-compose-v2

# Start background services
sudo systemctl enable --now postgresql
sudo systemctl enable --now redis-server
```

### 2. Configure PostgreSQL
```bash
sudo -u postgres psql -c "CREATE USER soc_user WITH PASSWORD 'soc_password';"
sudo -u postgres psql -c "CREATE DATABASE soc_db OWNER soc_user;"
```

### 3. Clone and Setup Environments
```bash
git clone https://github.com/Awesome-sanyam/AI_Powered_Real-Time_Deepfake_and_Phishing_Detection_Defense_System.git
cd "AI Deepfake and Phishing Defence System"

# Configure environment variables
cp .env.example .env
sed -i "s/change-me-to-a-long-random-string/$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')/" .env

# Setup Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
cd ..

# Setup AI Engine with CUDA support (or CPU)
cd ai_engine
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
# For NVIDIA CUDA 12.1:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
# Or for CPU-only:
# pip install torch torchvision torchaudio
pip install -r requirements.txt
deactivate
cd ..
```

### 4. Start Docker Infrastructure (Neo4j)
```bash
docker compose up -d neo4j
```

### 5. Download Model Weights
```bash
bash scripts/download_models.sh
```
</details>

<details>
<summary><b>🪟 Option 3: Windows (WSL2 with Ubuntu 22.04 / 24.04)</b></summary>

We strongly recommend running on Windows via **WSL2** (Windows Subsystem for Linux) for optimal POSIX and CUDA performance.

### 1. Prerequisites
1. Open PowerShell as Administrator and enable WSL:
   ```powershell
   wsl --install -d Ubuntu-22.04
   ```
2. Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) and enable the **WSL 2 backend** in Settings.
3. For NVIDIA GPU acceleration, ensure the latest [NVIDIA Windows Drivers](https://www.nvidia.com/Download/index.aspx) are installed.

### 2. Inside the WSL2 Ubuntu Terminal
Follow the [Linux (Ubuntu) instructions](#-option-2-linux-ubuntu-2204--2404-lts--debian) above to clone the repository and configure the environments.
</details>

---

## 🚀 Quickstart Guide

### Option A: The Unified Dev Launcher (Fastest)

If you are on macOS or Linux, run all services concurrently with a single command:
```bash
bash scripts/run_dev.sh
```
`run_dev.sh` will:
1. Verify prerequisites and activate virtual environments.
2. Check and start PostgreSQL, Redis, and Neo4j containers.
3. Automatically execute Django database migrations.
4. Launch the **FastAPI AI Engine** on `http://localhost:8001`.
5. Launch the **Celery Async Worker**.
6. Launch the **Daphne ASGI Web Server** on `http://localhost:8000`.

---

### Option B: Modular Manual Launch (Enterprise / Production)

If you prefer to run each process in a separate terminal window:

#### Terminal 1 — Infrastructure (PostgreSQL, Redis, Neo4j)
```bash
docker compose up -d
```
* PostgreSQL: `localhost:5432`
* Redis: `localhost:6379`
* Neo4j Browser: `http://localhost:7474` (Credentials: `neo4j` / `neo4j_password`)

#### Terminal 2 — FastAPI AI Engine (Port 8001)
```bash
cd ai_engine
source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
```

#### Terminal 3 — Celery Worker
```bash
cd backend
source .venv/bin/activate
celery -A config worker --loglevel=info --concurrency=2
```

#### Terminal 4 — Daphne ASGI Web Server (Port 8000)
```bash
cd backend
source .venv/bin/activate
python manage.py migrate
daphne -b 0.0.0.0 -p 8000 --verbosity 1 config.asgi:application
```

---

## 🔑 Default Credentials & Access Endpoints

Once running, navigate to **`http://localhost:8000`** in your browser.

| Service / Interface | URL | Default Credentials |
|---|---|---|
| **SOC Command Dashboard** | `http://localhost:8000/` | Requires login |
| **Deepfake Monitor** | `http://localhost:8000/deepfake/monitor/` | Requires login |
| **Phishing Scanner** | `http://localhost:8000/phishing/scanner/` | Requires login |
| **Threat Graph Visualizer** | `http://localhost:8000/threat-graph/view/` | Requires login |
| **Cryptographic Identity Vault** | `http://localhost:8000/identity/vault/` | Requires login |
| **Django Admin Portal** | `http://localhost:8000/admin/` | Superuser required |
| **FastAPI Health Proxy** | `http://localhost:8000/api/ai-engine/health/` | Public JSON endpoint |
| **Neo4j Browser Console** | `http://localhost:7474/` | `neo4j` / `neo4j_password` |

### Pre-Seeded Security Analyst Account
```
Username: analyst
Password: analyst1234
Role:     SOC Security Analyst (Level 3)
```
*(You can create additional accounts at `/auth/register/` or create a Django superuser using `python manage.py createsuperuser`)*

---

## 🎯 Operational Modules & User Guide

### 1. Testing Deepfake Detection Without a Physical Webcam
1. Navigate to [`/deepfake/monitor/`](http://localhost:8000/deepfake/monitor/).
2. In the **Live Stream Monitor** tab, click **"Simulate Live Feed"** (`#btn-demo-stream`).
3. The platform will activate the synthetic animated canvas generator (`startSyntheticStream`), rendering a 12 FPS test stream with dynamic speech patterns and blinking dynamics.
4. Observe the HUD:
   * Real-time bounding box and facial mesh overlays.
   * Frame rate and resolution badges (`12 FPS · 640x480`).
   * Live AI Verdict (`AUTHENTIC MEDIA` or `SUSPICIOUS`).
   * Pulsating **ECDSA Verified** cryptographic badge.

### 2. Testing Media File Upload Forensics
1. In [`/deepfake/monitor/`](http://localhost:8000/deepfake/monitor/), select the **Media File Upload** tab.
2. Drag and drop any `.mp4`, `.webm`, or `.mov` video into the dropzone.
3. Click **"Execute Forensic Analysis"**.
4. Review the generated forensic dossier:
   * **Overall Threat Score Gauge** (e.g., `45.4% Low Risk`).
   * **Lip-Sync Lag & Temporal Coherence** (measured in milliseconds).
   * **Blink Frequency (BPM)** with physiological normality scoring.
   * **Frame-by-Frame Breakdown Table** detailing artifact probabilities across individual sampled frames.
   * **ECDSA Signature Hash** validating tamper-proof integrity.

### 3. Testing Phishing Detection & Header Forensics
1. Navigate to [`/phishing/scanner/`](http://localhost:8000/phishing/scanner/).
2. Paste suspicious email content or input a URL to inspect.
3. Try homoglyph / Punycode URLs like:
   ```
   http://xn--pypal-4ve.tk/secure-login/
   ```
4. Click **"Analyze Phishing Threat"**.
5. The analyzer extracts:
   * Homoglyph character alerts (flagging Cyrillic substitutions).
   * Shannon entropy scores.
   * Suspicious header flags (SPF/DKIM/DMARC alignment).
   * LLM intent classification detailing urgency, coercion, or credential-harvesting motives.

### 4. Exploring the Threat Graph
1. Navigate to [`/threat-graph/view/`](http://localhost:8000/threat-graph/view/).
2. Interact with the D3.js force-directed canvas:
   * Drag nodes to inspect relationships.
   * Click any node to view entity metadata, risk scores, and connected components.
   * Use the risk threshold slider to filter high-threat campaigns.

---

## 📡 API & WebSocket Specifications

### Core REST Endpoints

| Endpoint | Method | Auth | Description |
|---|:---:|:---:|---|
| `/api/ai-engine/health/` | `GET` | None | Proxies health and device status of the FastAPI AI Engine |
| `/api/deepfake/sessions/` | `GET` | Session | Lists recent deepfake scan sessions and scores |
| `/api/deepfake/sessions/<id>/` | `GET` | Session | Detailed forensic breakdown for a specific video session |
| `/api/phishing/scans/` | `GET` | Session | History of email and URL scans |
| `/api/graph/data/` | `GET` | Session | D3-formatted nodes and edges from the Neo4j database |
| `/api/graph/health/` | `GET` | Session | Neo4j database connectivity and node count metrics |
| `/api/identity/keys/` | `GET` | Session | Active ECDSA public keys in PEM format |
| `/api/identity/verify/` | `POST` | Session | Verifies an arbitrary signature against a verdict payload |

### Real-Time WebSocket Channels

#### 1. Live Video Stream: `ws://localhost:8000/ws/deepfake/<session_id>/`
* **Client Send (Frame Payload):**
  ```json
  {
    "type": "video_frame",
    "frame": "data:image/jpeg;base64,...",
    "audio": "...",
    "timestamp": 1726321200.123
  }
  ```
* **Server Return (Live HUD Verdict):**
  ```json
  {
    "type": "analysis_result",
    "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "is_deepfake": false,
    "confidence": 0.45,
    "threat_level": "low",
    "verdict_label": "AUTHENTIC MEDIA",
    "processing_ms": 865,
    "ecdsa_verified": true,
    "signature": "3045022100e4b8..."
  }
  ```

#### 2. SOC Global Alert Feed: `ws://localhost:8000/ws/alerts/`
* Streams real-time notifications for critical threat detections across all active sessions to the dashboard header.

---

## 🧪 Automated Testing & Verification

The repository includes enterprise test suites validating the frontend, backend, AI microservice, and database pipelines:

### 1. Commercial Launch Readiness Audit (26 Checks)
```bash
python scripts/verify_ui_launch.py
```
```
════════════════════════════════════════════════════════════════════════════════
  🛡️  DEFENCESYS — Enterprise UI/UX Launch Readiness Audit
════════════════════════════════════════════════════════════════════════════════
  Total Checks: 26  |  Passed: 26  |  Failed: 0
  🎉 ALL UI/UX AND LAUNCH CHECKS PASSED — READY FOR COMMERCIAL LAUNCH!
```

### 2. End-to-End Verification Suite (22 Checks)
```bash
python scripts/verify_full_ui.py
```
```
========================================================================
  AUDIT PASSED: 22/22 tests completed with 100% success rate.
========================================================================
```

---

## 🛠️ Troubleshooting & FAQs

<details>
<summary><b>Q: Port 8000 or 8001 is already in use</b></summary>

Identify and terminate conflicting processes:
```bash
# Check port 8000 (Daphne/Django)
lsof -i :8000 | awk 'NR>1 {print $2}' | xargs kill -9 2>/dev/null || true

# Check port 8001 (FastAPI AI Engine)
lsof -i :8001 | awk 'NR>1 {print $2}' | xargs kill -9 2>/dev/null || true
```
</details>

<details>
<summary><b>Q: Redis connection timeout on localhost:6379</b></summary>

Ensure the Redis service or container is active:
```bash
# If using Docker:
docker compose up -d redis

# If using Homebrew (macOS):
brew services restart redis

# Test connectivity:
redis-cli ping  # Should return PONG
```
</details>

<details>
<summary><b>Q: Browser blocks camera or microphone</b></summary>

1. Ensure you are accessing the dashboard over `http://localhost:8000` (modern browsers treat `localhost` as a secure origin).
2. If microphone access is denied, DEFENCESYS automatically falls back to video-only streaming.
3. Alternatively, click the **"Simulate Live Feed"** button to run tests using the built-in HTML5 Canvas stream generator without requiring hardware access.
</details>

<details>
<summary><b>Q: Neo4j connection failure (`bolt://localhost:7687`)</b></summary>

Verify that the Neo4j container is healthy:
```bash
docker compose ps neo4j
# If stopped, restart it:
docker compose restart neo4j
```
</details>

---

## 🔒 Security & Responsible Disclosure

DEFENCESYS takes security vulnerabilities seriously. If you discover a security flaw or unintended behavior within this repository:
* Review our guidelines in [SECURITY.md](SECURITY.md).
* Do not file public GitHub issues for critical zero-day vulnerabilities.
* Please submit a responsible disclosure report to the author.

---

## 📄 License

This project is licensed under the terms of the [MIT License](LICENSE).

---

## 👥 Authors & Collaborators

* **Sanyam Gehlot** — *Lead Architect & Systems Engineer*
  * GitHub: [@Awesome-sanyam](https://github.com/Awesome-sanyam)
* **Alefiya** — *Project Collaborator & Core Contributor*
  * GitHub: [@alefiya12](https://github.com/alefiya12)

* **Repository:** [Awesome-sanyam/AI_Powered_Real-Time_Deepfake_and_Phishing_Detection_Defense_System](https://github.com/Awesome-sanyam/AI_Powered_Real-Time_Deepfake_and_Phishing_Detection_Defense_System.git)

