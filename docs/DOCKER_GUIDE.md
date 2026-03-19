# Docker Guide

## Purpose

This document is the source of truth for local Docker workflows in Servio.

Use it together with:

- `docker-compose.yml` for the base stack
- `docker-compose.dev.yml` for local development overrides
- `docker-compose.prod.yml` for production overrides
- `docker-compose.metrics.yml` for the observability stack, including GlitchTip
- `docker-compose.glitchtip.yml` for standalone local Sentry-compatible tracking when you do not need the full metrics overlay

## Environment Files

Docker Compose is configured in a safe order:

1. tracked `*.env.example` files provide defaults
2. untracked local `*.env` files override them when present

Current patterns:

- `backend/.env.example` + optional `backend/.env`
- `backend/.env.prod.example` + optional `backend/.env.prod`
- `bot/.env.example` + optional `bot/.env`
- `bot/.env.notify.example` + optional `bot/.env.notify`
- `deploy/glitchtip/.env.example` + optional `deploy/glitchtip/.env`

Rules:

- never commit real secrets to `*.env`
- if you need local credentials, copy from the matching `*.env.example`
- do not paste `docker compose config` output into tickets or chat because it expands env values

### Production Env Workflow

For production-like runs and predeploy checks, use `backend/.env.prod`, not the general local `backend/.env`.

Recommended bootstrap:

```bash
cp backend/.env.prod.example backend/.env.prod
```

Then fill the required values:

- `DJANGO_SECRET_KEY`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `INTERNAL_TOKEN`
- `ORDER_APPROVE_SECRET`
- `METRICS_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`

Current production host values used by the project:

- `ALLOWED_HOSTS=potatofarm.ru,www.potatofarm.ru`
- `CSRF_TRUSTED_ORIGINS=https://potatofarm.ru,https://www.potatofarm.ru`

Notes:

- `METRICS_TOKEN` is a secret and cannot be recovered from git history
- do not keep localhost values in `ALLOWED_HOSTS` or `CSRF_TRUSTED_ORIGINS` for `DEBUG=0`
- `docker-compose.prod.yml` is configured to load `backend/.env.prod.example` and optional `backend/.env.prod`

## Main Stacks

### Dev

```bash
make dev
```

Equivalent command:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### Dev + Metrics

```bash
make dev-metrics
```

Equivalent command:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml up --build
```

This overlay now includes:

- Prometheus
- Grafana
- Alertmanager
- Loki + Promtail
- exporters
- GlitchTip on `http://localhost:18000`

### Prod-like Local Run

```bash
make prod
```

Equivalent command:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Local GlitchTip

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml up -d glitchtip
```

If you want GlitchTip without the rest of the observability stack:

```bash
docker compose -f docker-compose.glitchtip.yml up -d
```

## Common Operations

### Stop Stacks

```bash
make stop
```

### Check Running Containers

```bash
make status
```

### Tail Logs

```bash
make logs
make logs-metrics
```

### Run Tests in Docker

```bash
make test
make test-fast TEST_ARGS="tests/test_shopfront_views.py -q"
make lint
make check-local
```

### Validate Compose Files

```bash
make docker-validate
```

This verifies:

- dev compose resolves
- prod compose resolves
- dev + metrics compose resolves
- glitchtip compose resolves
- deploy script matches the compose stack contract

### Predeploy Checks

Run these before a real rollout:

```bash
make prod-check
```

Equivalent explicit commands:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend /app/.venv/bin/python manage.py check --deploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend /app/.venv/bin/python manage.py migrate --check
```

Expected result:

- compose resolves successfully
- `check --deploy` completes without errors
- `migrate --check` exits cleanly

## Data and Volumes

The base stack uses external named volumes:

- `servio_pgdata`
- `servio_redisdata`
- `servio_opensearchdata`
- `servio_staticfiles`

Do not rename them in override files unless deployment scripts and docs are updated in the same change.

## Recommended Local Bootstrap

Optional local overrides:

```bash
cp backend/.env.example backend/.env
cp bot/.env.example bot/.env
cp bot/.env.notify.example bot/.env.notify
cp deploy/glitchtip/.env.example deploy/glitchtip/.env
```

Then start the stack:

```bash
make dev
```

If you do not create local override files, Compose will still use the tracked example defaults.
