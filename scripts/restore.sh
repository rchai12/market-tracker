#!/usr/bin/env bash
# Restore database from a backup file.
#
# Usage:
#   ./scripts/restore.sh /path/to/backup.dump.gz
#   ./scripts/restore.sh --yes /path/to/backup.dump.gz   # Skip confirmation
#
# Environment variables:
#   POSTGRES_DB    — database name (default: stock_predictor)
#   POSTGRES_USER  — database user (default: sp_user)
#   POSTGRES_HOST  — database host (default: localhost)
#   POSTGRES_PORT  — database port (default: 5432)

set -euo pipefail

SKIP_CONFIRM=false
BACKUP_FILE=""

for arg in "$@"; do
    case "${arg}" in
        --yes) SKIP_CONFIRM=true ;;
        *)     BACKUP_FILE="${arg}" ;;
    esac
done

if [ -z "${BACKUP_FILE}" ]; then
    echo "Usage: $0 [--yes] <backup-file.dump.gz>"
    exit 1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

DB_NAME="${POSTGRES_DB:-stock_predictor}"
DB_USER="${POSTGRES_USER:-sp_user}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

echo "=== Database Restore ==="
echo "  File:     ${BACKUP_FILE}"
echo "  Database: ${DB_NAME}"
echo "  Host:     ${DB_HOST}:${DB_PORT}"
echo ""
echo "WARNING: This will drop and recreate all tables in ${DB_NAME}."

if [ "${SKIP_CONFIRM}" = false ]; then
    echo ""
    read -rp "Continue? (y/N) " CONFIRM
    if [ "${CONFIRM}" != "y" ] && [ "${CONFIRM}" != "Y" ]; then
        echo "Aborted."
        exit 0
    fi
fi

echo ""
echo "[$(date -Iseconds)] Stopping backend..."
docker compose stop backend 2>/dev/null || true

echo "[$(date -Iseconds)] Restoring from ${BACKUP_FILE}..."
gunzip -c "${BACKUP_FILE}" | pg_restore \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --username="${DB_USER}" \
    --dbname="${DB_NAME}" \
    --clean \
    --if-exists \
    --no-owner \
    --no-password

echo "[$(date -Iseconds)] Restarting backend..."
docker compose start backend 2>/dev/null || true

echo "[$(date -Iseconds)] Restore complete."
