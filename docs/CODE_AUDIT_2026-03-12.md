# Code Audit 2026-03-12

## Scope

This audit covers the current state of the `servio` monorepo with focus on:

- `backend/`
- `bot/`
- operational glue visible in compose, settings, and docs

The review is based on source inspection, repository structure, code hotspots, and targeted quality signals. It is not a full formal security audit and it is not a full test-run report.

## Status After Remediation Pass

Completed in the current pass:

- synchronous OpenSearch indexing was removed from `catalog` model signals
- seller-store-triggered reindex was moved out of synchronous `commerce` signals
- company workspace synchronization was moved out of synchronous `commerce` signals
- order notification formatting was extracted from `orders/tasks.py` into a dedicated service module
- static and merchandising page views were extracted from `backend/shopfront/views.py` into `backend/shopfront/page_views.py`
- cart, checkout, guest-order, and payment flows were extracted from `backend/shopfront/views.py` into `backend/shopfront/checkout_views.py`
- favorites, compare, saved-list, and live-search views were extracted from `backend/shopfront/views.py` into `backend/shopfront/discovery_views.py`
- product detail, seller storefront/profile, and review views were extracted from `backend/shopfront/views.py` into `backend/shopfront/product_views.py`
- catalog and filter-suggestion views were extracted from `backend/shopfront/views.py` into `backend/shopfront/catalog_views.py`
- `backend/shopfront/views.py` was converted into a package-backed helper layer at `backend/shopfront/views/`
- `backend/orders/models.py` was split into a package at `backend/orders/models/`
- `backend/commerce/models.py` was split into a package at `backend/commerce/models/`
- `backend/catalog/models.py` was split into a package at `backend/catalog/models/`
- `backend/users/views.py` was split into a package at `backend/users/views/`
- local backend dev/test services were switched to source bind mounts, and compose-backed tests now run against the live working tree
- broad exception handling was tightened in notifications, order scheduling/tasks, fake payment transitions, and cart summary helpers
- auth and account-entry HTML views were extracted from `backend/users/views_html.py` into `backend/users/views_auth_html.py`
- buyer, company-account, and order-account HTML views were extracted from `backend/users/views_html.py` into `backend/users/views_account_html.py`
- seller cabinet views were extracted behind routing into `backend/users/views_seller_html.py`
- the original `backend/users/views_html.py` seller block was removed after routing migration
- the original `backend/users/views_html.py` buyer/account block was removed after routing migration
- regression tests were added for async signal scheduling
- several silent broad exception handlers in critical runtime paths were tightened or removed, including cart, review, compare, auth, and checkout input parsing
- containerized `manage.py check` passes against the live working tree
- compose-backed targeted pytest slices pass after the package refactor

Still outstanding:

- repo-wide elimination of broad `except Exception`

## Executive Summary

The project is functional and has clear domain separation, but it is carrying growing operational and architectural debt. The main risks are:

1. oversized modules that accumulate unrelated behavior
2. synchronous side effects in signals and request flows
3. broad exception swallowing that hides production failures
4. inconsistent type coverage and service boundaries
5. local/runtime drift caused by image-based containers and a growing number of manual steps

The backend is already beyond the point where "just keep adding features" is safe without cleanup. The next wave of work should prioritize reliability and decomposition over more surface area.

## What Is Good

- domain split is still recognizable: `catalog`, `commerce`, `orders`, `shopfront`, `users`, `core`
- API documentation now exists and is materially better than before
- search migration away from Elasticsearch is already reflected in code structure
- tests exist across many business domains instead of being limited to smoke checks
- shared infra modules such as logging and notifications are being centralized

## Priority Findings

### P0

#### 1. Synchronous indexing and cross-domain side effects inside model signals

Files:

- `backend/catalog/signals.py`
- `backend/commerce/signals.py`

Problem:

- product indexing is triggered directly in Django model signals
- seller-store changes iterate products and reindex them synchronously
- legal-entity approval flows create downstream entities and memberships implicitly through signals

Why this is risky:

- request latency becomes unpredictable
- save/delete operations can fail because external indexing failed
- signal behavior is hard to reason about and hard to test
- repeated saves can trigger duplicate or expensive side effects

Recommended fix:

- move OpenSearch indexing to explicit service calls or Celery tasks
- keep signals minimal: enqueue work, do not perform heavy work
- add idempotent task boundaries for entity creation and search reindex events

#### 2. Broad `except Exception` usage is too widespread

Signals from source search:

- many occurrences across `shopfront`, `core`, `orders`, `commerce`, `bot`

Representative files:

- `backend/shopfront/views/helpers.py`
- `backend/shopfront/context_processors.py`
- `backend/orders/tasks.py`
- `backend/core/notifications.py`
- `bot/app/main_notify.py`

Problem:

- exceptions are often swallowed with `pass`
- some branches downgrade real production errors into silent behavior changes

Why this is risky:

- bugs become invisible
- support incidents become harder to reproduce
- monitoring signal quality drops

Recommended fix:

- replace blanket `except Exception` with narrower exception classes
- where swallowing is intentional, always log with context and a reason code
- reserve silent `pass` for genuinely non-critical UI-only degradation

### P1

#### 3. Critical modules are too large and need decomposition

Line counts:

- `backend/shopfront/views.py`: 3415 lines before decomposition
- `backend/users/views_html.py`: 2711 lines
- `backend/commerce/views_public.py`: 440 lines
- `backend/orders/tasks.py`: 379 lines

Problem:

- these modules contain many responsibilities at once
- view logic, orchestration, analytics payloads, fallback logic, and response shaping are mixed together

Why this is risky:

- onboarding cost is high
- regression risk rises with every edit
- test targeting becomes less precise

Recommended fix:

- split `shopfront/views.py` by page area or capability:
  - catalog pages
  - product pages
  - checkout
  - account-like interactive fragments
- split `users/views_html.py` by account area
- move large helper clusters into service/selectors modules with explicit contracts

#### 4. Domain model files accumulate unrelated business concerns unless split early

Representative files:

- `backend/commerce/models.py`
- `backend/catalog/models.py`

Problem:

- legal entity, company, memberships, approval policy, contacts, delivery addresses, seller stores, and reviews are mixed in one file

Why this is risky:

- file navigation is poor
- merge conflicts become common
- domain ownership is blurred

Recommended fix:

- split models by subdomain:
  - legal entities and memberships
  - company workspace
  - seller marketplace
  - moderation requests
- completed for `commerce` and `catalog`; keep applying the same pattern to future model growth

#### 5. Image-based runtime causes local staleness and DX friction

Files:

- `docker-compose.yml`
- `backend/Dockerfile`

Problem:

- runtime containers do not fully reflect source edits without rebuild or manual copy
- docs and API schema can become stale relative to the working tree

Why this is risky:

- developers validate the wrong code
- debugging becomes misleading

Recommended fix:

- completed in local compose: backend, worker, beat, and backend-test now use source bind mounts while preserving the image-managed virtualenv
- keep image-based flow for CI and prod, but retain bind-mounted local dev for fast feedback

### P2

#### 6. Search layer still carries migration residue and naming drift

Files:

- `backend/shopfront/search.py`
- `backend/shopfront/search_service.py`
- `backend/catalog/opensearch_index.py`

Problem:

- the search architecture is improving, but migration residue remains in naming, logging events, and fallback assumptions
- low-level and orchestration layers are separated, which is good, but indexing and provider conventions are still evolving

Recommended fix:

- standardize naming across search, index, and logs around `opensearch`
- add one authoritative interface for index lifecycle
- document expected failure modes and fallback behavior

#### 7. Context processors are doing too much work

File:

- `backend/shopfront/context_processors.py`

Problem:

- request-time building of analytics, favorites, cart, compare state, categories, and monitoring payloads is bundled together

Why this is risky:

- every request pays for unrelated context assembly
- hidden performance regressions are easy to introduce

Recommended fix:

- split context processors by concern
- cache aggressively where safe
- avoid DB work in global context unless the page actually needs it

#### 8. Task layer mixes orchestration, formatting, and transport behavior

File:

- `backend/orders/tasks.py`

Problem:

- email formatting, Telegram formatting, recipient selection, and business triggers are all in the same task module

Recommended fix:

- extract message builders from Celery tasks
- keep tasks thin: load state, call service, log result
- add retry policy per transport type instead of generic task-level patterns

#### 9. Logging quality is improving, but conventions are not fully enforced

Files:

- `backend/core/logging_utils.py`
- many domain modules

Problem:

- some modules log structured extras well
- others still use inconsistent event names or skip logging for degraded branches

Recommended fix:

- define event naming guidelines
- require structured extras for external IO, fallback paths, and business rejections
- add a short logging style guide in `docs/`

#### 10. Bot service error handling needs the same hardening as backend

Files:

- `bot/app/main_notify.py`
- `bot/app/main_shop.py`
- `bot/app/common.py`

Problem:

- several broad exception handlers suppress transport and runtime issues
- this weakens the reliability of Telegram notifications, which are business-significant

Recommended fix:

- tighten exception boundaries
- propagate operational failures into logs with stable event names
- add focused tests for notification failure modes

## Security and Reliability Notes

### 1. Token-protected internal endpoints are correct in direction, but need stricter normalization

Examples:

- metrics token handling in `backend/core/views.py`
- internal token usage in notification and order approval flows

Improve:

- standardize token validation helpers
- document rotation procedure
- ensure all internal-only endpoints use one shared auth mechanism

### 2. External integrations need explicit timeout and failure contracts everywhere

Examples:

- DaData in `backend/commerce/views_public.py`
- bot notifications in `backend/core/notifications.py`
- OpenSearch in `backend/shopfront/search.py`

Improve:

- document timeout defaults centrally
- add fallback matrix in docs
- expose degraded-mode behavior in logs and maybe metrics

## Testing Gaps

### 1. There are many tests, but the project still needs stronger non-happy-path coverage

Add more tests for:

- signal idempotency
- fallback behavior when OpenSearch is down
- bot-service transport failures
- permission leakage across legal-entity boundaries
- stale-cache and malformed-session inputs in shopfront code

### 2. Architectural regression tests are missing

Examples:

- no guard against giant modules growing further
- no guard against new blanket `except Exception` usage
- no guard against request-time indexing or heavy signal behavior

Recommended fix:

- add a lightweight "architecture tests" module that fails on:
  - banned imports in specific layers
  - large module thresholds
  - direct external IO inside signals

## Documentation Gaps

Current docs are better than before, but still missing:

- explicit data-flow map for order lifecycle
- seller marketplace lifecycle
- search/index lifecycle
- internal notification topology
- operational playbook for local rebuild vs runtime freshness

## Recommended Improvement Plan

### Phase 1: Reliability Cleanup

- move signal side effects to Celery-backed tasks or explicit services
- replace silent broad exception handlers in critical flows
- centralize internal token validation helpers
- add focused tests for fallback and failure paths

### Phase 2: Decomposition

- split `shopfront/views.py`
- split `users/views_html.py`
- split monolithic model files by subdomain package
- extract message builders from `orders/tasks.py`

### Phase 3: Developer Experience

- enable backend code bind-mount in dev
- add architecture guard tests
- add logging conventions doc
- add runbook for search reindex and docs/schema refresh

## Concrete Backlog

### Must Do Soon

- [x] Replace synchronous indexing in `backend/catalog/signals.py`
- [x] Replace seller-store-triggered reindex loop in `backend/commerce/signals.py`
- [ ] Audit and reduce blanket `except Exception` in `backend/shopfront/views.py`
- [x] Extract thin services from `backend/orders/tasks.py`
- [ ] Add dev bind-mount strategy for backend code in compose

### Should Do Next

- [x] Split `backend/shopfront/views.py` into multiple modules
- [x] Split `backend/users/views_html.py` into account submodules
- [x] Split `backend/commerce/models.py` by subdomain
- [x] Split `backend/catalog/models.py` by subdomain
- [ ] Add architecture tests for module size and forbidden patterns
- [ ] Add logging conventions document

### Nice to Have

- [ ] Add generated dependency graph for backend apps
- [ ] Add metrics for degraded-mode fallbacks
- [ ] Add a local operational runbook for stale container vs stale schema debugging

## Method Notes

This audit used:

- repository structure review
- hotspot line counts
- targeted source inspection
- broad-pattern scan for risky exception handling and placeholders

It did not include:

- full production traffic profiling
- load testing
- full security pen-test
- exhaustive test-suite execution in this pass
