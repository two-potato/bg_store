#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_SCRIPT="$ROOT_DIR/scripts/backup_postgres.sh"
FRESHNESS_SCRIPT="$ROOT_DIR/scripts/check_backup_freshness.sh"
LOG_DIR="${BACKUP_CRON_LOG_DIR:-$ROOT_DIR/logs}"
mkdir -p "$LOG_DIR"

BACKUP_SCHEDULE="${BACKUP_CRON_SCHEDULE:-10 2 * * *}"
CHECK_SCHEDULE="${BACKUP_CHECK_CRON_SCHEDULE:-15 * * * *}"

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

{
  crontab -l 2>/dev/null | grep -v "servio_backup_postgres" | grep -v "servio_backup_freshness" || true
  echo "$BACKUP_SCHEDULE BACKUP_DIR=\"${BACKUP_DIR:-$ROOT_DIR/backups/postgres}\" RETENTION_DAYS=\"${RETENTION_DAYS:-14}\" \"$BACKUP_SCRIPT\" >> \"$LOG_DIR/backup_postgres.log\" 2>&1 # servio_backup_postgres"
  echo "$CHECK_SCHEDULE BACKUP_DIR=\"${BACKUP_DIR:-$ROOT_DIR/backups/postgres}\" MAX_AGE_HOURS=\"${MAX_AGE_HOURS:-26}\" \"$FRESHNESS_SCRIPT\" >> \"$LOG_DIR/backup_freshness.log\" 2>&1 # servio_backup_freshness"
} > "$tmpfile"

crontab "$tmpfile"
echo "[backup-cron] installed backup and freshness cron entries"
