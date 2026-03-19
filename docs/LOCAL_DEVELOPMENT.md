# Local Development

Docker-specific guidance lives in [`docs/DOCKER_GUIDE.md`](./DOCKER_GUIDE.md). This file keeps the day-to-day dev workflow concise.

## Bootstrap

```bash
cp backend/.env.example backend/.env
cp bot/.env.example bot/.env
cp bot/.env.notify.example bot/.env.notify
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

In a second terminal:

```bash
make migrate
make superuser
```

## Main Local URLs

- storefront via nginx: `http://localhost:8080/`
- admin: `http://localhost:8080/admin/`
- Swagger: `http://localhost:8080/api/docs/`
- Redoc: `http://localhost:8080/api/redoc/`
- OpenAPI schema: `http://localhost:8080/api/schema/`
- healthcheck: `http://localhost:8080/health/`

## Useful Commands

Validate the Docker stack contract before bigger changes:

```bash
make docker-validate
```

Run backend tests:

```bash
make test
```

The canonical test path is the compose-backed `backend-test` service. It shares the working tree through a bind mount and uses the same `db`, `redis`, and `opensearch` hostnames as the runtime services:

```bash
docker compose run --rm --no-deps backend-test /app/.venv/bin/pytest --no-cov tests/test_api_docs.py -q
```

Run Django checks inside the same runtime:

```bash
docker compose run --rm --no-deps backend-test /app/.venv/bin/python manage.py check
make check-local
```

Run the full dev stack with observability:

```bash
make dev-metrics
```

Run a focused test slice:

```bash
make test-fast TEST_ARGS="tests/test_api_docs.py -q"
```

Lint:

```bash
make lint
```

Reindex OpenSearch:

```bash
docker compose exec backend python manage.py reindex_products_search
```

## When Code Changes Do Not Show Up

Backend dev services are bind-mounted from `./backend`, so ordinary Python/template changes should appear without image rebuilds. Rebuild is still needed when Python dependencies or the Docker image itself change:

```bash
docker compose build backend
docker compose up -d --force-recreate backend
```

## Search Verification

After changing search behavior:

1. rebuild or restart backend
2. rebuild OpenSearch index
3. check a live query in the storefront
4. inspect `/api/schema/` if API search behavior changed

## Docs Verification

Use these URLs after changing API docs:

- `/api/schema/`
- `/api/docs/`
- `/api/redoc/`

If the code looks updated but the docs are stale, the backend container is usually stale too.
