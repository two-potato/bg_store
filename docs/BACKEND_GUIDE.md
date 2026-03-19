# Backend Guide

## Goal

This document is the shortest reliable mental model for changing backend code in this repository.

## Key Entry Points

### API

- URL config: `backend/config/urls.py`
- API docs: `/api/schema/`, `/api/docs/`, `/api/redoc/`
- main API domains:
  - `backend/catalog/`
  - `backend/commerce/`
  - `backend/orders/`
  - `backend/users/`
- package entrypoints that now matter:
  - `backend/catalog/models/`
  - `backend/commerce/models/`
  - `backend/commerce/views/`
  - `backend/orders/models/`
  - `backend/users/views/`

### Storefront

- shared storefront helpers: `backend/shopfront/views/`
- storefront page/view modules:
  - `backend/shopfront/page_views.py`
  - `backend/shopfront/catalog_views.py`
  - `backend/shopfront/product_views.py`
  - `backend/shopfront/discovery_views.py`
  - `backend/shopfront/checkout_views.py`
- search services:
  - `backend/shopfront/search.py`
  - `backend/shopfront/search_service.py`
  - `backend/shopfront/live_search_service.py`
- recommendation helpers: `backend/shopfront/recommendations.py`

### Catalog Domain

- catalog models package: `backend/catalog/models/`
- most frequently touched modules:
  - `backend/catalog/models/taxonomy.py`
  - `backend/catalog/models/product.py`
  - `backend/catalog/models/merchandising.py`
  - `backend/catalog/models/marketplace.py`
  - `backend/catalog/models/reviews.py`

### Orders Domain

- order models package: `backend/orders/models/`
- most frequently touched modules:
  - `backend/orders/models/base.py`
  - `backend/orders/models/fulfillment.py`
  - `backend/orders/models/payment.py`
  - `backend/orders/models/support.py`
  - `backend/orders/services.py`

### Shared Infrastructure

- logging and request context: `backend/core/logging_utils.py`
- middleware: `backend/core/middleware.py`
- notifications: `backend/core/notifications.py`
- shared models: `backend/core/models.py`

## Coding Conventions Used Here

- business behavior is often extracted into service modules even when consumed by views only
- query-heavy code prefers dedicated selectors/services over bloated templates
- search and recommendation logic intentionally use pragmatic heuristics, not heavyweight ML services
- API contracts are described with `drf-spectacular` annotations and serializer metadata

## Search Workflow

If you change catalog search behavior:

1. inspect `shopfront/search_service.py`
2. inspect `shopfront/search.py`
3. reindex:

```bash
docker compose exec backend python manage.py reindex_products_search
```

4. verify:

```bash
curl http://localhost:8080/api/schema/
curl http://localhost:8080/
```

## API Documentation Workflow

When adding or changing an endpoint:

1. annotate the view with `extend_schema` or `extend_schema_view`
2. document request and response serializers
3. add examples and meaningful `help_text`
4. verify live schema locally

Useful command:

```bash
docker compose exec backend /app/.venv/bin/python manage.py spectacular --file /tmp/schema.yaml --validate
```

## Common Pitfalls

- local compose bind-mounts `backend/` into `backend`, `backend-test`, `celery-worker`, and `celery-beat`
- OpenSearch changes are invisible until the index is rebuilt
- some flows depend on `INTERNAL_TOKEN`, Telegram env vars, or DaData env vars
- use compose-backed commands for schema and tests so they run against the live tree and the `db` hostname

## Recommended Change Strategy

For most backend changes:

1. inspect the owning domain and any service modules it calls
2. update code and docstrings together
3. update OpenAPI docs if the contract changes
4. verify the live endpoint or live schema
5. run the smallest relevant test slice

Useful local verification:

```bash
docker compose run --rm --no-deps backend-test /app/.venv/bin/python manage.py check
docker compose run --rm --no-deps backend-test /app/.venv/bin/pytest --no-cov tests/test_api_docs.py -q
```
