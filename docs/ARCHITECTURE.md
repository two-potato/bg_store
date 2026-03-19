# Architecture

## Overview

Servio is a monorepo with three main runtime surfaces:

- `backend/`: Django application, REST API, shopfront pages, Celery, admin, integrations.
- `bot/`: Telegram bot and internal notification HTTP service.
- `deploy/`: operational configs such as nginx, Prometheus, Grafana, and related infra.

At runtime the local stack is typically:

- `nginx` terminates HTTP and forwards requests to Django.
- `backend` serves the HTML storefront, DRF API, admin, and background task entrypoints.
- `db` stores transactional data.
- `redis` is used for caching, Celery broker, and ephemeral coordination.
- `opensearch` serves catalog search and live-search autocomplete.
- `bot` delivers Telegram notifications and WebApp-related interactions.

## Backend Domains

### `catalog`

Catalog stores brands, categories, products, collections, tags, and seller offers. It is the source of truth for:

- storefront product listings
- catalog API
- search indexing
- merchandising collections and promo flags

### `commerce`

Commerce covers company-side entities:

- legal entities
- delivery addresses
- memberships and membership requests
- company approval and moderation flows

This domain powers B2B checkout and access control around company-owned data.

### `orders`

Orders model checkout and downstream fulfillment state:

- order creation via API and shopfront
- FSM-based status transitions
- seller splits and seller orders
- shipment metadata
- internal approve/reject flows

### `shopfront`

Shopfront contains the HTML storefront and supporting application services:

- page views and HTMX endpoints
- search orchestration
- recommendations
- checkout helpers
- review flows

It is intentionally service-heavy because a lot of behavior is UI-facing but still business-critical.

### `users`

Users manages auth-adjacent behavior:

- Django user model and profile
- Telegram WebApp auth bridge
- role metadata

### `core`

Core contains cross-cutting infrastructure:

- logging
- middleware
- PDF rendering
- notifications
- shared base models

## Search Architecture

Search has two layers:

1. `shopfront/search.py`
   This is the low-level OpenSearch client. It builds payloads, executes HTTP calls, normalizes responses, and caches live-search bundles.

2. `shopfront/search_service.py`
   This is the orchestration layer. It selects providers, rewrites queries, collects fallback candidates from the database, and reranks merged results.

This split is deliberate:

- infra-specific behavior stays isolated
- views do not know about OpenSearch internals
- fallback behavior remains testable

## Request Flow

For a typical storefront request:

1. `nginx` routes the request to Django.
2. middleware attaches request context and request id.
3. a Django view or DRF viewset handles the request.
4. domain services are called as needed.
5. optional integrations are triggered:
   - OpenSearch for search
   - bot service for Telegram notifications
   - Celery for background work

## Operational Notes

- API schema is generated with `drf-spectacular`.
- Swagger UI is available at `/api/docs/`.
- Redoc is available at `/api/redoc/`.
- Product search requires a populated OpenSearch index.
- Docker images do not bind-mount the whole backend source into the runtime container, so code changes often require rebuild or explicit file sync.
