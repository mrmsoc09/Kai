#!/bin/bash
# Kaison AI - PostgreSQL Backup Script
# This script performs a pg_dump of the K1 database.

set -e

# Configuration
BACKUP_DIR="/app/artifacts/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/k1_backup_${TIMESTAMP}.sql.gz"
DB_NAME="k1"
DB_USER="k1"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

echo "Starting backup of database '${DB_NAME}' to ${BACKUP_FILE}..."

# Perform backup
# We assume pg_dump is available and PG_PASSWORD is set or handled via .pgpass
pg_dump -U "$DB_USER" -h postgres "$DB_NAME" | gzip > "$BACKUP_FILE"

echo "Backup completed successfully."

# Retention: Delete backups older than 90 days
find "$BACKUP_DIR" -type f -name "k1_backup_*.sql.gz" -mtime +90 -delete

echo "Old backups cleaned up."
