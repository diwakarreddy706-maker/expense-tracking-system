#!/usr/bin/env bash
# ==============================================================================
# Expense Tracking System - Interactive MySQL Database Restore Script
# Requires explicit safety confirmation before executing any database overwrite.
# ==============================================================================

set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /path/to/backup_file.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file '${BACKUP_FILE}' does not exist!"
    exit 1
fi

# Load DB credentials from .env if present and not set
if [ -f "/var/www/expense_tracking/.env" ]; then
    export $(grep -v '^#' /var/www/expense_tracking/.env | xargs -d '\n')
fi

DB_NAME="${DB_NAME:-expense_tracking_db}"
DB_USER="${DB_USER:-expense_user}"
DB_PASSWORD="${DB_PASSWORD:-}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"

echo "========================================================================"
echo "                   DATABASE RESTORE SAFETY WARNING                      "
echo "========================================================================"
echo "Target Host     : ${DB_HOST}:${DB_PORT}"
echo "Target Database : ${DB_NAME}"
echo "Backup File     : ${BACKUP_FILE}"
echo ""
echo "WARNING: Restoring will OVERWRITE existing data in database '${DB_NAME}'!"
echo "========================================================================"
read -r -p "Type 'RESTORE' to confirm and proceed: " CONFIRMATION

if [ "${CONFIRMATION}" != "RESTORE" ]; then
    echo "Operation aborted by user. No changes were made."
    exit 0
fi

TEMP_SQL=$(mktemp /tmp/ets_restore_XXXXXX.sql)
trap 'rm -f "${TEMP_SQL}"' EXIT

echo "Decompressing backup archive..."
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    gzip -dc "${BACKUP_FILE}" > "${TEMP_SQL}"
else
    cp "${BACKUP_FILE}" "${TEMP_SQL}"
fi

echo "Importing SQL dump into '${DB_NAME}'..."
if [ -n "${DB_PASSWORD}" ]; then
    MYSQL_PWD="${DB_PASSWORD}" mysql \
        --host="${DB_HOST}" \
        --port="${DB_PORT}" \
        --user="${DB_USER}" \
        --default-character-set=utf8mb4 \
        "${DB_NAME}" < "${TEMP_SQL}"
else
    mysql \
        --host="${DB_HOST}" \
        --port="${DB_PORT}" \
        --user="${DB_USER}" \
        --default-character-set=utf8mb4 \
        "${DB_NAME}" < "${TEMP_SQL}"
fi

echo "SUCCESS: Database '${DB_NAME}' restored successfully from ${BACKUP_FILE}."
exit 0
