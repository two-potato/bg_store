# Shopfront Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `backend/shopfront` as a business/application layer so Next.js is the sole storefront, Django owns transactional/domain APIs, and search/recommendation execution lives behind dedicated service boundaries.

**Architecture:** Move domain logic to `catalog`, `commerce`, `orders`, and `core`; keep legacy recommendation persistence only in `legacy_shopfront_state` while migrations/state still require the historical app label. Move public/internal API ownership to domain API packages and keep search/recommendation gateways as thin Django adapters to `services/search-api` and `services/recommendation-api`. Delete Django HTML storefront routes/templates/static dependencies once no runtime imports remain.

**Tech Stack:** Django 6, DRF, Celery, PostgreSQL, Redis, FastAPI, Next.js, Docker Swarm, GitHub Actions.

**Spec:** Existing architectural decision: Next.js is the only storefront; Django is API/domain backend; search and recommendation are independent services.

## Global Constraints
- Preserve historical `shopfront` app-label migration compatibility through `legacy_shopfront_state` until a separate state migration removes it.
- Preserve API behavior expected by Next.js.
- Preserve old Celery task names only as temporary queue-drain aliases; new producers and Beat schedules use canonical domain paths.
- Do not introduce a generic BFF/application layer.
- Remove legacy Django HTML storefront rendering and asset build steps.

---

### Task 1: Inventory and dependency map
- [ ] Enumerate every `backend/shopfront/**` file and repository reference to `shopfront`.
- [ ] Classify ownership: catalog, commerce, orders, core, search, recommendation, legacy state, compatibility-only, delete.
- [ ] Verify URLs, Celery, settings, management commands, templates/static, tests.

### Task 2: Background task ownership
- [ ] Move contact feedback to `core.tasks`.
- [ ] Move checkout attribution feedback to Orders-owned tasks.
- [ ] Move stateful recommendation jobs to `legacy_shopfront_state.tasks` during migration.
- [ ] Switch Beat/producers to canonical task names and retain only queue-drain aliases.

### Task 3: Commerce and checkout extraction
- [ ] Replace remaining `shopfront` cart/checkout call sites with `commerce`/`orders` modules.
- [ ] Move checkout orchestration/support and session customer state to owning domains.
- [ ] Update tests/imports and delete wrappers after zero runtime users.

### Task 4: Catalog extraction
- [ ] Move catalog/product/store selectors and API-facing assembly to `catalog`.
- [ ] Delete template-only view-model shaping unused by Next.js.
- [ ] Update APIs/tests and remove storefront wrappers.

### Task 5: Search boundary
- [ ] Move pure search contracts/observability/execution to search service/gateway ownership.
- [ ] Keep Django-session attribution only as explicit backend adapter while needed.
- [ ] Remove runtime `shopfront.searching` imports.

### Task 6: Recommendation boundary
- [ ] Move stateless contracts/ranking/selection/observability to recommendation service/gateway ownership.
- [ ] Isolate ORM-dependent features/training under explicit backend/legacy-state ownership.
- [ ] Move management commands/tasks and remove runtime `shopfront.recommendation` imports.

### Task 7: API ownership and URL cleanup
- [ ] Rehome `shopfront/api/**` by domain while preserving stable public URLs.
- [ ] Remove `shopfront.api` and internal URL ownership.
- [ ] Validate schema/frontend requests.

### Task 8: Remove Django storefront presentation
- [ ] Remove Django HTML storefront routes/views.
- [ ] Remove legacy storefront asset build from CI.
- [ ] Remove unused storefront templates/static/context processors/templatetags.
- [ ] Preserve non-storefront Django admin/account surfaces that are still routed.

### Task 9: Remove `shopfront` package
- [ ] Replace/delete every runtime `shopfront` reference except explicit historical migration metadata.
- [ ] Remove runtime app configuration and delete package.

### Task 10: Verification and cleanup
- [ ] Run backend pytest/coverage and Ruff.
- [ ] Run Django production `check --deploy`.
- [ ] Run Next.js typecheck/build.
- [ ] Validate Swarm config/healthchecks.
- [ ] Search for dead `shopfront` imports/routes/assets and review PR diff.
