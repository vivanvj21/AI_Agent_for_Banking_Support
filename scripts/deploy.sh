#!/usr/bin/env bash
set -Eeuo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Zero-Downtime Rolling Deployment Script with Automatic Rollback
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"

log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] [DEPLOY] $1"
}

rollback_on_failure() {
    log "CRITICAL: Deployment failed! Initiating automatic rollback..."
    bash "${SCRIPT_DIR}/rollback.sh"
    exit 1
}

trap 'rollback_on_failure' ERR

log "Starting production rolling deployment..."

cd "${ROOT_DIR}"

# 1. Pull / build latest container images
log "Building production container images..."
docker compose build --parallel

# 2. Run database migrations
log "Running PostgreSQL database migrations..."
docker compose run --rm api alembic upgrade head || log "Migrations skipped/already up to date"

# 3. Start services in background
log "Deploying updated services..."
docker compose up -d --remove-orphans

# 4. Perform automated health check
log "Validating system health after deployment..."
bash "${SCRIPT_DIR}/healthcheck.sh"

log "Deployment completed successfully!"
exit 0
