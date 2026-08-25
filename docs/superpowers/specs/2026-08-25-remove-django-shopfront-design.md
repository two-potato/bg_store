# Remove Django Shopfront: Next.js-only Storefront Architecture

Date: 2026-08-25
Status: Approved in chat; implementation pending written-spec review
Branch: `codex/all-local-changes-20260331-110158`

## Goal

Make `frontend/` (Next.js) the only customer-facing storefront and remove `backend/shopfront` as an architectural layer.

Django remains the transactional/domain backend and public API. Independent services remain appropriate for workloads that benefit from separate deployment and scaling, currently search and recommendations.

## Current Problem

`backend/shopfront` mixes unrelated responsibilities:

- Django-rendered storefront pages and URL routing;
- cart mutation and checkout orchestration;
- catalog page assembly and selectors;
- public/internal API endpoints;
- search orchestration and OpenSearch integration;
- recommendation orchestration, ranking, experiments, ML helpers, attribution and observability.

At the same time `frontend/` is already the intended Next.js storefront, and top-level `services/` already contains `search-api`, `recommendation-api`, and `platform-api`.

This creates duplicate presentation paths and an incorrect dependency direction: business/application logic is coupled to a module named after the UI surface.

## Target Architecture

```text
Browser
  |
  v
frontend/ (Next.js, only storefront)
  |
  v
backend/ (Django domain/API backend)
  |-- users/
  |-- catalog/
  |-- commerce/
  |-- orders/
  |-- core/
  |
  |-- HTTP/internal client --> services/search-api
  `-- HTTP/internal client --> services/recommendation-api
```

Django must not render the customer storefront after migration.

## Architectural Rules

1. `frontend/` owns customer-facing rendering, routing and page composition.
2. Django owns transactional state, permissions, domain invariants, database writes and stable API contracts.
3. Domain logic belongs to the owning Django app, never to a UI-oriented package.
4. Search-specific execution belongs in `services/search-api` where independent deployment/scaling is useful.
5. Recommendation-specific execution belongs in `services/recommendation-api` where independent deployment/scaling is useful.
6. Django may retain thin adapters/clients for those services, including timeout, authentication, fallback and response normalization, but not duplicate their algorithms.
7. `services/platform-api` must not become a dumping ground or a replacement for the Django backend. It should remain only if it has an independently justified responsibility.
8. Public URLs consumed by Next.js should remain compatible where practical during migration. Internal import paths may change freely with tests updated in the same commit series.
9. No Django HTML storefront fallback remains after completion.

## Migration Map

### Cart and Checkout

Move responsibilities from files such as:

- `shopfront/cart_store.py`
- `shopfront/cart_mutation_service.py`
- `shopfront/cart_checkout_service.py`
- `shopfront/checkout_common.py`

into the owning transactional domain, primarily `commerce/` and `orders/`.

Rules:

- cart state/mutations belong to commerce;
- order creation and checkout transaction boundaries belong to orders/commerce according to existing model ownership;
- serializers/API views remain thin and delegate to application services;
- no HTTP or template assumptions inside application services.

### Catalog

Move:

- `shopfront/catalog_selectors.py`
- reusable domain portions of `shopfront/catalog_page_service.py`

into `catalog/`.

Next.js-specific page composition should not be recreated in Django. The backend should expose domain/API data, not prepare template page contexts.

### Search

Move search execution/orchestration from `shopfront/searching/` into `services/search-api` where it belongs.

Django keeps only a thin search gateway if needed for authentication, public API stability or fallback policy.

The service owns:

- OpenSearch adapter behavior;
- search query execution;
- ranking/search-specific orchestration;
- search observability specific to the service.

Domain data remains sourced from Django-owned persistence/contracts rather than creating a second source of truth.

### Recommendations

Move recommendation execution from `shopfront/recommendation/` into `services/recommendation-api`.

The service owns:

- candidate/ranking execution that is recommendation-specific;
- scoring and ML inference helpers;
- recommendation experiments/policies;
- recommendation-service observability.

Django retains transactional event persistence or domain records only where those records belong to Django's source of truth, and exposes a thin integration boundary.

### API

Remove `shopfront.api` as the generic API namespace.

Route endpoints through owning apps:

- catalog endpoints -> `catalog`;
- commerce/cart endpoints -> `commerce`;
- checkout/order endpoints -> `orders`/`commerce` according to model ownership;
- search endpoint -> thin Django gateway or direct service route, chosen to preserve authentication/API contract;
- recommendation endpoint -> thin Django gateway or direct service route, chosen to preserve authentication/API contract.

Prefer retaining existing public `/api/...` paths during the migration to avoid unnecessary Next.js churn.

### HTML and Templates

Delete customer-facing Django storefront pieces once Next.js coverage is confirmed:

- `shopfront.urls` root include;
- storefront Django views;
- storefront templates;
- storefront-only templatetags;
- template context/page assembly helpers;
- tests whose sole purpose is Django-rendered customer pages.

Django admin and any explicitly non-storefront operational HTML are unaffected.

## URL Configuration

Current root routing includes both API and `path("", include("shopfront.urls"))`.

Target root routing contains system/admin/domain APIs only. `/` is served by Next.js/nginx, not Django.

The Swarm/nginx configuration must route customer traffic to Next.js and backend API/admin/system paths to Django.

## Compatibility Strategy

Migration is incremental but the final state contains no `shopfront` package.

Sequence:

1. Characterize current API behavior with contract tests.
2. Move cart/checkout domain logic to owning Django apps without changing public API behavior.
3. Move catalog selectors/domain logic to `catalog` and remove Django page-context assembly.
4. Move search implementation to `services/search-api`; keep a thin backend gateway while preserving API contracts.
5. Move recommendation implementation to `services/recommendation-api`; keep a thin backend gateway while preserving API contracts.
6. Move API views/serializers/URLs into owning apps.
7. Remove Django storefront HTML routes/templates.
8. Remove `shopfront` from `INSTALLED_APPS`, imports, coverage configuration and tests.
9. Remove the package entirely.
10. Run full CI, container/Swarm validation and browser smoke against Next.js.

## Failure and Fallback Policy

Search and recommendation are non-transactional dependencies and must fail predictably.

- explicit short timeouts;
- structured error logging/metrics;
- search may use a documented degraded fallback only if already required by product behavior;
- recommendation failure must not block catalog/cart/checkout;
- cart, checkout and order writes must never depend on recommendation/search availability.

No silent duplication of search/recommendation algorithms in Django solely as a fallback.

## Testing Strategy

Before moving code, add/retain characterization tests for externally observable behavior.

Required gates:

- domain unit tests for moved cart/checkout/catalog application services;
- API contract tests for paths consumed by Next.js;
- search service tests;
- recommendation service tests;
- integration tests for Django service gateways;
- `makemigrations --check --dry-run`;
- Django production checks;
- Ruff and type/static checks;
- full pytest and coverage gate;
- Next.js typecheck/build;
- Docker/Swarm stack validation;
- browser smoke proving storefront pages are served by Next.js;
- repository search proving no runtime import or installed-app reference to `shopfront` remains.

## Deployment Impact

The change must not require a database migration merely because code moves packages. Existing Django model ownership must be preserved unless a separate migration is explicitly justified.

Docker/Swarm manifests must reflect the actual service boundaries after migration. Search and recommendation healthchecks, resource limits, environment variables and internal URLs must remain explicit.

Nginx must not route `/` to Django after completion.

## Non-Goals

- Rewriting Django as FastAPI.
- Moving all domain logic into microservices.
- Splitting catalog, commerce, orders or users into independent services now.
- Changing database ownership without a concrete need.
- Changing public API shapes only for aesthetic reasons.
- Keeping duplicate Django and Next.js storefronts.

## Completion Criteria

The migration is complete only when all of the following are true:

- Next.js is the only customer storefront;
- `backend/shopfront` no longer exists;
- Django root URL config no longer includes storefront HTML routes;
- cart/checkout/catalog logic resides in owning Django domain apps;
- search execution resides in `services/search-api`;
- recommendation execution resides in `services/recommendation-api`;
- public API contracts needed by Next.js pass their tests;
- no `shopfront` runtime imports remain;
- full CI and security workflows are green;
- Swarm config validates with the new boundaries;
- browser smoke reaches Next.js storefront and backend health/API endpoints successfully.
