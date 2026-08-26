#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_CMD="${COMPOSE_CMD:-docker compose -f docker-compose.yml -f docker-compose.prod.yml}"
DB_SERVICE="${BACKUP_DB_SERVICE:-db}"
DB_NAME="${POSTGRES_DB:-shop}"
DB_USER="${POSTGRES_USER:-shop}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

timestamp="$(date -u +%Y%m%d-%H%M%S)"
output_path="$BACKUP_DIR/servio-postgres-$timestamp.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[backup] creating PostgreSQL dump at $output_path"
eval "$COMPOSE_CMD exec -T \"$DB_SERVICE\" pg_dump -U \"$DB_USER\" \"$DB_NAME\"" | gzip > "$output_path"

find "$BACKUP_DIR" -type f -name 'servio-postgres-*.sql.gz' -mtime "+$RETENTION_DAYS" -delete

echo "[backup] completed: $output_path"
