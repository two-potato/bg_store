# Servio Architecture

## System Shape

Servio is a modular monolith built on Django with sidecar services:

- `backend/`: Django apps, Celery tasks, API, storefront HTML
- `bot/`: FastAPI + aiogram notification and Telegram flows
- `services/search-api/`: FastAPI search contract service (platform extraction, stage 1)
- `services/recommendation-api/`: FastAPI recommendation contract service (platform extraction, stage 1)
- `deploy/`: Nginx, Prometheus, Loki, Grafana, Alertmanager, GlitchTip

Business source-of-truth stays in Django. New search/recommendation FastAPI services are introduced as additive bridge targets (`django-inline` fallback stays default) to support controlled migration.

## Core Domains

- `core`: shared runtime helpers, middleware, idempotency, notifications
- `users`: account UI, seller cabinet, profile and auth-adjacent flows
- `commerce`: legal entities, addresses, company workspace
- `catalog`: taxonomy, products, reviews, documents, offers, inventories
- `orders`: order lifecycle, payments, seller splits, claims, support
- `promotions`: discounting and coupon redemption
- `shopfront`: storefront UX, search, recommendations, cart, checkout

## Shopfront Structure

`shopfront` is the most complex domain and should follow these boundaries:

- `shopfront/views/`: thin HTTP adapters only
- `shopfront/searching/`: search backend, fallback strategy, attribution, observability
- `shopfront/recommendation/`: candidate retrieval, ranking, attribution, observability
- `shopfront/*_service.py`: orchestration that can be unit-tested without HTTP
- `shopfront/context_processors.py`: lightweight runtime config and shared page state

Current service boundaries introduced in this cycle:

- `catalog_page_service.py`: catalog filtering, search integration, facets, pagination, SEO context
- `checkout_orchestration_service.py`: checkout submit orchestration and payment bootstrap
- `saved_list_service.py`: saved lists, favorites, subscriptions, saved searches
- `product_detail_service.py` and `store_detail_service.py`: PDP and storefront composition
- `pages_service.py`: brand/category/collection page composition

## Request Flow Examples

### Catalog

1. `CatalogView` parses request into `CatalogRequestParams`
2. `CatalogPageService` applies filters, search provider ranking and fallback logic
3. Selectors build optimized querysets (`select_related/prefetch_related`)
4. Service composes facets, pagination and SEO payload
5. View renders full page or grid-append fragment

### Checkout

1. `CheckoutSubmitView` delegates to `CheckoutSubmissionService`
2. Submission parsing, cart normalization and order creation happen in service layer
3. Transaction finalizes totals, discounts and seller splits
4. Search/recommendation attribution feedback is queued via Celery after commit
5. View returns redirect or payment panel fragment (HTMX)

## Operational Dependencies

- PostgreSQL: primary transactional store
- Redis: cache, Celery broker/result backend
- OpenSearch: catalog/search retrieval
- Celery worker + beat: async and scheduled jobs

## Current Engineering Rules

- Keep views thin; move orchestration into services
- Prefer ORM + selectors with `select_related/prefetch_related`
- Add explicit observability for search, checkout, payments, and seller ops
- Keep legacy import compatibility during package moves until tests are updated

## Architecture Decisions

- ADR index: `docs/adr/README.md`
- `0001`: modular shopfront boundaries
- `0002`: ML dependencies moved to optional extras

## Current Hot Spots

- `backend/shopfront/views/catalog.py`
- `backend/shopfront/views/checkout_flow.py`
- `backend/users/views/helpers.py`

These files should be treated as refactor candidates first when complexity grows again.
