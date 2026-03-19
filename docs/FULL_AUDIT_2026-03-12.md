# Full Project Audit 2026-03-12

## Scope

This audit covers the current state of the `servio` monorepo across:

- backend architecture and code quality
- frontend storefront stack and HTMX/UI patterns
- DevOps, deployment, CI/CD, and observability
- project documentation and operational readiness

The audit is based on repository inspection, targeted configuration/code reads, and limited local verification. It is not a formal penetration test and it is not a full end-to-end runtime validation.

## Verification Performed

Confirmed during this pass:

- compose configs parse successfully:
  - `docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet`
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml config --quiet`
- skill-independent local inspection of backend, frontend, workflow, and deploy files
- browser smoke for storefront shell, catalog, and checkout
- pixel-based visual regression check for storefront shell, catalog, and checkout
- targeted checkout/payment regression slices in compose-backed test runs
- checkout refactor validation with `py_compile` and Ruff
- deterministic smoke-data seeding for browser checks
- expanded browser smoke and visual regression coverage for product, cart, filled-cart, and mobile storefront states
- hotspot review of:
  - signals and Celery task boundaries
  - search/OpenSearch flow
  - checkout and payment flow
  - logging and notifications
  - base template, frontend asset loading, HTMX usage
  - CI and deploy workflows

Attempted but not fully executable in the current shell context:

- `backend/manage.py check`
- local pytest slices using the repo virtualenv

These failed because the local non-compose shell defaulted to production settings and a `db` hostname that is only resolvable inside compose. This is itself an audit finding.

## Remediation Update

Completed immediately after this audit pass:

- deploy script naming drift was corrected for OpenSearch service and volume names
- prod compose PostgreSQL volume name was aligned with the base compose file
- `backend/manage.py` now defaults to dev settings unless `DJANGO_SETTINGS_MODULE` is explicitly set
- `make check-local` was added as an explicit compose-backed Django check entrypoint
- storefront favorites state now uses cache with explicit invalidation on favorite toggle
- storefront cart badge context now caches the price snapshot by cart signature instead of querying product pricing on every render
- checkout fake-payment FSM fallbacks were narrowed from blanket `except Exception` to `TransitionNotAllowed` with structured logging
- remaining broad exception handling was narrowed in OpenSearch/search/logging and Telegram notify hotspots
- CI now validates the frontend Tailwind asset build and ensures `backend/static/css/app.css` is produced
- frontend architecture documentation was refreshed to match the current templates plus HTMX plus Tailwind runtime model
- dev nginx metrics endpoint access was corrected so `nginx-exporter` can start cleanly in the compose metrics stack
- `shopfront` model-to-migration drift for `RecentlyViewedProduct.updated_at` was resolved with an explicit migration
- fake and online payment page/event handling in checkout views was deduplicated into shared helpers without changing tested behavior
- checkout submit flow was partially extracted into a dedicated service layer module
- checkout guest-access and payment support logic were extracted from `checkout_views.py` into a dedicated helper module
- browser smoke coverage was added for the storefront shell, catalog, and checkout pages
- pixel-based visual regression checks were added for storefront shell, catalog, and checkout screenshots
- automated deploy-versus-compose drift validation was added to CI
- storefront context processors were tightened further to remove broad exception handling and duplicate cart session parsing
- global product-card cart/favorite state moved out of context processors into request-scoped template tags
- cart, payment, and guest-order checkout views were split into dedicated modules with compatibility exports
- checkout page and submit orchestration were extracted into `checkout_flow_views.py`, leaving `checkout_views.py` as a compatibility/export module
- browser smoke and visual baselines were expanded to cover product, cart, filled-cart, and mobile storefront states
- frontend base template now gates page-specific scripts by `page_type`
- frontend base template now also gates selected page-specific CSS assets by `page_type`
- debug-mode placeholder secret usage now emits explicit backend warnings
- bot health now exposes internal-token auth status and logs clearer fallback reasons
- documentation ownership was formalized in `docs/DOC_OWNERSHIP_2026-03-13.md`
- `README.md` was aligned as the repo entrypoint and linked to the current source-of-truth docs

## Remediation Status

### Done

- P0 deploy/compose drift for OpenSearch service naming and persistent volume naming
- local DX fix for `manage.py` default settings selection
- explicit local Django check entrypoint via `make check-local`
- partial reduction of global storefront request-time load:
  - favorites state caching
  - cart badge price snapshot caching
- checkout/payment FSM fallback tightening for fake-payment transitions
- narrowed exception handling in search/indexing/logging/bot integration hotspots
- frontend CI asset build validation
- refreshed frontend architecture documentation
- dev metrics stack fix for `nginx-exporter` against the Nginx status endpoint
- resolved `shopfront` migration drift for `RecentlyViewedProduct.updated_at`
- reduced duplication in checkout payment page/event handling
- extracted a meaningful portion of checkout submit orchestration into a service module
- extracted guest-order access, payment event, and payment panel support logic out of `checkout_views.py`
- added browser smoke automation for server-rendered storefront pages
- added visual regression checks with baseline, current, and diff artifacts
- added an automated deploy/compose drift guard to CI
- reduced repeated cart parsing and exception swallowing in global storefront context processors
- removed global `cart_product_ids`, `cart_qty_map`, and `favorite_product_ids` template contract from context processors
- split cart, payment, and guest-order checkout views into narrower modules
- completed checkout decomposition by moving checkout page and submit orchestration into `checkout_flow_views.py`
- reduced `backend/shopfront/checkout_views.py` to a compatibility/export module
- expanded visual coverage to product, cart, filled-cart, and mobile storefront states
- moved page-specific storefront scripts behind `page_type` checks in `base.html`
- moved selected page-specific storefront CSS assets behind `page_type` checks in `base.html`
- made placeholder secret usage and bot internal-token auth fallback more explicit in runtime signals
- added an explicit documentation ownership map
- aligned `README.md` as the repository entrypoint

### Follow-up Opportunities

- deeper auth-bound interactive visual coverage such as favorite or account-specific mutation states
- further legacy CSS reduction and shared-asset slimming over time
- ongoing documentation freshness for `README.md` and ownership docs as the repo evolves

The findings below describe the audited state and should be read together with these immediate fixes.

For a concise Russian-language backlog of what remains, see `docs/REMAINING_WORK_RU_2026-03-13.md`.

## Executive Summary

The project has materially improved architecture compared with the older monolith state. The strongest areas today are:

- domain separation is visible and mostly coherent
- search moved toward explicit OpenSearch and async maintenance boundaries
- backend docs and architecture docs now exist
- observability stack is present and reasonably integrated
- CI now includes deploy-preflight security checks, frontend asset build validation, browser smoke, visual regression checks, and deploy/compose drift validation

The main remaining risks now are operationally smaller than at the start of this audit cycle:

1. visual regression coverage is now real across desktop and mobile shell states, including deterministic cart-state transitions, but can still be deepened for auth-bound mutations
2. frontend shell asset loading is healthier and more page-scoped than before, but legacy and modern layers still coexist
3. some findings below are historically closed but remain useful as a record of what changed during remediation

## Priority Findings

### P0

#### 1. Production deploy script is inconsistent with the current compose topology

Status:

- closed during remediation

Files:

- `scripts/deploy_prod.sh:107`
- `scripts/deploy_prod.sh:181`
- `scripts/deploy_prod.sh:198`
- `docker-compose.yml:184`
- `docker-compose.yml:231`
- `docker-compose.prod.yml:46`

Problem:

- deploy script creates `servio_esdata`, but the active compose file uses `servio_opensearchdata`
- deploy script starts service `es`, but the active service name is `opensearch`
- prod compose overrides `pgdata` to `bad-guys-shop_pgdata`, while the base compose and deploy script expect `servio_pgdata`

Why this is risky:

- first-time or recovery deployments can fail or partially bootstrap
- rollout scripts can create unused volumes and still miss the real stateful volume
- service startup commands can silently diverge from the actual runtime graph
- restore/rebuild procedures become error-prone under incident pressure

Recommended fix:

- unify service and volume names across `docker-compose.yml`, `docker-compose.prod.yml`, and `scripts/deploy_prod.sh`
- remove legacy `es` naming entirely
- decide on one canonical PostgreSQL volume name and use it everywhere
- add a CI check that diffs deploy script assumptions against compose output

### P1

#### 2. Local management commands default to production settings and break non-compose verification

Status:

- largely closed during remediation
- local shell ergonomics were fixed by defaulting `manage.py` to dev settings and adding `make check-local`
- compose-backed verification remains the recommended path for DB-backed commands

Files:

- `backend/manage.py:5`
- `backend/manage.py:8`
- `backend/config/settings/base.py:95`
- `backend/config/settings/base.py:389`

Problem:

- `manage.py` defaults to `config.settings.prod` when `DEBUG` is unset
- database host defaults to `db`, which only resolves in compose
- strict production checks then block plain local commands unless a full prod-like env is provided

Observed result:

- `./.venv/bin/python manage.py check` failed locally with `ImproperlyConfigured`
- targeted pytest slices failed locally because hostname `db` could not be resolved outside compose

Why this is risky:

- ad hoc debugging and maintenance commands are confusing outside docker-compose
- contributors can think the project is broken when the real issue is hidden environment coupling
- documentation and shell ergonomics drift apart

Recommended fix:

- default `manage.py` to dev settings unless `DJANGO_SETTINGS_MODULE` is explicitly set
- keep production strictness in CI and prod startup, not as the default local shell mode
- add a `make check-local` or documented compose-backed alias as the only blessed runtime check path

#### 3. Global storefront context processors still perform expensive request-time work

Status:

- materially remediated
- favorites state and cart price snapshots are cached
- repeated cart parsing and broad exception swallowing were reduced
- product-card cart/favorite state moved to request-scoped template tags instead of global context
- remaining global storefront context is now mostly shell-level

Files:

- `backend/shopfront/context_processors.py:41`
- `backend/shopfront/context_processors.py:61`
- `backend/shopfront/context_processors.py:178`

Problem:

- `cart_badge()` parses session cart, loads products, prefetches seller offers, applies offer snapshots, and computes subtotal on every request
- `favorites_state()` queries up to 2000 favorite product ids on every authenticated request
- these processors are registered globally in template settings

Why this is risky:

- storefront latency and DB pressure grow with unrelated page traffic
- every HTMX fragment render inherits this cost unless explicitly bypassed
- authenticated browsing cost scales with session/cart size, not only with the page itself

Recommended fix:

- split lightweight header state from expensive cart/favorites enrichment
- cache computed cart badge state more aggressively or update it on cart mutation boundaries
- load full favorite state only on pages that render favorite affordances

#### 4. Checkout/payment state transitions still fall back through broad exception handling

Status:

- partially remediated
- fake-payment transitions now only fall back on `TransitionNotAllowed` and emit structured logs
- checkout orchestration is still not fully isolated from views

Files:

- `backend/shopfront/checkout_views.py:328`
- `backend/shopfront/checkout_views.py:336`
- `backend/shopfront/checkout_views.py:343`
- `backend/shopfront/checkout_views.py:350`

Problem:

- fake payment event handling attempts FSM transitions and falls back to direct status mutation on any exception
- illegal transitions and model contract breaks are therefore converted into silent status assignments

Why this is risky:

- payment/debugging incidents become harder to diagnose
- state transitions can drift from the intended FSM rules
- behavior regressions may only surface later in fulfillment or analytics

Recommended fix:

- catch only expected FSM transition exceptions
- log the exact rejected transition and keep the failure visible
- centralize order/payment status orchestration in a dedicated service instead of view-local fallbacks

#### 5. Broad exception swallowing remains in operationally important paths

Status:

- mostly remediated in reviewed hotspots
- keep this section as a historical record for search/logging/bot cleanup already performed

Representative files:

- `backend/shopfront/search.py:130`
- `backend/catalog/opensearch_index.py:125`
- `backend/core/logging_utils.py:52`
- `bot/app/main_notify.py:92`
- `bot/app/main_notify.py:107`
- `bot/app/main_notify.py:132`
- `bot/app/main_notify.py:160`
- `bot/app/main_notify.py:181`
- `bot/app/main_notify.py:227`
- `bot/app/main_notify.py:249`

Problem:

- some blanket `except Exception` blocks intentionally degrade behavior, but several still suppress valuable root-cause data or convert integration failures into silent skips

Why this is risky:

- search/indexing failures can be under-reported
- bot delivery fallback paths hide actual delivery reasons
- request context cleanup relies on private contextvars internals and silently ignores failure

Recommended fix:

- narrow exceptions where the failure mode is known
- keep fallback behavior, but attach structured reason codes everywhere
- remove private attribute reliance in `clear_request_context()`

#### 6. CI validates backend only; frontend build and UI regression protection are still absent

Status:

- closed during remediation
- CI now installs Node dependencies, builds Tailwind, runs browser smoke, runs pixel-based visual regression, and checks deploy/compose drift

Files:

- `.github/workflows/ci.yml:1`
- `package.json:1`
- `backend/templates/shopfront/base.html:51`
- `docs/frontend_audit_2026-03-07.md:85`

Problem:

- CI runs backend tests, deploy preflight, coverage gate, and Ruff
- CI does not install Node dependencies
- CI does not run `npm run tw:build`
- CI does not validate template/static regressions or any browser/screenshot checks

Why this is risky:

- broken Tailwind output or broken static asset expectations can merge undetected
- HTMX regressions are only partially covered by backend HTML tests
- the project relies heavily on server-rendered UI, so absence of UI validation is now a real release risk

Recommended fix:

- add a frontend build step in CI
- archive built CSS artifact or fail on diff
- add at least a smoke browser check for home, catalog, product, cart, and checkout
- extend visual regression coverage to header/mobile nav/cart controls and HTMX mutation states

### P2

#### 7. Frontend documentation is stale relative to the actual runtime asset model

Status:

- closed during remediation with refreshed frontend architecture documentation

Files:

- `docs/frontend_audit_2026-03-07.md:5`
- `docs/frontend_audit_2026-03-07.md:49`
- `docs/frontend_audit_2026-03-07.md:56`
- `backend/templates/shopfront/base.html:51`

Problem:

- the frontend audit still describes runtime around `theme.css` and `unified-theme.css`
- current `base.html` loads a split asset model: legacy CSS shards plus tokens/base/layout/component styles and a large JS set

Why this matters:

- future frontend refactors can optimize against the wrong runtime model
- contributors lose trust in docs when debugging styling or asset ordering problems

Recommended fix:

- publish a new frontend architecture note matching the current split CSS/JS structure
- explicitly document what is legacy, what is canonical, and what is transitional

#### 8. Frontend shell has high asset and dependency complexity

Status:

- still open
- partially remediated
- page-specific storefront scripts are now gated by `page_type`
- remaining issue is mostly shared asset weight and legacy-css coexistence

Files:

- `backend/templates/shopfront/base.html:39`
- `backend/templates/shopfront/base.html:51`
- `backend/templates/shopfront/base.html:75`
- `backend/templates/shopfront/base.html:80`

Problem:

- `base.html` loads external fonts, GTM, optional Sentry browser SDK, many CSS files, and many JS files on nearly every page
- several scripts are global even though the behavior is page-specific

Why this is risky:

- increases initial render complexity and debugging surface
- raises the cost of HTMX page-enter reinitialization correctness
- makes performance tuning and CSP tightening harder

Recommended fix:

- classify assets into always-on, page-scoped, and deferred
- move more page scripts behind template blocks or page-type checks
- measure real storefront page weight before further feature expansion

#### 9. Checkout module remains oversized after the first decomposition pass

Status:

- still open, but materially improved
- submit orchestration, guest/payment support, cart views, and payment/guest-order views have already been extracted from the main view module

Files:

- `backend/shopfront/checkout_views.py:1`

Measured size:

- `backend/shopfront/checkout_views.py`: 1133 lines

Problem:

- cart views, checkout submission, guest order detail, fake payments, online payments, analytics payloads, and SEO helpers still coexist in one module

Why this is risky:

- regression surface is still large for every checkout change
- onboarding remains expensive in the most sensitive commerce flow

Recommended fix:

- split by responsibility:
  - cart mutation and fragments
  - checkout form and submit flow
  - guest order access
  - payment transition pages and events

#### 10. Some operational security posture is still transitional

Status:

- partially remediated
- debug-mode placeholder secret usage now emits explicit warnings
- bot health/readiness now exposes internal-token auth mode and placeholder-secret state
- current state is still acceptable for local development only and should be tightened further for production-grade posture

Files:

- `deploy/nginx/nginx.dev.conf:17`
- `backend/config/settings/base.py:264`
- `bot/app/common.py:45`

Problem:

- dev CSP still requires `'unsafe-inline'` and `'unsafe-eval'`
- backend and bot still carry placeholder defaults for critical shared secrets in base config
- bot internal-token auth can disable itself automatically when placeholder secrets remain

Why this matters:

- acceptable for local dev, but dangerous if env separation drifts
- encourages hidden insecure fallback behavior instead of loud failure

Recommended fix:

- keep placeholders only in dev-only env examples, not in runtime base assumptions
- make insecure bot auth disablement more visible in logs and readiness
- document strict separation between dev and production secret policy

### P3

#### 11. Existing frontend and architecture docs now compete instead of forming one source of truth

Status:

- largely remediated
- documentation ownership is now explicit in `docs/DOC_OWNERSHIP_2026-03-13.md`
- remaining gap is keeping `README.md` aligned as a clean entrypoint

Files:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/BACKEND_GUIDE.md`
- `docs/frontend_audit_2026-03-07.md`
- `docs/marketplace_2026_execution_plan.md`

Problem:

- there is good documentation volume, but no explicit ownership model or freshness contract
- some docs are current operational guides, others are historical snapshots, and the distinction is not always obvious

Recommended fix:

- mark each doc as one of:
  - source of truth
  - current guide
  - historical audit
  - archived plan

## Area-by-Area Assessment

### Backend

Strengths:

- modular Django apps and subpackages are materially better than before
- search client and search service separation is clear
- async maintenance via Celery is now present for product indexing and downstream commerce synchronization
- tests cover many business flows, not only smoke paths

Main backend risks:

- still-heavy global request helpers
- oversized checkout module
- broad exception fallback in sensitive flows
- local command ergonomics strongly coupled to compose

### Frontend

Strengths:

- server-driven UI direction is coherent with the product
- HTMX usage is extensive and mostly consistent
- component extraction is visible in templates
- page-level JS files exist instead of one giant storefront script

Main frontend risks:

- base shell loads many assets globally
- visual coverage still misses several important interactive states
- legacy and new CSS structures still coexist

### Architecture

Strengths:

- domain boundaries are now recognizable
- search and async-first decisions generally move in the right direction
- observability is treated as part of platform design, not an afterthought

Main architecture risks:

- request-time convenience code still leaks across the whole storefront
- some flows still hide orchestration inside very large view modules
- frontend and backend operational contracts are healthier than before, but still not fully page-scoped

### DevOps and Operations

Strengths:

- CI includes tests, lint, coverage checks, and Django deploy checks
- observability stack includes Prometheus, Loki, Grafana, exporters, and blackbox checks
- local compose model is much better than stale image-only development

Main DevOps risks:

- destructive remote deploy sequence depends on the repo state being exactly right

## Recommended Next Steps

### Immediate

1. Reduce global storefront context further so cart/favorites enrichment is page-scoped instead of global.
2. Continue splitting `backend/shopfront/checkout_views.py` until submit, guest access, and payment surfaces are fully isolated.
3. Extend visual regression coverage to product, cart, mobile navigation, and HTMX mutation states.
4. Review frontend shell asset loading and move more scripts/styles to page-scoped delivery.

### Near Term

1. Tighten dev/prod secret posture and make insecure fallback modes louder.
2. Define documentation freshness and source-of-truth ownership across `README`, architecture docs, and audit artifacts.
3. Measure storefront asset weight and remove always-on dependencies that are not needed for every page.
4. Finish removing remaining broad exception swallowing outside the already remediated hotspots.

### Later

1. Add richer UI-state regression checks for authenticated flows and HTMX mutations.
2. Introduce stronger deploy safety around remote repo state and rollout sequencing.
3. Continue converting convenience-heavy request logic into service- or page-scoped flows.

## Bottom Line

Servio is no longer blocked by missing architecture or missing process. The remaining work is concentrated in three places: reducing global storefront coupling, finishing checkout decomposition, and deepening UI regression coverage. Those are now tractable follow-up tasks rather than structural blockers.
