#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_env.sh — One-shot bootstrap for the AI Defence System (macOS M4)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "📁 Project root: $PROJECT_ROOT"

# ── 1. Check prerequisites ────────────────────────────────────────────────────
echo ""
echo "🔍 Checking prerequisites..."
command -v python3 >/dev/null || { echo "❌ python3 not found. Install from python.org"; exit 1; }
command -v brew >/dev/null || { echo "❌ Homebrew not found. Install from brew.sh"; exit 1; }
command -v docker >/dev/null || { echo "⚠️  Docker not found. Neo4j + Redis won't auto-start"; }

# ── 2. System services via Homebrew ───────────────────────────────────────────
echo ""
echo "📦 Installing system dependencies..."
brew install postgresql@16 redis 2>/dev/null || echo "  (already installed)"
brew services start postgresql@16 || true
brew services start redis || true

# ── 3. Copy .env ──────────────────────────────────────────────────────────────
echo ""
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    # Generate a random Django secret key
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/change-me-to-a-long-random-string/$SECRET/" "$PROJECT_ROOT/.env"
    else
        sed -i "s/change-me-to-a-long-random-string/$SECRET/" "$PROJECT_ROOT/.env"
    fi
    echo "✅ Created .env (secret key auto-generated)"
else
    echo "  .env already exists — skipping"
fi

# ── 4. Backend virtual environment ────────────────────────────────────────────
echo ""
echo "🐍 Setting up backend virtual environment..."
cd "$PROJECT_ROOT/backend"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ Backend deps installed"

# ── 5. PostgreSQL database setup ──────────────────────────────────────────────
echo ""
echo "🗄️  Setting up PostgreSQL..."
source "$PROJECT_ROOT/.env"
psql postgres -c "CREATE USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD';" 2>/dev/null || echo "  User exists"
psql postgres -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;" 2>/dev/null || echo "  Database exists"
deactivate

# ── 6. AI Engine virtual environment ─────────────────────────────────────────
echo ""
echo "🤖 Setting up AI engine virtual environment..."
cd "$PROJECT_ROOT/ai_engine"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q

# Install PyTorch with MPS support (macOS)
echo "  Installing PyTorch (MPS)..."
pip install torch torchvision torchaudio -q

# Install remaining AI deps
pip install -r requirements.txt -q
echo "✅ AI engine deps installed"

# Verify MPS
python3 -c "
import torch
if torch.backends.mps.is_available():
    print('  ✅ MPS (Apple Metal) is AVAILABLE')
else:
    print('  ⚠️  MPS not available — will use CPU')
"
deactivate


# ── 8. Docker services (Neo4j + Redis) ────────────────────────────────────────
echo ""
if command -v docker >/dev/null; then
    echo "🐳 Starting Docker services (Neo4j + Redis)..."
    cd "$PROJECT_ROOT"
    docker compose up -d
    echo "✅ Docker services started"
    echo "   Neo4j browser: http://localhost:7474"
fi

echo ""
echo "═══════════════════════════════════════════════════"
echo "✅ Setup complete! Next steps:"
echo "   1. Run Django migrations:  cd backend && source .venv/bin/activate && python manage.py migrate"
echo "   2. Start all services:     ./scripts/run_dev.sh"
echo "   3. Download LLM model:     ./scripts/download_models.sh"
echo "═══════════════════════════════════════════════════"
