#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
#  scripts/run_dev.sh — DEFENCESYS Development Server Launcher
#  Starts Daphne (Django/Channels) + Celery worker concurrently.
#
#  Usage:
#    cd /path/to/AI\ Deepfake\ and\ Phishing\ Defence\ System
#    bash scripts/run_dev.sh
#
#  Prerequisites:
#    - backend/.venv must exist (source it automatically)
#    - OrbStack / Docker running: docker compose up -d
#    - POSTGRES_HOST is set to localhost (done in this script)
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
cleanup() {
    info "Shutting down all services..."
    kill "$DAPHNE_PID" "$CELERY_PID" 2>/dev/null || true
    wait "$DAPHNE_PID" "$CELERY_PID" 2>/dev/null || true
    info "All services stopped."
}
trap cleanup EXIT INT TERM

# ── Start Celery worker ───────────────────────────────────────────────────────
info "Starting Celery worker..."
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
echo -e "${GREEN}  Neo4j Browser          http://localhost:7474${NC}"
echo -e "${GREEN}  Logs: logs/daphne.log  logs/celery.log${NC}"
echo -e "${GREEN}  Press Ctrl+C to stop all services${NC}"
echo -e "${GREEN}=====================================================${NC}"

# ── Wait indefinitely (cleanup runs on exit) ──────────────────────────────────
wait
