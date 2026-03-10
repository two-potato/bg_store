# Servio — Full Monorepo

**Everything merged**: base + patches (auth via Telegram WebApp, legal entities workflow, orders w/ FSM, Celery tasks, bot notifier,
PDF invoices, catalog, admin panel, and mobile-first frontend on HTMX + Bootstrap 5). Uses **uv** for Python.


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
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
# new terminal:
make migrate
make superuser
```

Open:
- Web (Nginx proxy): http://localhost/
- Admin: http://localhost/admin/
- API docs (Swagger): http://localhost/api/docs/
- Metrics: http://localhost/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000  (admin / admin)

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
