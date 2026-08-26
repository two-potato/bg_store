#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-servio}"
DB_SERVICE="${DB_SERVICE:-${STACK_NAME}_db}"
PROD_ENV_FILE="${PROD_ENV_FILE:-/opt/servio/shared/.env.prod}"
BACKUP_DIR="${BACKUP_DIR:-/opt/servio/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
REMOTE_BACKUP_HOST="${REMOTE_BACKUP_HOST:-root@192.168.0.5}"
REMOTE_BACKUP_DIR="${REMOTE_BACKUP_DIR:-/opt/servio/backups/postgres}"
SSH_OPTIONS="${SSH_OPTIONS:--o BatchMode=yes -o ConnectTimeout=10}"

if [[ ! -f "$PROD_ENV_FILE" ]]; then
  echo "Production env file missing: $PROD_ENV_FILE" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "$PROD_ENV_FILE"
set +a

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"

container_id="$(docker ps --filter "label=com.docker.swarm.service.name=${DB_SERVICE}" --format '{{.ID}}' | head -n1)"
if [[ -z "$container_id" ]]; then
  echo "No running PostgreSQL task found for service $DB_SERVICE" >&2
  docker service ps "$DB_SERVICE" --no-trunc >&2 || true
  exit 1
fi

mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%d-%H%M%S)"
final_path="$BACKUP_DIR/servio-postgres-$timestamp.sql.gz"
tmp_path="$final_path.tmp"

cleanup() {
  rm -f "$tmp_path"
}
trap cleanup EXIT

echo "[backup] dumping $POSTGRES_DB from $DB_SERVICE"
docker exec "$container_id" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl | gzip -9 > "$tmp_path"
test -s "$tmp_path"
gzip -t "$tmp_path"
mv "$tmp_path" "$final_path"
trap - EXIT

find "$BACKUP_DIR" -type f -name 'servio-postgres-*.sql.gz' -mtime "+$RETENTION_DAYS" -delete

if [[ -n "$REMOTE_BACKUP_HOST" ]]; then
  echo "[backup] copying off-node to $REMOTE_BACKUP_HOST:$REMOTE_BACKUP_DIR"
  # Intentional word splitting for SSH_OPTIONS.
  # shellcheck disable=SC2086
  ssh $SSH_OPTIONS "$REMOTE_BACKUP_HOST" "mkdir -p '$REMOTE_BACKUP_DIR' && find '$REMOTE_BACKUP_DIR' -type f -name 'servio-postgres-*.sql.gz' -mtime +$RETENTION_DAYS -delete"
  # shellcheck disable=SC2086
  scp $SSH_OPTIONS "$final_path" "$REMOTE_BACKUP_HOST:$REMOTE_BACKUP_DIR/"
fi

date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP_DIR/.last-success"
echo "[backup] completed: $final_path"
