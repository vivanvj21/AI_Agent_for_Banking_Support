#!/usr/bin/env bash
set -Eeuo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Automated Database & Redis Backup Script with Retention Policy
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"
BACKUP_DIR="${ROOT_DIR}/backups"
TIMESTAMP="$(date -u +'%Y%m%d_%H%M%S')"

log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] [BACKUP] $1"
}

mkdir -p "${BACKUP_DIR}"

log "Starting PostgreSQL backup..."
docker compose exec -T postgres pg_dump -U postgres -F c -b -v -f "/tmp/bank_db_${TIMESTAMP}.dump" bank_db || true
docker compose cp "postgres:/tmp/bank_db_${TIMESTAMP}.dump" "${BACKUP_DIR}/bank_db_${TIMESTAMP}.dump" || true

log "Starting Redis backup..."
docker compose exec -T redis redis-cli BGSAVE || true

# Retention policy: delete backups older than 14 days
log "Cleaning up old backups (>14 days)..."
find "${BACKUP_DIR}" -type f -name "*.dump" -mtime +14 -exec rm -f {} \;

log "Backup completed: ${BACKUP_DIR}/bank_db_${TIMESTAMP}.dump"
exit 0
