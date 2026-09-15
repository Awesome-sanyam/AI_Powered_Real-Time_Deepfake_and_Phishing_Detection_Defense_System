# 🤝 Contributing to DEFENCESYS

Thank you for your interest in contributing to **DEFENCESYS**! We welcome contributions, bug fixes, feature proposals, and architectural improvements from the global cybersecurity, AI/ML, and open-source communities.

---

## 👥 Project Leadership & Core Maintainers

* **Sanyam Gehlot** ([@Awesome-sanyam](https://github.com/Awesome-sanyam)) — *Project Founder & Lead Maintainer*

---

## 📜 Code of Conduct

* **Integrity First:** Ensure that all detection algorithms, metrics, and benchmarks are honest, verifiable, and mathematically sound.
* **Respect & Collaboration:** Maintain a welcoming, inclusive, and professional environment for all contributors.
* **Responsible Security Disclosure:** Do NOT open public issues for security vulnerabilities. Follow the protocols in [SECURITY.md](SECURITY.md).

---

## 🛠️ Development Setup & Workflow

### 1. Fork and Clone
```bash
git clone https://github.com/Awesome-sanyam/AI_Powered_Real-Time_Deepfake_and_Phishing_Detection_Defense_System.git
cd "AI Deepfake and Phishing Defence System"
```

### 2. Environment Initialization
Follow the step-by-step setup guide in [README.md](README.md) to initialize the virtual environments, install dependencies, and launch the Docker infrastructure (`postgres`, `redis`, `neo4j`).

### 3. Git Branching Strategy
* **`main`**: Production-ready branch. Must remain green and deployable at all times.
* **`develop`**: Integration branch for upcoming minor releases.
* **`feat/<feature-slug>`**: New capabilities (e.g., `feat/audio-denoising-filter`).
* **`fix/<bug-slug>`**: Bug fixes and regressions (e.g., `fix/websocket-reconnect-backoff`).
* **`docs/<topic>`**: Documentation updates (e.g., `docs/api-spec-update`).

---

## 📐 Engineering Standards & Code Guidelines

### Python (Backend & AI Microservice)
* **PEP 8 Compliance:** Use `black` and `flake8` for formatting and linting.
* **Type Annotations:** Enforce strict type hints (`typing.Optional`, `typing.Union`, `dataclasses.dataclass`).
* **Django ORM Efficiency:** Always prevent $N+1$ query bottlenecks using `select_related()` and `prefetch_related()`.
* **Async & Thread Safety:** Avoid blocking event loops in Django Channels consumers and FastAPI routes. Delegate heavy computational tasks to Celery workers.
* **Memory Management:** In PyTorch code, explicitly call `torch.mps.empty_cache()` or `torch.cuda.empty_cache()` after batch inference.

### Frontend (HTML5, Tailwind CSS & JavaScript)
* **Pure Pitch-Black Dark Theme:** Use pure pitch-black and deep zinc backgrounds (`dark:bg-black`, `dark:bg-zinc-950`). **Never introduce blue tints** (`bg-blue-*`, `dark:bg-blue-900`) in SOC dashboard backgrounds.
* **Zero-Flash Theme Persistence:** Ensure theme state is executed synchronously in the `<head>` to prevent flash-of-unstyled-content (FOUC).
* **Accessibility:** Include descriptive `aria-label`, `role`, and `title` attributes on all buttons, canvas HUD elements, and modals.
* **Vanilla JavaScript:** Write clean, modular ES6+ JavaScript. Keep WebSocket reconnection resilient with exponential backoff.

---

## 🧪 Testing & Quality Gates

Every Pull Request must pass 100% of the project's automated verification suites before being considered for review:

```bash
# 1. Commercial Launch Readiness Audit (26 Checks)
python scripts/verify_ui_launch.py

# 2. Full UI/UX & AI Pipeline Verification Suite (22 Checks)
python scripts/verify_full_ui.py
```

---

## 📝 Commit Message Conventions

We enforce the **Conventional Commits** specification:

| Prefix | Usage Example |
|---|---|
| **`feat:`** | `feat(deepfake): add multi-face tracking bounding boxes` |
| **`fix:`** | `fix(auth): prevent session timeout during long video analysis` |
| **`docs:`** | `docs(readme): update cross-platform CUDA setup guide` |
| **`perf:`** | `perf(vision): optimize MobileNetV2 fp16 tensor pre-allocation` |
| **`test:`** | `test(phishing): add test cases for Punycode homoglyphs` |
| **`refactor:`** | `refactor(threat_graph): streamline Cypher query builder` |
| **`chore:`** | `chore(deps): bump cryptography from 42.0 to 42.1` |

---

## 🚀 Submitting a Pull Request

1. Push your feature or fix branch to your GitHub fork:
   ```bash
   git push origin feat/your-feature-name
   ```
2. Open a Pull Request targeting the `main` branch.
3. Complete the PR template describing:
   * **What changes were made.**
   * **Why the change is needed.**
   * **How the change was verified (attach test logs or screenshots).**
   * **Any impact on hardware memory or processing latency.**
4. Address review feedback promptly. Once approved and CI checks pass, a core maintainer will merge your PR.
