# Local Development

## Quick Start

```bash
cp backend/.env.example backend/.env
cp bot/.env.example bot/.env
cp bot/.env.notify.example bot/.env.notify
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
make migrate
make superuser
```

## Main URLs

- Web: `http://localhost:8080/`
- Admin: `http://localhost:8080/admin/`
- Swagger: `http://localhost:8080/api/docs/`
- Redoc: `http://localhost:8080/api/redoc/`
- Schema: `http://localhost:8080/api/schema/`

## Daily Commands

```bash
make test
make test-fast TEST_ARGS="tests/test_shopfront_views.py -k catalog_filter"
make lint
```

## Optional ML Environment

```bash
cd backend
uv sync --extra ml
```

Use this extra only for recommendation model training and experiments.

## Backup and Restore (Local Drill)

```bash
scripts/backup_postgres.sh
RESTORE_CONFIRM=1 scripts/restore_postgres_backup.sh backups/postgres/<dump>.sql.gz
scripts/check_backup_freshness.sh
```

## Search

OpenSearch runs in compose as `opensearch:9200`.

```bash
docker compose exec backend python manage.py reindex_products_search
```

## Metrics Overlay

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml up -d
```

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Alertmanager: `http://localhost:9093`
- GlitchTip: `http://localhost:18000`
