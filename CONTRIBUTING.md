# Contributing to DEFENCESYS

Thank you for your interest in contributing to **DEFENCESYS**! We welcome bug reports, feature proposals, and pull requests from the cybersecurity and AI research community.

---

## Code of Conduct

* Be respectful and considerate of all contributors.
* Adhere to responsible security disclosure practices (see [SECURITY.md](SECURITY.md)).
* Strive for high software quality, rigorous mathematical rigor, and reproducible results.

---

## Development Workflow

1. **Fork and Clone:**
   ```bash
   git clone https://github.com/Awesome-sanyam/AI_Powered_Real-Time_Deepfake_and_Phishing_Detection_Defense_System.git
   ```

2. **Set Up Environments:**
   Follow the instructions in [README.md](README.md) to initialize your Python virtual environments and launch the Docker infrastructure.

3. **Branching Strategy:**
   * `main`: Production and stable release branch.
   * `develop`: Integration branch for active features.
   * `feat/<feature-name>`: Feature branches.
   * `fix/<bug-name>`: Bug fixes.

4. **Testing Requirements:**
   Before submitting any Pull Request, ensure that all automated test suites pass with 100% success rate:
   ```bash
   python scripts/verify_ui_launch.py
   python scripts/verify_full_ui.py
   ```

5. **Style Guidelines:**
   * Python: Follow PEP 8 with explicit type annotations where possible.
   * Templates & CSS: Maintain pure pitch-black styling (`dark:bg-black`, `dark:bg-zinc-950`) without blue background bleeding.
   * JavaScript: Modern ES6+ with robust error handling and WebSocket lifecycle reconnect logic.

---

## Submitting Pull Requests

1. Commit your changes with clear, semantic commit messages (e.g., `feat(deepfake): add multi-face tracking support`).
2. Push your branch to your fork.
3. Open a Pull Request targeting `main`.
4. Detail your proposed changes, testing methodology, and any performance or memory implications.
