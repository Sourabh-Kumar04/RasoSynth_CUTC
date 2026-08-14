#!/usr/bin/env bash
# PostgreSQL backup script for RasoDataset-Agent
# Usage: ./scripts/backup.sh [output_dir]
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PG_USER="${PG_USER:-postgres}"
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_DB="${PG_DB:-dataset_engine}"
PG_PASSWORD="${PG_PASSWORD:-}"

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="${BACKUP_DIR}/dataset_engine_${TIMESTAMP}.sql.gz"
LOG_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting backup of ${PG_DB}..." | tee -a "$LOG_FILE"

export PGPASSWORD="$PG_PASSWORD"

if pg_dump -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
    --format=custom \
    --compress=9 \
    --file="${BACKUP_FILE%.gz}" \
    2>> "$LOG_FILE"; then
    # Compress the dump
    gzip -f "${BACKUP_FILE%.gz}"
    FILESIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null || echo "unknown")
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup complete: ${BACKUP_FILE} (${FILESIZE} bytes)" | tee -a "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WAL archive: ensure archive_mode=on in postgresql.conf" | tee -a "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup FAILED!" | tee -a "$LOG_FILE"
    exit 1
fi

# Rotate backups older than 30 days
find "$BACKUP_DIR" -name "dataset_engine_*.sql.gz" -mtime +30 -delete 2>/dev/null
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleaned up backups older than 30 days" | tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done." | tee -a "$LOG_FILE"
