# Servio

B2B marketplace monorepo on Django + HTMX with OpenSearch, Celery, Telegram bot integrations, and an observability stack.

This README is the repository entrypoint. For current architecture and operational guidance, start with the source-of-truth docs listed below.


## Start Here

- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) — current system architecture
- [docs/BACKEND_GUIDE.md](./docs/BACKEND_GUIDE.md) — backend layering and placement rules
- [docs/FRONTEND_ARCHITECTURE.md](./docs/FRONTEND_ARCHITECTURE.md) — storefront frontend/runtime model
- [docs/LOCAL_DEVELOPMENT.md](./docs/LOCAL_DEVELOPMENT.md) — local dev workflow
- [docs/DOCKER_GUIDE.md](./docs/DOCKER_GUIDE.md) — Docker stacks and compose layers
- [docs/OPERATIONS_RUNBOOK_RU.md](./docs/OPERATIONS_RUNBOOK_RU.md) — deploy, rollback, backup, restore
- [docs/FULL_PROJECT_AUDIT_RU_2026-03-20.md](./docs/FULL_PROJECT_AUDIT_RU_2026-03-20.md) — latest full audit and remediation status

## Repository Structure

backend/ — Django backend, Celery, API
bot/ — Telegram bot
deploy/ — configs for monitoring, nginx, etc.

## Environment Variables
- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD
- DJANGO_SECRET_KEY
- TELEGRAM_BOT_TOKEN
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET

## Quick Start (Dev)

```bash
cp backend/.env.example backend/.env
cp bot/.env.example bot/.env
cp bot/.env.notify.example bot/.env.notify
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
# new terminal:
make migrate
make superuser
```

Open:
- Web (Nginx proxy): http://localhost:8080/
- Admin: http://localhost:8080/admin/
- API docs (Swagger): http://localhost:8080/api/docs/
- API docs (Redoc): http://localhost:8080/api/redoc/
- API schema: http://localhost:8080/api/schema/
- Metrics endpoint on nginx: http://localhost:8080/metrics

If you start the metrics overlay too:

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000  (admin / admin)
- Alertmanager: http://localhost:9093
- GlitchTip: http://localhost:18000

Detailed reference:

- [backend/API.md](./backend/API.md)
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- [docs/BACKEND_GUIDE.md](./docs/BACKEND_GUIDE.md)
- [docs/FRONTEND_ARCHITECTURE.md](./docs/FRONTEND_ARCHITECTURE.md)
- [docs/LOCAL_DEVELOPMENT.md](./docs/LOCAL_DEVELOPMENT.md)
- [docs/DOCKER_GUIDE.md](./docs/DOCKER_GUIDE.md)
- [docs/OPERATIONS_RUNBOOK_RU.md](./docs/OPERATIONS_RUNBOOK_RU.md)
- [CONTRIBUTING.md](./CONTRIBUTING.md)

Search:
- OpenSearch runs locally as `opensearch:9200` inside compose
- Reindex products after first boot:

```bash
docker compose exec backend python manage.py reindex_products_search
```

## Self-Hosted Error Tracking

Local self-hosted Sentry-compatible tracking is available via GlitchTip.

Start it:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml up -d glitchtip
```

Open:
- GlitchTip: http://localhost:18000

Then set `SENTRY_DSN` in `backend/.env`, `bot/.env`, or other service env files to the DSN of your GlitchTip project.

## Tests

Backend tests and lint now run in a dedicated dockerized service with dev dependencies and access to the compose network.

Full suite with the repo coverage gate:

```bash
make test
```

Targeted run without the global `pytest.ini` coverage threshold:

```bash
make test-fast TEST_ARGS="tests/test_shopfront_views.py -k catalog_filter"
```

Lint in the same dev image:

```bash
make lint
```

## Workflow: Dev -> Prod

1. Вся разработка идет в ветке `dev`.
2. В `dev` запускается GitHub CI (tests/lint).
3. В `main` попадаем только через PR из `dev`.
4. `main` автоматически деплоится в production через `.github/workflows/deploy.yml`.

Рекомендуется включить branch protection:
- для `main`: required checks = `CI`, запрет прямого push;
- для `dev`: required checks = `CI` (по желанию команды).
- PR template: `.github/PULL_REQUEST_TEMPLATE.md`
- Release checklist: `.github/RELEASE_CHECKLIST.md`

## Google OAuth (real login)

1. Create OAuth 2.0 Client ID in Google Cloud Console.
2. Add Authorized redirect URIs:
   - `http://localhost:8080/account/social/google/login/callback/`
   - `http://localhost:8000/account/social/google/login/callback/`
3. Put credentials into `backend/.env`:
   - `GOOGLE_CLIENT_ID=...`
   - `GOOGLE_CLIENT_SECRET=...`
4. Rebuild/restart backend:
```bash
docker compose build backend
docker compose up -d backend nginx
```

## Production (example)
```bash
# set strong secrets in .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Codespaces
Open repo in Codespaces, then the same commands as above.
