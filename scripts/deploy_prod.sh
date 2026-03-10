#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.metrics.yml"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-admin@potatofarm.ru}"
LETSENCRYPT_DOMAIN="${LETSENCRYPT_DOMAIN:-potatofarm.ru}"
LETSENCRYPT_DOMAIN_WWW="${LETSENCRYPT_DOMAIN_WWW:-www.potatofarm.ru}"
LETSENCRYPT_EXTRA_DOMAINS="${LETSENCRYPT_EXTRA_DOMAINS:-grafana.potatofarm.ru}"
LETSENCRYPT_CERT_PATH="$ROOT_DIR/deploy/letsencrypt/live/$LETSENCRYPT_DOMAIN/fullchain.pem"
ALLOWED_SSH_PORT_RAW="${ALLOWED_SSH_PORT:-22}"
DEPLOY_CONFIGURE_FIREWALL="${DEPLOY_CONFIGURE_FIREWALL:-0}"
ALLOWED_SSH_PORT="$(printf '%s' "$ALLOWED_SSH_PORT_RAW" | grep -Eo '[0-9]{1,5}' | head -n1 || true)"
if [[ -n "$ALLOWED_SSH_PORT" ]] && [ "$ALLOWED_SSH_PORT" -ge 1 ] && [ "$ALLOWED_SSH_PORT" -le 65535 ]; then
  :
else
  echo "[deploy] Invalid ALLOWED_SSH_PORT='$ALLOWED_SSH_PORT_RAW', fallback to 22"
  ALLOWED_SSH_PORT="22"
fi
export NGINX_HTTP_PORT="${NGINX_HTTP_PORT:-80}"

mkdir -p "$ROOT_DIR/deploy/letsencrypt" "$ROOT_DIR/deploy/letsencrypt-lib" "$ROOT_DIR/deploy/certbot-www"

compose_exec_backend() {
  $COMPOSE exec -T backend "$@"
}

wait_for_service_health() {
  local service="$1"
  local timeout="${2:-180}"
  local start_ts
  start_ts="$(date +%s)"

  while true; do
    local container_id
    container_id="$($COMPOSE ps -q "$service" | head -n1)"
    if [ -n "$container_id" ]; then
      local status
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
      case "$status" in
        healthy|running)
          echo "[deploy] Service '$service' is $status"
          return 0
          ;;
        unhealthy|exited|dead)
          echo "[deploy] Service '$service' is $status"
          docker logs --tail 120 "$container_id" || true
          return 1
          ;;
      esac
    fi

    local now_ts
    now_ts="$(date +%s)"
    if [ $((now_ts - start_ts)) -ge "$timeout" ]; then
      echo "[deploy] Timed out waiting for '$service' health after ${timeout}s"
      if [ -n "${container_id:-}" ]; then
        docker logs --tail 120 "$container_id" || true
      fi
      return 1
    fi

    echo "[deploy] Waiting for '$service' to become healthy..."
    sleep 5
  done
}

ensure_named_volumes() {
  local volumes=(
    "servio_pgdata"
    "servio_esdata"
    "servio_redisdata"
    "servio_staticfiles"
  )
  local volume
  for volume in "${volumes[@]}"; do
    if ! docker volume inspect "$volume" >/dev/null 2>&1; then
      echo "[deploy] Creating missing Docker volume: $volume"
      docker volume create "$volume" >/dev/null
    fi
  done
}

configure_firewall() {
  if [ "$DEPLOY_CONFIGURE_FIREWALL" != "1" ]; then
    echo "[deploy] Firewall hardening skipped (set DEPLOY_CONFIGURE_FIREWALL=1 to enable)"
    return
  fi

  if ! command -v ufw >/dev/null 2>&1; then
    echo "[deploy] ufw not found, skipping firewall hardening"
    return
  fi

  echo "[deploy] Applying UFW inbound policy (allow only SSH/HTTP/HTTPS)"
  ufw --force reset
  ufw default deny incoming
  ufw default allow outgoing
  ufw allow "${ALLOWED_SSH_PORT}/tcp"
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable || true
}

issue_or_renew_cert_standalone() {
  local domains=("$LETSENCRYPT_DOMAIN" "$LETSENCRYPT_DOMAIN_WWW")
  local d
  local certbot_domain_args=()

  IFS=',' read -ra extra_domains <<< "$LETSENCRYPT_EXTRA_DOMAINS"
  for d in "${extra_domains[@]}"; do
    d="$(echo "$d" | xargs)"
    [ -z "$d" ] && continue
    if getent hosts "$d" >/dev/null 2>&1; then
      domains+=("$d")
    else
      echo "[deploy] Skipping LE domain '$d' (DNS record not found yet)"
    fi
  done

  for d in "${domains[@]}"; do
    certbot_domain_args+=("-d" "$d")
  done

  echo "[deploy] Requesting/renewing Let's Encrypt certificate for $LETSENCRYPT_DOMAIN"
  $COMPOSE stop nginx || true
  docker run --rm \
    -p 80:80 -p 443:443 \
    -v "$ROOT_DIR/deploy/letsencrypt:/etc/letsencrypt" \
    -v "$ROOT_DIR/deploy/letsencrypt-lib:/var/lib/letsencrypt" \
    certbot/certbot:latest certonly \
      --standalone \
      --non-interactive \
      --agree-tos \
      --email "$LETSENCRYPT_EMAIL" \
      --keep-until-expiring \
      "${certbot_domain_args[@]}"
}

if [ ! -f "$LETSENCRYPT_CERT_PATH" ]; then
  echo "[deploy] TLS certificate not found, performing first-time issuance"
  $COMPOSE up -d --build --remove-orphans db redis es bot bot-notify backend celery-worker celery-beat
  issue_or_renew_cert_standalone
fi

# Renew certificate only when it expires within 30 days.
if [ -f "$LETSENCRYPT_CERT_PATH" ]; then
  if command -v openssl >/dev/null 2>&1; then
    if ! openssl x509 -checkend 2592000 -noout -in "$LETSENCRYPT_CERT_PATH" >/dev/null; then
      issue_or_renew_cert_standalone
    fi
  else
    echo "[deploy] openssl is not installed, skipping expiration check"
  fi
fi

echo "[deploy] Pulling/building and starting services"
ensure_named_volumes
$COMPOSE up -d --build --remove-orphans

echo "[deploy] Waiting for core services"
wait_for_service_health db 120
wait_for_service_health redis 120
wait_for_service_health bot 180
wait_for_service_health bot-notify 180
wait_for_service_health backend 240

echo "[deploy] Running migrations"
compose_exec_backend /app/.venv/bin/python manage.py migrate --noinput

echo "[deploy] Restoring sellers/stores links when missing"
if compose_exec_backend /app/.venv/bin/python manage.py help seed_sellers >/dev/null 2>&1; then
  if ! compose_exec_backend /app/.venv/bin/python manage.py seed_sellers; then
    echo "[deploy] WARNING: seed_sellers failed, continuing deploy"
  fi
else
  echo "[deploy] seed_sellers command not available, skipping"
fi

echo "[deploy] Clearing application cache"
compose_exec_backend /app/.venv/bin/python manage.py shell -c "from django.core.cache import cache; cache.clear()"

echo "[deploy] Fixing staticfiles volume permissions"
$COMPOSE exec -T --user root backend sh -lc "mkdir -p /app/staticfiles && chown -R app:app /app/staticfiles"

echo "[deploy] Collecting static files"
compose_exec_backend /app/.venv/bin/python manage.py collectstatic --noinput --verbosity 0

echo "[deploy] Service status"
$COMPOSE ps

echo "[deploy] Health checks"
curl -fsS http://localhost/health/ >/dev/null
echo "[deploy] OK"

configure_firewall
