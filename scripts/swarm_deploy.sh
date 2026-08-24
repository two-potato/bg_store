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
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"
DEPLOY_DIR="${DEPLOY_DIR:-$ROOT_DIR/.deploy}"
STACK_FILE="${STACK_FILE:-$ROOT_DIR/deploy/swarm/stack.yml}"

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

mkdir -p "$DEPLOY_DIR" "$LETSENCRYPT_DIR" "$LETSENCRYPT_LIB_DIR" "$CERTBOT_WWW_DIR"

cert_path="$LETSENCRYPT_DIR/live/$LETSENCRYPT_DOMAIN/fullchain.pem"
if [[ ! -f "$cert_path" ]]; then
  if [[ -z "$LETSENCRYPT_EMAIL" ]]; then
    echo "LETSENCRYPT_EMAIL is required for first certificate issuance" >&2
    exit 2
  fi
  echo "Issuing first TLS certificate for $LETSENCRYPT_DOMAIN"
  docker run --rm \
    -p 80:80 \
    -v "$LETSENCRYPT_DIR:/etc/letsencrypt" \
    -v "$LETSENCRYPT_LIB_DIR:/var/lib/letsencrypt" \
    certbot/certbot:latest certonly \
      --standalone --non-interactive --agree-tos \
      --email "$LETSENCRYPT_EMAIL" \
      -d "$LETSENCRYPT_DOMAIN"
else
  docker run --rm \
    -v "$LETSENCRYPT_DIR:/etc/letsencrypt" \
    -v "$LETSENCRYPT_LIB_DIR:/var/lib/letsencrypt" \
    -v "$CERTBOT_WWW_DIR:/var/www/certbot" \
    certbot/certbot:latest renew --webroot -w /var/www/certbot --quiet || true
fi

export IMAGE_TAG IMAGE_PREFIX PROD_ENV_FILE PROD_BOT_ENV_FILE PROD_BOT_NOTIFY_ENV_FILE LETSENCRYPT_DIR CERTBOT_WWW_DIR
export SWARM_NGINX_CONF="${SWARM_NGINX_CONF:-$ROOT_DIR/deploy/swarm/nginx.conf}"

old_sha=""
if [[ -f "$DEPLOY_DIR/current-sha" ]]; then
  old_sha="$(tr -d '[:space:]' < "$DEPLOY_DIR/current-sha")"
fi

echo "Deploying $IMAGE_TAG to stack $STACK_NAME"
docker stack config -c "$STACK_FILE" >/dev/null
docker stack deploy --with-registry-auth --prune -c "$STACK_FILE" "$STACK_NAME"

backend_container=""
for _ in $(seq 1 60); do
  backend_container="$(docker ps --filter "label=com.docker.swarm.service.name=${STACK_NAME}_backend" --format '{{.ID}}' | head -n1)"
  [[ -n "$backend_container" ]] && break
  sleep 2
done
if [[ -z "$backend_container" ]]; then
  echo "Backend task did not start on manager" >&2
  docker stack ps "$STACK_NAME" --no-trunc >&2 || true
  exit 1
fi

echo "Collecting static files"
docker exec "$backend_container" /app/.venv/bin/python manage.py collectstatic --noinput --verbosity 0

STACK_NAME="$STACK_NAME" HEALTH_URL="https://${LETSENCRYPT_DOMAIN}/health/" "$ROOT_DIR/scripts/swarm_healthcheck.sh"

if [[ -n "$old_sha" && "$old_sha" != "$IMAGE_TAG" ]]; then
  printf '%s\n' "$old_sha" > "$DEPLOY_DIR/previous-sha"
fi
printf '%s\n' "$IMAGE_TAG" > "$DEPLOY_DIR/current-sha"
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DEPLOY_DIR/deployed-at"

echo "Deployment complete: $IMAGE_TAG"
