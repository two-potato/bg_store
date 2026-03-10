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

log_step() {
  printf '[deploy][%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

dump_compose_diagnostics() {
  log_step "Compose service status"
  $COMPOSE ps || true
  log_step "Recent backend logs"
  $COMPOSE logs --tail=120 backend || true
  log_step "Recent nginx logs"
  $COMPOSE logs --tail=120 nginx || true
  log_step "Recent db logs"
  $COMPOSE logs --tail=80 db || true
}

on_deploy_error() {
  local exit_code=$?
  log_step "Deployment failed with exit code ${exit_code}"
  dump_compose_diagnostics
  exit "$exit_code"
}

trap on_deploy_error ERR

mkdir -p "$ROOT_DIR/deploy/letsencrypt" "$ROOT_DIR/deploy/letsencrypt-lib" "$ROOT_DIR/deploy/certbot-www"

compose_exec_backend() {
  $COMPOSE exec -T backend "$@"
}

run_with_timeout() {
  local timeout_seconds="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout --foreground "$timeout_seconds" "$@"
  else
    "$@"
  fi
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
          log_step "Service '$service' is $status"
          return 0
          ;;
        unhealthy|exited|dead)
          log_step "Service '$service' is $status"
          docker logs --tail 120 "$container_id" || true
          return 1
          ;;
      esac
    fi

    local now_ts
    now_ts="$(date +%s)"
    if [ $((now_ts - start_ts)) -ge "$timeout" ]; then
      log_step "Timed out waiting for '$service' health after ${timeout}s"
      if [ -n "${container_id:-}" ]; then
        docker logs --tail 120 "$container_id" || true
      fi
      return 1
    fi

    log_step "Waiting for '$service' to become healthy..."
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
      log_step "Creating missing Docker volume: $volume"
      docker volume create "$volume" >/dev/null
    fi
  done
}

configure_firewall() {
  if [ "$DEPLOY_CONFIGURE_FIREWALL" != "1" ]; then
    log_step "Firewall hardening skipped (set DEPLOY_CONFIGURE_FIREWALL=1 to enable)"
    return
  fi

  if ! command -v ufw >/dev/null 2>&1; then
    log_step "ufw not found, skipping firewall hardening"
    return
  fi

  log_step "Applying UFW inbound policy (allow only SSH/HTTP/HTTPS)"
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
      log_step "Skipping LE domain '$d' (DNS record not found yet)"
    fi
  done

  for d in "${domains[@]}"; do
    certbot_domain_args+=("-d" "$d")
  done

  log_step "Requesting/renewing Let's Encrypt certificate for $LETSENCRYPT_DOMAIN"
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
  log_step "TLS certificate not found, performing first-time issuance"
  run_with_timeout 900 $COMPOSE up -d --build --remove-orphans db redis es bot bot-notify backend celery-worker celery-beat
  issue_or_renew_cert_standalone
fi

# Renew certificate only when it expires within 30 days.
if [ -f "$LETSENCRYPT_CERT_PATH" ]; then
  if command -v openssl >/dev/null 2>&1; then
    if ! openssl x509 -checkend 2592000 -noout -in "$LETSENCRYPT_CERT_PATH" >/dev/null; then
      issue_or_renew_cert_standalone
    fi
  else
    log_step "openssl is not installed, skipping expiration check"
  fi
fi

log_step "Pulling/building and starting services"
ensure_named_volumes
run_with_timeout 1200 $COMPOSE up -d --build --remove-orphans

log_step "Waiting for core services"
wait_for_service_health db 120
wait_for_service_health redis 120
wait_for_service_health bot 180
wait_for_service_health bot-notify 180
wait_for_service_health backend 240

log_step "Running migrations"
run_with_timeout 300 compose_exec_backend /app/.venv/bin/python manage.py migrate --noinput

log_step "Restoring sellers/stores links when missing"
if compose_exec_backend /app/.venv/bin/python manage.py help seed_sellers >/dev/null 2>&1; then
  if ! run_with_timeout 300 compose_exec_backend /app/.venv/bin/python manage.py seed_sellers; then
    log_step "WARNING: seed_sellers failed, continuing deploy"
  fi
else
  log_step "seed_sellers command not available, skipping"
fi

log_step "Clearing application cache"
run_with_timeout 120 compose_exec_backend /app/.venv/bin/python manage.py shell -c "from django.core.cache import cache; cache.clear()"

log_step "Fixing staticfiles volume permissions"
run_with_timeout 120 $COMPOSE exec -T --user root backend sh -lc "mkdir -p /app/staticfiles && chown -R app:app /app/staticfiles"

log_step "Collecting static files"
run_with_timeout 300 compose_exec_backend /app/.venv/bin/python manage.py collectstatic --noinput --verbosity 0

log_step "Service status"
$COMPOSE ps

log_step "Health checks"
run_with_timeout 60 curl -fsS http://localhost/health/ >/dev/null
log_step "OK"

configure_firewall
