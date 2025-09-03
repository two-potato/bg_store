# Bad Guys Shop — Full Monorepo

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

## Production (example)
```bash
# set strong secrets in .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Codespaces
Open repo in Codespaces, then the same commands as above.
