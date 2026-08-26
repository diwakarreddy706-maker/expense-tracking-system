#!/usr/bin/env bash
# ==============================================================================
# Expense Tracking System - Automated MySQL Database Backup Script
# Performs transactional consistency dump, gzip compression, and 30-day pruning.
# ==============================================================================

set -euo pipefail

# Configuration (Overrides via environment variables)
BACKUP_DIR="${BACKUP_DIR:-/var/backups/expense_tracking}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/ets_backup_${TIMESTAMP}.sql.gz"
LOG_FILE="${BACKUP_DIR}/backup.log"

# Load DB credentials from .env if present and not set
if [ -f "/var/www/expense_tracking/.env" ]; then
    export $(grep -v '^#' /var/www/expense_tracking/.env | xargs -d '\n')
fi

DB_NAME="${DB_NAME:-expense_tracking_db}"
DB_USER="${DB_USER:-expense_user}"
DB_PASSWORD="${DB_PASSWORD:-}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"

mkdir -p "${BACKUP_DIR}"

log() {
    local msg="[$(date +'%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg"
    echo "$msg" >> "${LOG_FILE}"
}

log "Starting automated backup for database '${DB_NAME}'..."

# Verify mysqldump is available
if ! command -v mysqldump &> /dev/null; then
    log "ERROR: 'mysqldump' command not found. Please install mysql-client."
    exit 1
fi

# Execute transactional mysqldump with compression
log "Dumping database schema, tables, triggers, and stored routines..."
if [ -n "${DB_PASSWORD}" ]; then
    MYSQL_PWD="${DB_PASSWORD}" mysqldump \
        --host="${DB_HOST}" \
        --port="${DB_PORT}" \
        --user="${DB_USER}" \
        --single-transaction \
        --quick \
        --routines \
        --triggers \
        --default-character-set=utf8mb4 \
        "${DB_NAME}" | gzip -9 > "${BACKUP_FILE}"
else
    mysqldump \
        --host="${DB_HOST}" \
        --port="${DB_PORT}" \
        --user="${DB_USER}" \
        --single-transaction \
        --quick \
        --routines \
        --triggers \
        --default-character-set=utf8mb4 \
        "${DB_NAME}" | gzip -9 > "${BACKUP_FILE}"
fi

# Integrity verification
if [ -f "${BACKUP_FILE}" ] && [ -s "${BACKUP_FILE}" ]; then
    FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    log "SUCCESS: Backup completed successfully: ${BACKUP_FILE} (Size: ${FILE_SIZE})"
else
    log "ERROR: Backup file ${BACKUP_FILE} is missing or empty! Backup failed."
    exit 1
fi

# Prune old backups past retention threshold
log "Pruning backups older than ${RETENTION_DAYS} days..."
DELETED_COUNT=$(find "${BACKUP_DIR}" -type f -name "ets_backup_*.sql.gz" -mtime +"${RETENTION_DAYS}" -print -delete | wc -l)
log "Pruning complete. Removed ${DELETED_COUNT} expired backup file(s)."

log "Backup job finished cleanly."
exit 0
