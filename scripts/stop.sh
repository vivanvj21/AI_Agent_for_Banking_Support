#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"

log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] [STOP] $1"
}

log "Gracefully stopping Docker Compose stack..."
cd "${ROOT_DIR}"
docker compose stop --timeout 30

log "Stack stopped successfully."
exit 0
