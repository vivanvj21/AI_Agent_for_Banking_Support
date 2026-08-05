#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"

log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] [START] $1"
}

log "Starting Autonomous Banking Assistant stack via Docker Compose..."
cd "${ROOT_DIR}"
docker compose up -d

log "Verifying health..."
bash "${SCRIPT_DIR}/healthcheck.sh"
log "Stack started successfully."
exit 0
