#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Autonomous Bank Assistant — Linux/macOS deployment helper
#
# Usage:
#   ./deploy.sh setup       Install deps into a venv
#   ./deploy.sh dev         Run Streamlit in dev mode
#   ./deploy.sh api         Run FastAPI in dev mode
#   ./deploy.sh docker      Build and start Docker Compose stack
#   ./deploy.sh docker-dev  Start Docker Compose in dev mode (live reload)
#   ./deploy.sh stop        Stop Docker Compose services
#   ./deploy.sh logs        Tail Docker Compose logs
#   ./deploy.sh health      Check API health endpoint
#   ./deploy.sh init-db     Initialize database (local Python)
#   ./deploy.sh clean       Remove Docker volumes (WARNING: destroys data)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE=".env"
VENV_DIR=".venv"
PYTHON="${PYTHON:-python3}"
COMPOSE="docker compose"

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Preflight checks ──────────────────────────────────────────────────────────
check_env_file() {
    if [[ ! -f "$ENV_FILE" ]]; then
        warn ".env not found. Copying from .env.example..."
        cp .env.example .env
        warn "Please edit .env and set ANTHROPIC_API_KEY, then re-run."
        exit 1
    fi
}

check_api_key() {
    if grep -qE "^ANTHROPIC_API_KEY=sk-ant-your-key-here$" "$ENV_FILE" 2>/dev/null; then
        error "ANTHROPIC_API_KEY is still the placeholder. Edit .env first."
    fi
    if grep -qE "^ANTHROPIC_API_KEY=$" "$ENV_FILE" 2>/dev/null; then
        error "ANTHROPIC_API_KEY is blank. Edit .env first."
    fi
}

# ── Commands ──────────────────────────────────────────────────────────────────

cmd_setup() {
    info "Creating virtual environment in $VENV_DIR..."
    "$PYTHON" -m venv "$VENV_DIR"
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip
    pip install -r requirements.txt
    success "Virtual environment ready. Activate with: source $VENV_DIR/bin/activate"
    echo ""
    info "Next steps:"
    echo "  1. cp .env.example .env"
    echo "  2. Edit .env and set ANTHROPIC_API_KEY"
    echo "  3. python start.py check"
    echo "  4. python start.py"
}

cmd_dev() {
    check_env_file
    # shellcheck source=/dev/null
    [[ -f "$VENV_DIR/bin/activate" ]] && source "$VENV_DIR/bin/activate"
    info "Starting Streamlit in development mode..."
    python start.py streamlit
}

cmd_api() {
    check_env_file
    [[ -f "$VENV_DIR/bin/activate" ]] && source "$VENV_DIR/bin/activate"
    info "Starting FastAPI (dev, auto-reload)..."
    python start.py api --reload
}

cmd_docker() {
    check_env_file
    check_api_key
    info "Building and starting Docker Compose stack..."
    $COMPOSE up --build -d
    success "Stack started."
    echo ""
    info "Services:"
    echo "  Streamlit UI : http://localhost:${STREAMLIT_PORT:-8501}"
    echo "  FastAPI      : http://localhost:${API_PORT:-8000}"
    echo "  API Docs     : http://localhost:${API_PORT:-8000}/docs"
    echo ""
    info "Logs: ./deploy.sh logs"
    info "Stop: ./deploy.sh stop"
}

cmd_docker_dev() {
    check_env_file
    info "Starting Docker Compose in dev mode (live code reload)..."
    $COMPOSE -f docker-compose.yml -f docker-compose.dev.yml up --build
}

cmd_stop() {
    info "Stopping Docker Compose services..."
    $COMPOSE down
    success "Stopped."
}

cmd_logs() {
    $COMPOSE logs -f --tail=100
}

cmd_health() {
    API_PORT="${API_PORT:-8000}"
    info "Checking health at http://localhost:${API_PORT}/health..."
    curl -sf "http://localhost:${API_PORT}/health" | python3 -m json.tool || \
        error "Health check failed. Is the API running?"
}

cmd_init_db() {
    [[ -f "$VENV_DIR/bin/activate" ]] && source "$VENV_DIR/bin/activate"
    info "Initializing database..."
    python start.py init-db
    success "Database initialized."
}

cmd_clean() {
    warn "This will DELETE all Docker volumes (database, Chroma, logs)."
    read -rp "Are you sure? (yes/no): " confirm
    if [[ "$confirm" == "yes" ]]; then
        $COMPOSE down -v
        success "Volumes removed."
    else
        info "Aborted."
    fi
}

# ── Entry point ───────────────────────────────────────────────────────────────
COMMAND="${1:-help}"

case "$COMMAND" in
    setup)       cmd_setup ;;
    dev)         cmd_dev ;;
    api)         cmd_api ;;
    docker)      cmd_docker ;;
    docker-dev)  cmd_docker_dev ;;
    stop)        cmd_stop ;;
    logs)        cmd_logs ;;
    health)      cmd_health ;;
    init-db)     cmd_init_db ;;
    clean)       cmd_clean ;;
    help|--help|-h)
        echo ""
        echo "  Autonomous Bank Assistant — deployment helper"
        echo ""
        echo "  Usage: ./deploy.sh <command>"
        echo ""
        echo "  Commands:"
        echo "    setup        Create venv and install Python dependencies"
        echo "    dev          Run Streamlit UI locally"
        echo "    api          Run FastAPI locally (with auto-reload)"
        echo "    docker       Build and start Docker Compose (background)"
        echo "    docker-dev   Start Docker Compose with live code reload"
        echo "    stop         Stop Docker Compose services"
        echo "    logs         Tail Docker Compose logs"
        echo "    health       Check FastAPI /health endpoint"
        echo "    init-db      Initialize/seed SQLite database"
        echo "    clean        Remove all Docker volumes (destructive!)"
        echo ""
        ;;
    *)
        error "Unknown command: $COMMAND. Run './deploy.sh help' for usage."
        ;;
esac
