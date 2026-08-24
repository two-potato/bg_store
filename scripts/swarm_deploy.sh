#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STACK_NAME="${STACK_NAME:-servio}"
IMAGE_TAG="${IMAGE_TAG:-}"
IMAGE_PREFIX="${IMAGE_PREFIX:-ghcr.io/two-potato/servio}"
PROD_ENV_FILE="${PROD_ENV_FILE:-/opt/servio/shared/.env.prod}"
PROD_BOT_ENV_FILE="${PROD_BOT_ENV_FILE:-/opt/servio/shared/.env.bot}"
PROD_BOT_NOTIFY_ENV_FILE="${PROD_BOT_NOTIFY_ENV_FILE:-/opt/servio/shared/.env.bot-notify}"
LETSENCRYPT_DIR="${LETSENCRYPT_DIR:-/opt/servio/shared/letsencrypt}"
LETSENCRYPT_LIB_DIR="${LETSENCRYPT_LIB_DIR:-/opt/servio/shared/letsencrypt-lib}"
CERTBOT_WWW_DIR="${CERTBOT_WWW_DIR:-/opt/servio/shared/certbot-www}"
LETSENCRYPT_DOMAIN="${LETSENCRYPT_DOMAIN:-24sparts.ru}"
LETSENCRYPT_WWW_DOMAIN="${LETSENCRYPT_WWW_DOMAIN:-www.24sparts.ru}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"
DEPLOY_DIR="${DEPLOY_DIR:-$ROOT_DIR/.deploy}"
STACK_FILE="${STACK_FILE:-$ROOT_DIR/deploy/swarm/stack.yml}"
SKIP_MIGRATIONS="${SKIP_MIGRATIONS:-0}"
ALLOW_RISKY_MIGRATIONS="${ALLOW_RISKY_MIGRATIONS:-0}"

DESIRED_BACKEND_REPLICAS="${BACKEND_REPLICAS:-1}"
DESIRED_FRONTEND_REPLICAS="${FRONTEND_REPLICAS:-1}"
DESIRED_CELERY_WORKER_REPLICAS="${CELERY_WORKER_REPLICAS:-1}"
DESIRED_CELERY_BEAT_REPLICAS="${CELERY_BEAT_REPLICAS:-1}"
DESIRED_BOT_REPLICAS="${BOT_REPLICAS:-1}"
DESIRED_BOT_NOTIFY_REPLICAS="${BOT_NOTIFY_REPLICAS:-1}"

log() {
  printf '[swarm-deploy][%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

fail_diagnostics() {
  local rc=$?
  log "Deployment failed with exit code $rc"
  docker stack services "$STACK_NAME" >&2 || true
  docker stack ps "$STACK_NAME" --no-trunc >&2 || true
  exit "$rc"
}
trap fail_diagnostics ERR

if [[ -z "$IMAGE_TAG" ]]; then
  echo "IMAGE_TAG is required" >&2
  exit 2
fi
if [[ "$(docker info --format '{{.Swarm.ControlAvailable}}')" != "true" ]]; then
  echo "This script must run on a Swarm manager" >&2
  exit 2
fi
for file in "$PROD_ENV_FILE" "$PROD_BOT_ENV_FILE" "$PROD_BOT_NOTIFY_ENV_FILE" "$STACK_FILE"; do
  if [[ ! -f "$file" ]]; then
    echo "Required file is missing: $file" >&2
    exit 2
  fi
done

set -a
# Production dotenv files are intentionally shell-compatible KEY=value files.
# shellcheck disable=SC1090
source "$PROD_ENV_FILE"
set +a

required_prod_vars=(DJANGO_SECRET_KEY POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD INTERNAL_TOKEN ORDER_APPROVE_SECRET METRICS_TOKEN TELEGRAM_BOT_TOKEN ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS GRAFANA_ADMIN_PASSWORD)
for name in "${required_prod_vars[@]}"; do
  value="${!name:-}"
  if [[ -z "$value" || "$value" == replace-* || "$value" == "change-me" || "$value" == "dev" || "$value" == "dev-secret" || "$value" == "change-me-before-production" ]]; then
    echo "Unsafe or missing production variable: $name" >&2
    exit 2
  fi
done

mkdir -p "$DEPLOY_DIR" "$LETSENCRYPT_DIR" "$LETSENCRYPT_LIB_DIR" "$CERTBOT_WWW_DIR"

old_sha=""
if [[ -f "$DEPLOY_DIR/current-sha" ]]; then
  old_sha="$(tr -d '[:space:]' < "$DEPLOY_DIR/current-sha")"
fi

if [[ "$SKIP_MIGRATIONS" != "1" ]]; then
  migration_base="${MIGRATION_BASE_REF:-}"
  if [[ -z "$migration_base" ]]; then
    if [[ -n "$old_sha" ]] && git rev-parse --verify "$old_sha" >/dev/null 2>&1; then
      migration_base="$old_sha"
    else
      migration_base="origin/dev"
    fi
  fi
  BASE_REF="$migration_base" ALLOW_RISKY_MIGRATIONS="$ALLOW_RISKY_MIGRATIONS" "$ROOT_DIR/scripts/check_migration_safety.sh"
fi

cert_path="$LETSENCRYPT_DIR/live/$LETSENCRYPT_DOMAIN/fullchain.pem"
cert_domains=("$LETSENCRYPT_DOMAIN")
if getent ahosts "$LETSENCRYPT_WWW_DOMAIN" >/dev/null 2>&1; then
  cert_domains+=("$LETSENCRYPT_WWW_DOMAIN")
fi
cert_args=()
for domain in "${cert_domains[@]}"; do
  cert_args+=("-d" "$domain")
done

if [[ ! -f "$cert_path" ]]; then
  if [[ -z "$LETSENCRYPT_EMAIL" ]]; then
    echo "LETSENCRYPT_EMAIL is required for first certificate issuance" >&2
    exit 2
  fi
  log "Issuing TLS certificate for ${cert_domains[*]}"
  if docker service inspect "${STACK_NAME}_nginx" >/dev/null 2>&1; then
    docker service scale "${STACK_NAME}_nginx=0" >/dev/null
  fi
  docker run --rm \
    -p 80:80 \
    -v "$LETSENCRYPT_DIR:/etc/letsencrypt" \
    -v "$LETSENCRYPT_LIB_DIR:/var/lib/letsencrypt" \
    certbot/certbot:latest certonly \
      --standalone --non-interactive --agree-tos \
      --email "$LETSENCRYPT_EMAIL" \
      "${cert_args[@]}"
else
  docker run --rm \
    -v "$LETSENCRYPT_DIR:/etc/letsencrypt" \
    -v "$LETSENCRYPT_LIB_DIR:/var/lib/letsencrypt" \
    -v "$CERTBOT_WWW_DIR:/var/www/certbot" \
    certbot/certbot:latest renew --webroot -w /var/www/certbot --quiet || true
fi

export IMAGE_TAG IMAGE_PREFIX PROD_ENV_FILE PROD_BOT_ENV_FILE PROD_BOT_NOTIFY_ENV_FILE LETSENCRYPT_DIR CERTBOT_WWW_DIR
export SWARM_NGINX_CONF="${SWARM_NGINX_CONF:-$ROOT_DIR/deploy/swarm/nginx.conf}"

log "Validating rendered stack"
docker stack config -c "$STACK_FILE" >/dev/null

log "Deploying infrastructure/release phase with application replicas paused"
BACKEND_REPLICAS=0 \
FRONTEND_REPLICAS=0 \
CELERY_WORKER_REPLICAS=0 \
CELERY_BEAT_REPLICAS=0 \
BOT_REPLICAS=0 \
BOT_NOTIFY_REPLICAS=0 \
docker stack deploy --with-registry-auth --prune -c "$STACK_FILE" "$STACK_NAME"

wait_healthy_container() {
  local service="$1"
  local timeout="${2:-180}"
  local start now container status
  start="$(date +%s)"
  while true; do
    container="$(docker ps --filter "label=com.docker.swarm.service.name=${STACK_NAME}_${service}" --format '{{.ID}}' | head -n1)"
    if [[ -n "$container" ]]; then
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"
      if [[ "$status" == "healthy" || "$status" == "running" ]]; then
        return 0
      fi
      if [[ "$status" == "unhealthy" || "$status" == "dead" ]]; then
        docker logs --tail 120 "$container" >&2 || true
        return 1
      fi
    fi
    now="$(date +%s)"
    if (( now - start >= timeout )); then
      echo "Timed out waiting for ${STACK_NAME}_${service}" >&2
      docker service ps "${STACK_NAME}_${service}" --no-trunc >&2 || true
      return 1
    fi
    sleep 3
  done
}

log "Waiting for stateful dependencies"
wait_healthy_container db 180
wait_healthy_container redis 120
wait_healthy_container opensearch 240

release_image="${IMAGE_PREFIX}-backend:${IMAGE_TAG}"
release_network="${STACK_NAME}_backend"
release_common=(
  --rm
  --network "$release_network"
  --env-file "$PROD_ENV_FILE"
  -e DJANGO_SETTINGS_MODULE=config.settings.prod
  -e DEBUG=0
  -e POSTGRES_HOST=db
  -e REDIS_URL=redis://redis:6379/0
  -e CACHE_URL=redis://redis:6379/1
  -e OPENSEARCH_URL=http://opensearch:9200
  -v servio_staticfiles:/app/staticfiles
)

if [[ "$SKIP_MIGRATIONS" != "1" ]]; then
  log "Rendering Django migration plan"
  docker run "${release_common[@]}" "$release_image" /app/.venv/bin/python manage.py migrate --plan
  log "Applying Django migrations as release phase"
  docker run "${release_common[@]}" "$release_image" /app/.venv/bin/python manage.py migrate --noinput
else
  log "Skipping migrations for code-only rollback"
fi

log "Collecting static files as release phase"
docker run "${release_common[@]}" "$release_image" /app/.venv/bin/python manage.py collectstatic --noinput --verbosity 0

log "Rolling out application services"
export BACKEND_REPLICAS="$DESIRED_BACKEND_REPLICAS"
export FRONTEND_REPLICAS="$DESIRED_FRONTEND_REPLICAS"
export CELERY_WORKER_REPLICAS="$DESIRED_CELERY_WORKER_REPLICAS"
export CELERY_BEAT_REPLICAS="$DESIRED_CELERY_BEAT_REPLICAS"
export BOT_REPLICAS="$DESIRED_BOT_REPLICAS"
export BOT_NOTIFY_REPLICAS="$DESIRED_BOT_NOTIFY_REPLICAS"
docker stack deploy --with-registry-auth --prune -c "$STACK_FILE" "$STACK_NAME"

STACK_NAME="$STACK_NAME" HEALTH_URL="https://${LETSENCRYPT_DOMAIN}/health/" "$ROOT_DIR/scripts/swarm_healthcheck.sh"

if [[ -n "$old_sha" && "$old_sha" != "$IMAGE_TAG" ]]; then
  printf '%s\n' "$old_sha" > "$DEPLOY_DIR/previous-sha"
fi
printf '%s\n' "$IMAGE_TAG" > "$DEPLOY_DIR/current-sha"
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DEPLOY_DIR/deployed-at"

trap - ERR
log "Deployment complete: $IMAGE_TAG"
