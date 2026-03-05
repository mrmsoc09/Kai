#!/usr/bin/env bash
# K1 PostgreSQL Backup Script
#
# Keeps 7 daily and 4 weekly backups in BACKUP_DIR.
# Intended to be run as a daily cron job:
#   0 2 * * * /app/scripts/backup_db.sh >> /var/log/k1-backup.log 2>&1
#
# Environment variables (can be set via .env.prod or Docker env):
#   DATABASE_URL  — full PostgreSQL connection URL (preferred)
#   POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
#   BACKUP_DIR    — destination directory (default: /var/backups/k1)

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/k1}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DAILY_DIR="${BACKUP_DIR}/daily"
WEEKLY_DIR="${BACKUP_DIR}/weekly"
KEEP_DAILY=7
KEEP_WEEKLY=4

# ---------------------------------------------------------------------------
# Parse connection from DATABASE_URL if set
# ---------------------------------------------------------------------------
if [[ -n "${DATABASE_URL:-}" ]]; then
    # Expected format: postgresql://user:password@host:port/dbname
    POSTGRES_USER=$(echo "$DATABASE_URL" | sed -E 's|.*://([^:]+):.*|\1|')
    POSTGRES_PASSWORD=$(echo "$DATABASE_URL" | sed -E 's|.*://[^:]+:([^@]+)@.*|\1|')
    POSTGRES_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+)[:/].*|\1|')
    POSTGRES_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*@[^:]+:([0-9]+)/.*|\1|')
    POSTGRES_DB=$(echo "$DATABASE_URL" | sed -E 's|.*/([^?]+).*|\1|')
fi

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-k1}"
POSTGRES_DB="${POSTGRES_DB:-k1}"

export PGPASSWORD="${POSTGRES_PASSWORD:-}"

mkdir -p "$DAILY_DIR" "$WEEKLY_DIR"

BACKUP_FILE="${DAILY_DIR}/k1_${TIMESTAMP}.sql.gz"

echo "[$(date -Iseconds)] Starting backup → ${BACKUP_FILE}"

pg_dump \
    --host="$POSTGRES_HOST" \
    --port="$POSTGRES_PORT" \
    --username="$POSTGRES_USER" \
    --format=plain \
    --no-password \
    "$POSTGRES_DB" | gzip > "$BACKUP_FILE"

echo "[$(date -Iseconds)] Backup complete ($(du -sh "$BACKUP_FILE" | cut -f1))"

# ---------------------------------------------------------------------------
# Weekly copy (every Sunday)
# ---------------------------------------------------------------------------
if [[ "$(date +%u)" == "7" ]]; then
    WEEKLY_FILE="${WEEKLY_DIR}/k1_weekly_${TIMESTAMP}.sql.gz"
    cp "$BACKUP_FILE" "$WEEKLY_FILE"
    echo "[$(date -Iseconds)] Weekly snapshot saved → ${WEEKLY_FILE}"
fi

# ---------------------------------------------------------------------------
# Retention: remove old backups
# ---------------------------------------------------------------------------
echo "[$(date -Iseconds)] Pruning daily backups (keeping ${KEEP_DAILY})..."
ls -1t "${DAILY_DIR}"/k1_*.sql.gz 2>/dev/null | tail -n +$((KEEP_DAILY + 1)) | xargs -r rm -v

echo "[$(date -Iseconds)] Pruning weekly backups (keeping ${KEEP_WEEKLY})..."
ls -1t "${WEEKLY_DIR}"/k1_weekly_*.sql.gz 2>/dev/null | tail -n +$((KEEP_WEEKLY + 1)) | xargs -r rm -v

echo "[$(date -Iseconds)] Backup job finished."
