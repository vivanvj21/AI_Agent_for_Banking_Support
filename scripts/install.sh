#!/usr/bin/env bash
set -Eeuo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Installation Script for Autonomous Banking Assistant System
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"

log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] [INSTALL] $1"
}

error_handler() {
    log "ERROR: Installation failed at line $1"
    exit 1
}

trap 'error_handler $LINENO' ERR

log "Starting enterprise system installation..."

# 1. Verify OS
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    log "Detected OS: ${NAME} ${VERSION_ID}"
fi

# 2. Update system & install dependencies
log "Installing system package dependencies..."
sudo apt-get update -qq && sudo apt-get install -y -qq \
    curl \
    git \
    build-essential \
    libpq-dev \
    python3-dev \
    python3-pip \
    jq \
    ca-certificates

# 3. Verify Docker installation
if ! command -v docker &> /dev/null; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER" || true
else
    log "Docker is already installed: $(docker --version)"
fi

# 4. Verify Docker Compose plugin
if ! docker compose version &> /dev/null; then
    log "Installing Docker Compose plugin..."
    sudo apt-get install -y -qq docker-compose-plugin
fi

log "Docker Compose version: $(docker compose version)"

# 5. Initialize environment file if missing
if [[ ! -f "${ROOT_DIR}/.env" ]]; then
    log "Copying .env.example to .env..."
    cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
fi

log "Installation completed successfully."
exit 0
