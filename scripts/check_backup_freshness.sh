#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups/postgres}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-26}"
PATTERN="${BACKUP_PATTERN:-servio-postgres-*.sql.gz}"
METRIC_FILE="${BACKUP_METRIC_FILE:-}"

if [ ! -d "$BACKUP_DIR" ]; then
  echo "[backup-check] backup dir does not exist: $BACKUP_DIR"
  exit 2
fi

latest_file="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name "$PATTERN" -printf '%T@ %p\n' | sort -nr | head -n 1 | awk '{print $2}')"
if [ -z "${latest_file:-}" ]; then
  echo "[backup-check] no backup files found in $BACKUP_DIR"
  exit 2
fi

latest_mtime="$(stat -c %Y "$latest_file")"
now_epoch="$(date +%s)"
age_seconds="$((now_epoch - latest_mtime))"
age_hours="$((age_seconds / 3600))"

if [ -n "$METRIC_FILE" ]; then
  mkdir -p "$(dirname "$METRIC_FILE")"
  {
    echo "# HELP servio_backup_age_hours Age of latest PostgreSQL backup in hours"
    echo "# TYPE servio_backup_age_hours gauge"
    echo "servio_backup_age_hours ${age_hours}"
    echo "# HELP servio_backup_latest_timestamp_seconds Unix timestamp of latest backup"
    echo "# TYPE servio_backup_latest_timestamp_seconds gauge"
    echo "servio_backup_latest_timestamp_seconds ${latest_mtime}"
  } > "$METRIC_FILE"
fi

if [ "$age_hours" -gt "$MAX_AGE_HOURS" ]; then
  echo "[backup-check] stale backup detected: ${age_hours}h old (max ${MAX_AGE_HOURS}h), file=${latest_file}"
  exit 1
fi

echo "[backup-check] backup freshness OK: ${age_hours}h old, file=${latest_file}"
