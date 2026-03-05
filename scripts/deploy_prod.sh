#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "[deploy] Pulling/building and starting services"
$COMPOSE up -d --build --remove-orphans

echo "[deploy] Running migrations"
$COMPOSE exec -T backend /app/.venv/bin/python manage.py migrate --noinput

echo "[deploy] Collecting static files"
$COMPOSE exec -T backend /app/.venv/bin/python manage.py collectstatic --noinput

echo "[deploy] Service status"
$COMPOSE ps

echo "[deploy] Health checks"
curl -fsS http://localhost:8080/health/ >/dev/null
echo "[deploy] OK"

