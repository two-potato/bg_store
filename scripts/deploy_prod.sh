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

mkdir -p "$ROOT_DIR/deploy/letsencrypt" "$ROOT_DIR/deploy/letsencrypt-lib" "$ROOT_DIR/deploy/certbot-www"

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
$COMPOSE up -d --build --remove-orphans

echo "[deploy] Running migrations"
$COMPOSE exec -T backend /app/.venv/bin/python manage.py migrate --noinput

echo "[deploy] Fixing staticfiles volume permissions"
$COMPOSE exec -T --user root backend sh -lc "mkdir -p /app/staticfiles && chown -R app:app /app/staticfiles"

echo "[deploy] Collecting static files"
$COMPOSE exec -T backend /app/.venv/bin/python manage.py collectstatic --noinput

echo "[deploy] Service status"
$COMPOSE ps

echo "[deploy] Health checks"
curl -fsS http://localhost/health/ >/dev/null
echo "[deploy] OK"
