#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_dev.sh — Start all services concurrently for development
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PROJECT_ROOT/.env"

# Color codes for process output
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log() { echo -e "${BLUE}[run_dev]${NC} $1"; }

cleanup() {
    log "Shutting down all services..."
    kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

log "Starting AI Defence System — Development Mode"
echo ""

# ── Django ASGI Server (Daphne) ───────────────────────────────────────────────
(
    cd "$PROJECT_ROOT/backend"
    source .venv/bin/activate
    export DJANGO_SETTINGS_MODULE=config.settings.development
    echo -e "${GREEN}[Django]${NC} Starting on http://localhost:8000"
    python manage.py migrate --run-syncdb 2>&1 | sed "s/^/${GREEN}[Django]${NC} /"
    daphne -b 0.0.0.0 -p 8000 config.asgi:application 2>&1 | sed "s/^/${GREEN}[Django]${NC} /"
) &

# ── Celery Worker ─────────────────────────────────────────────────────────────
(
    cd "$PROJECT_ROOT/backend"
    source .venv/bin/activate
    export DJANGO_SETTINGS_MODULE=config.settings.development
    echo -e "${YELLOW}[Celery]${NC} Starting worker..."
    celery -A config worker --loglevel=info --concurrency=2 2>&1 | sed "s/^/${YELLOW}[Celery]${NC} /"
) &

# ── AI Engine (FastAPI + Uvicorn) ─────────────────────────────────────────────
(
    cd "$PROJECT_ROOT"
    source ai_engine/.venv/bin/activate
    echo -e "${CYAN}[AI Engine]${NC} Starting on http://localhost:8001"
    uvicorn ai_engine.server:app --host 0.0.0.0 --port 8001 --workers 1 --reload 2>&1 | \
        sed "s/^/${CYAN}[AI Engine]${NC} /"
) &

echo ""
log "All services starting. URLs:"
log "  Django   → http://localhost:8000"
log "  AI Engine → http://localhost:8001"
log "  Neo4j UI → http://localhost:7474"
log ""
log "Press Ctrl+C to stop all services."
wait
