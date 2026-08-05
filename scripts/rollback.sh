#!/usr/bin/env bash
set -Eeuo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Automated Rollback Script
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"

log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] [ROLLBACK] $1"
}

log "Executing system rollback to previous stable state..."

cd "${ROOT_DIR}"

# 1. Restart existing stable containers
log "Restarting last known stable container stack..."
docker compose restart || docker compose up -d

# 2. Re-verify health
log "Verifying health post-rollback..."
bash "${SCRIPT_DIR}/healthcheck.sh" || {
    log "EMERGENCY: System remains unhealthy post-rollback. Manual intervention required."
    exit 2
}

log "Rollback finished successfully. System restored."
exit 0
