#!/usr/bin/env python3
"""
Deep Audit Script
=================
Automated CI/CD security check for the AI Defense System.
Checks:
  1. corsheaders is loaded before CommonMiddleware in settings
  2. CharField has max_length specified in models
  3. No raw innerHTML usage in templates
  4. Template |safe filter checks
"""
import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def check_middleware() -> list[str]:
    errors = []
    settings_path = BASE_DIR / "backend" / "config" / "settings" / "base.py"
    if not settings_path.exists():
        return ["settings/base.py not found"]

    content = settings_path.read_text()
    match = re.search(r"MIDDLEWARE\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if match:
        middlewares = [m.strip().strip('"\'') for m in match.group(1).split(",") if m.strip()]
        try:
            cors_idx = middlewares.index("corsheaders.middleware.CorsMiddleware")
            common_idx = middlewares.index("django.middleware.common.CommonMiddleware")
            if cors_idx > common_idx:
                errors.append("CorsMiddleware must appear BEFORE CommonMiddleware in settings")
        except ValueError:
            pass
    return errors


def check_models() -> list[str]:
    errors = []
    for path in (BASE_DIR / "backend" / "apps").rglob("models.py"):
        content = path.read_text()
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "models.CharField" in line and "max_length" not in line:
                errors.append(f"{path.relative_to(BASE_DIR)}:{i+1} — CharField missing max_length")
    return errors


def check_templates() -> list[str]:
    errors = []
    for path in (BASE_DIR / "backend" / "templates").rglob("*.html"):
        content = path.read_text()
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if ".innerHTML" in line and "=''" not in line.replace(" ", "") and '=""' not in line.replace(" ", ""):
                errors.append(f"{path.relative_to(BASE_DIR)}:{i+1} — .innerHTML usage detected (XSS risk). Use DOM API textContent instead.")
            if "|safe" in line and "script" in line:
                errors.append(f"{path.relative_to(BASE_DIR)}:{i+1} — |safe filter used near script tags.")
    return errors


def main():
    print("Starting Deep Audit...")
    errors = []
    errors.extend(check_middleware())
    errors.extend(check_models())
    errors.extend(check_templates())

    if errors:
        print(f"\n❌ Audit failed with {len(errors)} errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    
    print("\n✅ All security checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
