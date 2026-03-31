#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "usage: $0 /absolute/or/relative/path/to/backup.sql.gz"
  exit 1
fi

if [ "${RESTORE_CONFIRM:-0}" != "1" ]; then
  echo "Set RESTORE_CONFIRM=1 to run a database restore."
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKUP_FILE="$1"
COMPOSE_CMD="${COMPOSE_CMD:-docker compose -f docker-compose.yml -f docker-compose.prod.yml}"
DB_SERVICE="${BACKUP_DB_SERVICE:-db}"
DB_NAME="${POSTGRES_DB:-shop}"
DB_USER="${POSTGRES_USER:-shop}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "backup file not found: $BACKUP_FILE"
  exit 1
fi

echo "[restore] restoring $BACKUP_FILE into $DB_NAME"
gunzip -c "$BACKUP_FILE" | eval "$COMPOSE_CMD exec -T \"$DB_SERVICE\" psql -U \"$DB_USER\" \"$DB_NAME\""
echo "[restore] completed"
