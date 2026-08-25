# Remove Django Shopfront Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сделать `frontend/` (Next.js) единственным storefront и полностью удалить `backend/shopfront`, сохранив публичные API-контракты и Django как transactional/domain backend.

**Architecture:** Миграция выполняется по доменным границам, а не механическим переносом каталога файлов. Cart/checkout/catalog переходят в соответствующие Django apps; search и recommendation становятся отдельными сервисами с тонкими Django gateway-слоями. Удаление HTML storefront, URL include и самого Django app выполняется только после того, как runtime-imports и контракты переведены.

**Tech Stack:** Django 6, DRF, PostgreSQL, Redis, Celery, OpenSearch, FastAPI/service containers, Next.js, pytest, Ruff, Docker/Swarm, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-25-remove-django-shopfront-design.md`

## Global Constraints

- `frontend/` — единственный customer-facing storefront.
- Django остаётся source of truth для каталога, корзины, checkout, заказов, auth, прав доступа и транзакционных записей.
- Публичные `/api/...` URL и JSON-shapes, используемые Next.js, сохраняются где это практически возможно.
- Search/recommendation failure не должен блокировать cart/checkout/order writes.
- Не переносить весь Django backend в `services/platform-api`.
- Не создавать database migration только из-за переноса Python-кода.
- Не оставлять Django HTML storefront/fallback после завершения.
- Каждый перенос проходит TDD: RED contract/domain test -> GREEN implementation -> regression/CI.

---

### Task 1: Зафиксировать API-контракты storefront перед переносом

**Files:**
- Create: `backend/tests/contracts/test_storefront_api_contracts.py`
- Read/characterize: `backend/shopfront/api/urls.py`
- Read/characterize: `backend/shopfront/api/internal_urls.py`
- Read/characterize: `backend/shopfront/api/serializers.py`
- Read/characterize: `backend/shopfront/api/views_search.py`
- Read/characterize: `backend/shopfront/api/views_recommendations.py`

**Interfaces:**
- Consumes: существующие `/api/...` endpoints.
- Produces: regression contract tests, которые должны оставаться зелёными до конца миграции.

- [ ] **Step 1: Написать contract tests для URL resolution и ключевых response-shapes**

Тесты должны проверять, что публичные paths resolve без ссылки на HTML storefront и что search/recommendation/cart/catalog endpoints сохраняют имена/маршруты.

- [ ] **Step 2: Запустить RED через GitHub Actions**

Expected: новый тест падает там, где целевые domain namespaces ещё не существуют.

- [ ] **Step 3: Не менять production code в этом task**

Этот task — characterization boundary.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/contracts/test_storefront_api_contracts.py
git commit -m "test: characterize storefront api contracts"
```

### Task 2: Перенести cart state и mutation service в `commerce`

**Files:**
- Create: `backend/commerce/services/cart_store.py`
- Create: `backend/commerce/services/cart_mutations.py`
- Create: `backend/commerce/tests/test_cart_services.py`
- Modify imports in API consumers that currently import:
  - `backend/shopfront/cart_store.py`
  - `backend/shopfront/cart_mutation_service.py`

**Interfaces:**
- Produces: API-compatible cart read/mutation functions with the same externally observable behavior.

- [ ] **Step 1: Написать failing unit tests против `commerce.services.cart_store` и `commerce.services.cart_mutations`.**
- [ ] **Step 2: RED CI.**
- [ ] **Step 3: Перенести минимальную domain logic без HTTP/template assumptions.**
- [ ] **Step 4: Перевести import consumers на новый namespace.**
- [ ] **Step 5: GREEN CI + existing cart/API tests.**
- [ ] **Step 6: Commit `refactor: move cart services to commerce`.**

### Task 3: Перенести checkout orchestration в `orders`/`commerce`

**Files:**
- Create: `backend/orders/services/checkout.py`
- Create: `backend/orders/services/checkout_common.py`
- Create: `backend/orders/tests/test_checkout_service.py`
- Migrate behavior from:
  - `backend/shopfront/cart_checkout_service.py`
  - `backend/shopfront/checkout_common.py`

**Interfaces:**
- Checkout transaction boundary remains in Django.
- Search/recommendation must never be required for order creation.

- [ ] **Step 1: RED tests for successful checkout, validation failure and transaction rollback semantics.**
- [ ] **Step 2: Implement minimal service move.**
- [ ] **Step 3: Update API imports.**
- [ ] **Step 4: GREEN CI and order regression tests.**
- [ ] **Step 5: Commit `refactor: move checkout orchestration to orders`.**

### Task 4: Перенести catalog selectors и удалить Django page-context composition

**Files:**
- Create: `backend/catalog/services/selectors.py`
- Create: `backend/catalog/tests/test_catalog_selectors.py`
- Migrate reusable domain logic from:
  - `backend/shopfront/catalog_selectors.py`
- Decompose/delete storefront-only parts of:
  - `backend/shopfront/catalog_page_service.py`

**Interfaces:**
- Backend returns catalog/domain/API data; не формирует template page contexts для Next.js.

- [ ] **Step 1: RED tests for category/product selector behavior.**
- [ ] **Step 2: Move reusable selectors to `catalog.services.selectors`.**
- [ ] **Step 3: Update API/import consumers.**
- [ ] **Step 4: Delete page-context-only functions once no runtime import remains.**
- [ ] **Step 5: GREEN CI.**
- [ ] **Step 6: Commit `refactor: move catalog selectors to catalog`.**

### Task 5: Перенести search execution в `services/search-api`

**Files:**
- Modify/create under: `services/search-api/app/`
- Create backend gateway: `backend/catalog/integrations/search_client.py`
- Create gateway tests: `backend/catalog/tests/test_search_client.py`
- Migrate implementation from: `backend/shopfront/searching/`
- Migrate API view from: `backend/shopfront/api/views_search.py`

**Interfaces:**
- Django gateway owns auth/public API compatibility, timeout and response normalization.
- `search-api` owns OpenSearch execution/query rewrite/ranking/facets/suggestions.

- [ ] **Step 1: RED service and gateway contract tests.**
- [ ] **Step 2: Implement service endpoint with explicit short timeout at Django client boundary.**
- [ ] **Step 3: Preserve public search response shape.**
- [ ] **Step 4: Remove duplicated Django search algorithm code.**
- [ ] **Step 5: GREEN CI/service tests.**
- [ ] **Step 6: Commit `refactor: isolate search service execution`.**

### Task 6: Перенести recommendation execution в `services/recommendation-api`

**Files:**
- Modify/create under: `services/recommendation-api/app/`
- Create backend gateway: `backend/catalog/integrations/recommendation_client.py`
- Create gateway tests: `backend/catalog/tests/test_recommendation_client.py`
- Migrate implementation from: `backend/shopfront/recommendation/`
- Migrate API view from: `backend/shopfront/api/views_recommendations.py`

**Interfaces:**
- Recommendation failure degrades to an empty/non-blocking recommendation result.
- Transactional event persistence remains in Django only where Django owns the record.

- [ ] **Step 1: RED tests for success, timeout and degraded response.**
- [ ] **Step 2: Move ranking/inference/policy implementation to service.**
- [ ] **Step 3: Add thin Django client and preserve public response shape.**
- [ ] **Step 4: Move Celery/task references away from `shopfront.*`.**
- [ ] **Step 5: GREEN CI.**
- [ ] **Step 6: Commit `refactor: isolate recommendation service execution`.**

### Task 7: Разнести `shopfront.api` по owning Django apps

**Files:**
- Create/modify `backend/catalog/api/*`
- Create/modify `backend/commerce/api/*`
- Create/modify `backend/orders/api/*`
- Migrate from:
  - `backend/shopfront/api/serializers.py`
  - `backend/shopfront/api/urls.py`
  - `backend/shopfront/api/internal_urls.py`
  - `backend/shopfront/api/views_internal.py`
- Modify: `backend/config/urls.py`

**Interfaces:**
- Public URLs remain stable.
- Internal endpoints get explicit domain ownership instead of generic `shopfront.api`.

- [ ] **Step 1: RED URL-resolution tests asserting no resolved view module starts with `shopfront.`.**
- [ ] **Step 2: Move serializers/views/urls by domain.**
- [ ] **Step 3: Update `config/urls.py` to include domain URL modules only.**
- [ ] **Step 4: GREEN contract tests.**
- [ ] **Step 5: Commit `refactor: move storefront api to domain apps`.**

### Task 8: Удалить Django HTML storefront

**Files:**
- Delete: `backend/shopfront/urls.py`
- Delete storefront HTML views under `backend/shopfront/`
- Delete: `backend/shopfront/templates/`
- Delete: `backend/shopfront/templatetags/`
- Modify: `backend/config/urls.py`
- Modify nginx/Swarm routing under `deploy/` as required.

**Interfaces:**
- `/` is served by Next.js through nginx.
- `/api/`, `/admin/`, `/health/`, `/ready/`, `/metrics` route to Django as appropriate.

- [ ] **Step 1: RED routing test asserting Django does not resolve `/` to a storefront view.**
- [ ] **Step 2: Remove `path("", include("shopfront.urls"))`.**
- [ ] **Step 3: Delete templates/views/templatetags no longer referenced.**
- [ ] **Step 4: Verify nginx routes `/` to frontend service and backend paths to Django.**
- [ ] **Step 5: GREEN CI + Next.js build.**
- [ ] **Step 6: Commit `refactor: remove django html storefront`.**

### Task 9: Удалить `shopfront` Django app и остаточные runtime references

**Files:**
- Modify: `backend/config/settings/base.py`
- Modify: `backend/.coveragerc`
- Modify Celery schedules/tasks/imports referencing `shopfront.*`
- Move any domain models/admin still owned by `shopfront` to their actual owner with explicit migration strategy if model app labels would change.
- Delete remaining `backend/shopfront/` only after repository search is clean.

**Interfaces:**
- No runtime import, `INSTALLED_APPS`, Celery task path or URL include contains `shopfront`.

- [ ] **Step 1: RED repository/static test that fails when runtime `shopfront` references remain.**
- [ ] **Step 2: Resolve every remaining runtime reference by ownership.**
- [ ] **Step 3: Remove `shopfront` from `INSTALLED_APPS`.**
- [ ] **Step 4: Delete package.**
- [ ] **Step 5: Run `makemigrations --check --dry-run`; expected: no migration solely from Python move.**
- [ ] **Step 6: GREEN CI.**
- [ ] **Step 7: Commit `refactor: remove shopfront django app`.**

### Task 10: Production/deploy verification

**Files:**
- Verify/update: `.github/workflows/ci.yml`
- Verify/update: `.github/workflows/deploy.yml`
- Verify/update: `deploy/nginx/nginx.conf`
- Verify/update: Swarm stack files under `deploy/`
- Update: `backend/API.md` and relevant runbook/docs.

**Interfaces:**
- Next.js storefront health and Django API health are independently observable.
- Search/recommendation services have explicit healthchecks/resource/env boundaries.

- [ ] **Step 1: Run Ruff/static checks and full pytest through CI.**
- [ ] **Step 2: Run Django `check --deploy` and migration check.**
- [ ] **Step 3: Run Next.js typecheck/build.**
- [ ] **Step 4: Validate Docker/Swarm config.**
- [ ] **Step 5: Verify repository search has no runtime `shopfront` references.**
- [ ] **Step 6: Verify browser smoke: `/` -> Next.js; `/api/...` -> Django; search/recommendation degradation is non-blocking.**
- [ ] **Step 7: Commit `docs: finalize next-only storefront migration`.**
