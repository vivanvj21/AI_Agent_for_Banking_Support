#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"

log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] [RESTART] $1"
}

log "Restarting Docker Compose stack..."
cd "${ROOT_DIR}"
bash "${SCRIPT_DIR}/stop.sh"
bash "${SCRIPT_DIR}/start.sh"
log "Restart completed successfully."
exit 0
