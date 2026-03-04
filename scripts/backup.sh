#!/usr/bin/env bash
# Database backup with configurable retention.
#
# Usage:
#   ./scripts/backup.sh
#
# Environment variables:
#   BACKUP_DIR       — where to store backups (default: /var/backups/stock-predictor)
#   RETENTION_DAYS   — delete backups older than N days (default: 7)
#   POSTGRES_DB      — database name (default: stock_predictor)
#   POSTGRES_USER    — database user (default: sp_user)
#   POSTGRES_HOST    — database host (default: localhost)
#   POSTGRES_PORT    — database port (default: 5432)
#
# Crontab example (daily at 2 AM):
#   0 2 * * * /opt/stock-predictor/scripts/backup.sh >> /var/log/stock-predictor-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/stock-predictor}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
DB_NAME="${POSTGRES_DB:-stock_predictor}"
DB_USER="${POSTGRES_USER:-sp_user}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILENAME="${DB_NAME}_${TIMESTAMP}.dump.gz"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] Starting backup of ${DB_NAME}..."

pg_dump \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --username="${DB_USER}" \
    --format=custom \
    --no-password \
    "${DB_NAME}" | gzip > "${FILEPATH}"

SIZE="$(du -h "${FILEPATH}" | cut -f1)"
echo "[$(date -Iseconds)] Backup complete: ${FILEPATH} (${SIZE})"

# Retention cleanup
DELETED="$(find "${BACKUP_DIR}" -name "*.dump.gz" -mtime +"${RETENTION_DAYS}" -print -delete | wc -l)"
if [ "${DELETED}" -gt 0 ]; then
    echo "[$(date -Iseconds)] Deleted ${DELETED} backup(s) older than ${RETENTION_DAYS} days"
fi

echo "[$(date -Iseconds)] Done."
