#!/usr/bin/env bash
set -Eeuo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Multi-Endpoint System Health Check Script
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"

log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] [HEALTHCHECK] $1"
}

API_URL="${API_URL:-http://localhost:8000}"
HEALTH_ENDPOINT="${API_URL}/health/ready"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-15}"
SLEEP_INTERVAL="${SLEEP_INTERVAL:-2}"

log "Starting health check verification against ${HEALTH_ENDPOINT}..."

attempt=1
while [[ ${attempt} -le ${MAX_ATTEMPTS} ]]; do
    log "Attempt ${attempt}/${MAX_ATTEMPTS}: checking health..."
    
    http_code=$(curl -s -o /tmp/health_response.json -w "%{http_code}" "${HEALTH_ENDPOINT}" || echo "000")
    
    if [[ "${http_code}" == "200" ]]; then
        log "SUCCESS: API is healthy (HTTP 200)."
        cat /tmp/health_response.json | jq . || cat /tmp/health_response.json
        exit 0
    else
        log "WARNING: API health check returned HTTP ${http_code}. Retrying in ${SLEEP_INTERVAL}s..."
    fi

    attempt=$((attempt + 1))
    sleep "${SLEEP_INTERVAL}"
done

log "ERROR: System failed health check after ${MAX_ATTEMPTS} attempts."
exit 1
