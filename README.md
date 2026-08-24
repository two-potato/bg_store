# Servio

B2B marketplace monorepo on Django + HTMX with OpenSearch, Celery, Telegram bot integrations, and an observability stack.

This README is the repository entrypoint. For current architecture and operational guidance, start with the source-of-truth docs listed below.

## Start Here

- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) — current system architecture
- [docs/BACKEND_GUIDE.md](./docs/BACKEND_GUIDE.md) — backend layering and placement rules
- [docs/FRONTEND_ARCHITECTURE.md](./docs/FRONTEND_ARCHITECTURE.md) — storefront frontend/runtime model
- [docs/LOCAL_DEVELOPMENT.md](./docs/LOCAL_DEVELOPMENT.md) — local dev workflow
- [docs/DOCKER_GUIDE.md](./docs/DOCKER_GUIDE.md) — local Docker/Compose guidance
- [docs/OPERATIONS_RUNBOOK_RU.md](./docs/OPERATIONS_RUNBOOK_RU.md) — production deploy, rollback, backup, restore
- [deploy/swarm/README.md](./deploy/swarm/README.md) — two-node production Swarm bootstrap
- [docs/PRODUCTION_READINESS.md](./docs/PRODUCTION_READINESS.md) — production release gates

## Repository Structure

- `backend/` — Django backend, Celery, API
- `frontend/` — Next.js storefront foundation
- `bot/` — Telegram bot services
- `services/` — optional search/recommendation services
- `deploy/` — reverse proxy, monitoring and Swarm production configuration
- `scripts/` — operational and CI helper scripts

## Environment Variables

Core variables include:
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DJANGO_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

See `backend/.env.example` for local development and `backend/.env.prod.example` for production.

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

If you start the local metrics overlay too:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Alertmanager: http://localhost:9093
- GlitchTip: http://localhost:18000

## Search

OpenSearch runs locally as `opensearch:9200` inside Compose. Reindex products after first boot:

```bash
docker compose exec backend python manage.py reindex_products_search
```

## Self-Hosted Error Tracking (local)

Local Sentry-compatible tracking is available via GlitchTip:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml up -d glitchtip
```

Then configure `SENTRY_DSN` in the relevant local env files.

## Tests

Full backend suite with repository coverage gate:

```bash
make test
```

Targeted run without the global coverage threshold:

```bash
make test-fast TEST_ARGS="tests/test_shopfront_views.py -k catalog_filter"
```

Lint:

```bash
make lint
```

## Branch and Release Workflow

1. Active development is integrated through `dev`.
2. `CI` and `Security Audit` validate production candidates.
3. The production candidate branch must contain the current `dev` history.
4. Production deployment is explicit: run **Deploy Production Swarm** manually or push an approved `prod-*` tag.
5. Production deploys immutable GHCR images by commit SHA to the two-node Docker Swarm.

Production is **not** deployed automatically on every feature-branch push.

## Production

Production for `24sparts.ru` uses Docker Swarm, not the local Compose overlay.

Start here:

```text
deploy/swarm/README.md
docs/OPERATIONS_RUNBOOK_RU.md
docs/PRODUCTION_READINESS.md
```

The production topology is one manager/core node and one worker node; application images are built by GitHub Actions and deployed by exact commit SHA.

## Google OAuth (local setup)

1. Create OAuth 2.0 Client ID in Google Cloud Console.
2. Add local Authorized redirect URIs:
   - `http://localhost:8080/account/social/google/login/callback/`
   - `http://localhost:8000/account/social/google/login/callback/`
3. Put credentials into `backend/.env`.
4. Rebuild/restart backend:

```bash
docker compose build backend
docker compose up -d backend nginx
```

## Codespaces

Open the repository in Codespaces and use the local development commands above.
