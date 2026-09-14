#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
#  scripts/run_dev.sh — DEFENCESYS Development Server Launcher
#  Starts Daphne (Django/Channels) + Celery worker + AI Engine (FastAPI).
#
#  Usage:
#    cd /path/to/"AI Deepfake and Phishing Defence System"
#    bash scripts/run_dev.sh
#
#  Prerequisites:
#    - backend/.venv must exist
#    - OrbStack / Docker must be running
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
VENV="$BACKEND/.venv/bin/activate"

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[run_dev]${NC} $*"; }
ok()    { echo -e "${GREEN}[run_dev] ✓${NC} $*"; }
warn()  { echo -e "${YELLOW}[run_dev] ⚠${NC} $*"; }
die()   { echo -e "${RED}[run_dev] ✗${NC} $*"; exit 1; }

info "DEFENCESYS Development Launcher"
info "Repo root: $REPO_ROOT"

# ── Activate virtual environment ──────────────────────────────────────────────
[[ -f "$VENV" ]] || die "Virtual environment not found at $VENV. Run: cd backend && python -m venv .venv && pip install -r requirements.txt"
source "$VENV"
ok "Virtual environment activated"

# ── OrbStack docker path ──────────────────────────────────────────────────────
export PATH=~/.orbstack/bin:$PATH

# ── Environment variables ─────────────────────────────────────────────────────
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=soc_db
export POSTGRES_USER=soc_user
export POSTGRES_PASSWORD=soc_password
export REDIS_URL=redis://localhost:6379/0
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=neo4j_password
export DJANGO_SETTINGS_MODULE=config.settings.development
export AI_ENGINE_BASE_URL=http://localhost:8001

# Prevent Python from buffering stdout/stderr
export PYTHONUNBUFFERED=1

# Optimize Apple Silicon MPS PyTorch memory allocation
# In PyTorch on macOS, setting high watermark requires low watermark <= high watermark.
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.7
export PYTORCH_MPS_LOW_WATERMARK_RATIO=0.5

# ── GGUF model path — absolute so uvicorn subprocess sees it ─────────────────
export GGUF_MODEL_PATH="$REPO_ROOT/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf"

if [[ ! -f "$GGUF_MODEL_PATH" ]]; then
    warn "GGUF model not found at $GGUF_MODEL_PATH"
    warn "AI Engine will start in heuristics-only mode (no LLM inference)"
    warn "To download: bash scripts/download_models.sh"
else
    ok "GGUF model found: $(basename "$GGUF_MODEL_PATH")"
fi

# ── Ensure Docker services are running ───────────────────────────────────────
info "Checking Docker services..."
if docker compose -f "$REPO_ROOT/docker-compose.yml" ps --services --filter status=running 2>/dev/null | grep -q postgres; then
    ok "PostgreSQL, Redis, Neo4j containers are running"
else
    warn "Docker services not detected. Starting them..."
    docker compose -f "$REPO_ROOT/docker-compose.yml" up -d
    info "Waiting 8s for services to become healthy..."
    sleep 8
fi

# ── Run Django migrations ─────────────────────────────────────────────────────
info "Running database migrations..."
cd "$BACKEND"
python manage.py migrate --run-syncdb 2>&1 | tail -5
ok "Migrations done"

# ── Create log directory ──────────────────────────────────────────────────────
mkdir -p "$REPO_ROOT/logs"

# ── Cleanup handler ───────────────────────────────────────────────────────────
AI_ENGINE_PID=""
CELERY_PID=""
DAPHNE_PID=""

cleanup() {
    info "Shutting down all services..."
    [[ -n "$AI_ENGINE_PID" ]] && kill "$AI_ENGINE_PID" 2>/dev/null || true
    [[ -n "$CELERY_PID"    ]] && kill "$CELERY_PID"    2>/dev/null || true
    [[ -n "$DAPHNE_PID"    ]] && kill "$DAPHNE_PID"    2>/dev/null || true
    wait 2>/dev/null || true
    info "All services stopped."
}
trap cleanup EXIT INT TERM

# ── Start AI Engine (FastAPI/uvicorn on port 8001) ────────────────────────────
# CRITICAL: Must start from REPO_ROOT so dlib model relative paths resolve.
info "Starting AI Engine on http://0.0.0.0:8001 ..."
cd "$REPO_ROOT"
uvicorn ai_engine.server:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers 1 \
    --log-level info \
    > "$REPO_ROOT/logs/ai_engine.log" 2>&1 &
AI_ENGINE_PID=$!
ok "AI Engine PID=$AI_ENGINE_PID  ->  logs/ai_engine.log"

# Brief pause so AI Engine binds before Celery tasks can reach it
sleep 2

# ── Start Celery worker ───────────────────────────────────────────────────────
info "Starting Celery worker..."
cd "$BACKEND"
celery -A config worker \
    --loglevel=info \
    --concurrency=2 \
    --max-memory-per-child=512000 \
    > "$REPO_ROOT/logs/celery.log" 2>&1 &
CELERY_PID=$!
ok "Celery PID=$CELERY_PID  ->  logs/celery.log"

# ── Start Daphne (Django Channels ASGI server) ────────────────────────────────
info "Starting Daphne on http://0.0.0.0:8000 ..."
daphne \
    -b 0.0.0.0 \
    -p 8000 \
    --verbosity 1 \
    config.asgi:application \
    > "$REPO_ROOT/logs/daphne.log" 2>&1 &
DAPHNE_PID=$!
ok "Daphne PID=$DAPHNE_PID  ->  logs/daphne.log"

echo ""
echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}  DEFENCESYS running at  http://localhost:8000${NC}"
echo -e "${GREEN}  AI Engine (FastAPI)     http://localhost:8001${NC}"
echo -e "${GREEN}  AI Engine Health        http://localhost:8001/health${NC}"
echo -e "${GREEN}  Neo4j Browser           http://localhost:7474${NC}"
echo -e "${GREEN}  Logs:  logs/daphne.log  |  logs/celery.log  |  logs/ai_engine.log${NC}"
echo -e "${GREEN}  Press Ctrl+C to stop all services${NC}"
echo -e "${GREEN}=====================================================${NC}"

# ── Wait indefinitely (cleanup runs on exit) ──────────────────────────────────
wait
