# Storefront Next Backlog

Дата: 2026-03-27
Статус: рабочий backlog для доведения storefront migration до полного покрытия пользовательского web-контура

## Цель

Зафиксировать всё, что осталось перенести из Django templates/HTMX в Next.js App Router storefront, не ломая backend, admin, bot, SEO, analytics и release safety.

## Что уже на Next

- public shell
- home
- marketing pages
- catalog
- product detail page

## Что остаётся в Django как source of truth

- бизнес-логика
- auth и права доступа
- cart, checkout, orders
- seller-domain
- search orchestration
- recommendations orchestration
- admin
- bot

## Бэклог по волнам

### Wave 2. Public storefront completion

#### Discovery и navigation surfaces

- `/search/`
- `/search/live/` как typed JSON bridge для нового search box
- `/categories/<path>/`
- `/brands/<slug>/`
- `/collections/<slug>/`
- `/vendors/<slug>/`
- `vendors` listing
- `blog` detail pages, если появятся slug routes

#### PDP adjacent surfaces

- reviews summary
- review CRUD flows
- review comments
- review voting
- product questions
- recommendation sections на PDP
- offer ladder
- trust badges и seller/store facts из server service

#### API и bridge

- catalog/search contract с `q`, `sort`, pagination, facets, suggestions, zero-results recovery
- live search contract без HTML partial dependence
- PDP contract по `slug` с reviews, related sections, seller/store surfaces, offer ladder

#### SEO и observability

- metadata parity для search/category/brand/collection/vendor pages
- canonical/noindex strategy для filter/search pages
- JSON-LD parity
- search analytics parity
- recommendation feedback parity

### Wave 3. Auth / Cart / Account

#### Browser auth

- `/account/login/`
- `/account/register/`
- `/account/confirm-email/`
- logout
- password reset flows
- browser session bootstrap
- csrf/session bridge для form и mutation flows
- social login handoff, если используется

#### Discovery persistence

- `/favorites/`
- `/compare/`
- `/lists/`
- `/lists/<id>/`
- `/lists/shared/<token>/`
- `/saved-searches/`
- subscription toggle

#### Cart

- cart badge
- cart drawer/panel
- `/cart/`
- add/update/remove/clear
- buy-now flow
- merge cart after login
- empty/loading/error states

#### Buyer account

- `/account/`
- `/account/orders/`
- `/account/addresses/`
- `/account/legal-entities/`
- `/account/comments/`
- reorder, saved lists from order

#### API и bridge

- web auth/session contract
- cart REST contract
- favorites/compare/lists/saved-searches contract
- buyer account contract
- address/legal entity contract cleanup

#### Риски

- session drift между Django и Next
- потеря CSRF correctness
- потеря cart badge parity
- broken redirect after login/logout

### Wave 4. Checkout

#### Buyer checkout

- `/checkout/`
- checkout summary
- address selection
- delivery options
- payment method selection
- submit
- validation and error surfaces

#### Guest flows

- guest checkout bootstrap
- guest order success page
- guest payment retry/status

#### Payments

- `/payments/fake/**`
- `/payments/online/**`
- payment status polling and confirmation states

#### API и bridge

- checkout bootstrap
- totals preview
- delivery/payment choices
- coupon/promo validation
- order submit
- payment init/status/retry

#### Quality requirements

- no duplicated pricing logic in frontend
- strict analytics on each step
- rollback-ready edge switch per route family

### Wave 5. Seller surfaces

#### Seller storefront and cabinet

- `/account/seller/`
- seller products
- add/edit product flows
- offers
- warehouse/inventory flows
- seller orders
- moderation states
- seller analytics surfaces

#### Public seller pages

- store detail
- seller profile
- store reviews

#### API и bridge

- seller cabinet API coverage
- product management mutations
- moderation and media upload contract
- seller analytics contract

#### Риски

- highest release risk
- operational regressions
- hidden dependencies on server-rendered HTML and session context

## Поперечный backlog по системам

### UI system

- search bar
- filter panel
- sort control
- compare tray
- cart line
- checkout summary
- account navigation
- seller tables
- skeleton states
- empty/error/success states

### API contract discipline

- OpenAPI completeness for storefront routes
- typed error format
- rate-limit awareness for browser surfaces
- pagination normalization
- file upload contract for seller/media flows

### Performance

- image policy for catalog, PDP, brands, collections
- streaming and segment-level loading
- caching strategy per route family
- mobile layout stabilization

### Analytics / observability

- PostHog parity
- Sentry parity
- search-feedback parity
- recommendation-feedback parity
- checkout funnel parity
- seller action telemetry

## Affected files and domains

### Frontend

- `frontend/app/**`
- `frontend/components/**`
- `frontend/lib/**`

### Backend

- `backend/shopfront/views/**`
- `backend/shopfront/urls.py`
- `backend/catalog/api/**`
- `backend/orders/api/**`
- `backend/users/views/**`
- `backend/users/urls_html.py`
- `backend/commerce/api/**`

### Edge / delivery

- `deploy/nginx/**`
- `docker-compose*.yml`
- `.github/workflows/**`

## Definition of Ready для каждого блока

- понятен route ownership
- есть contract gap list
- определён rollback path
- определены SEO последствия
- определены analytics/observability последствия

## Definition of Done для каждого блока

- route живёт на Next и не ломает backend domain logic
- контракты стабилизированы и задокументированы
- учтены mobile, empty, loading, error, success states
- есть ручной сценарий проверки
- есть release-safe rollback

## Ручные сценарии проверки

1. Home -> catalog -> PDP -> brand/category navigation.
2. Search -> suggestion -> zero-results recovery.
3. Login -> favorites/lists/cart/account.
4. Cart -> checkout -> payment -> success.
5. Buyer account -> order history -> reorder.
6. Seller login -> cabinet -> offer/product flows.

## Rollback approach

- любой маршрут переключается обратно на Django на уровне `nginx`
- backend contracts остаются additive и не ломают старых клиентов
- rollout идёт route family by route family, а не broad rewrite

## Явно вне scope

- `admin`
- `bot`
- перенос доменной логики в Next
