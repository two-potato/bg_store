# Storefront Migration Run 1

Дата: 2026-03-27
Роль запуска: architect

## Цель

Запустить первый рабочий проход по поэтапной миграции storefront Servio с Django templates/HTMX на Next.js App Router без поломки backend, admin, bot и SEO.

## Почему это важно

Текущий storefront уже функционально широк, но frontend-контур по-прежнему собран вокруг Django templates, HTMX partials, server-rendered SEO и Django session. Это даёт быстрый SSR, но мешает вынести storefront в отдельный Next.js-контур без специального bridge-слоя.

## Активные роли

Проект уже содержит все шесть рабочих ролей, поэтому новые сущности не создаются:

- architect
- frontend
- uiux
- qa_metrics
- backend
- devops

Ключевые конфигурации ролей:

- `.codex/agents/architect.toml`
- `.codex/agents/frontend.toml`
- `.codex/agents/uiux.toml`
- `.codex/agents/qa_metrics.toml`
- `.codex/agents/backend.toml`
- `.codex/agents/devops.toml`

## Текущее состояние storefront

### Ключевые домены и файлы

- Публичный storefront routing: `backend/shopfront/urls.py`
- Buyer/seller HTML routing: `backend/users/urls_html.py`
- Базовый HTML shell и HTMX runtime: `backend/templates/shopfront/base.html`
- SEO helpers и metadata: `backend/shopfront/views/utils_seo.py`
- `robots.txt` и `sitemap.xml`: `backend/shopfront/views/site_meta.py`
- Catalog API: `backend/catalog/api/views.py`
- Commerce public API: `backend/commerce/api/public.py`
- Orders API: `backend/orders/api/views.py`
- Browser auth HTML: `backend/users/views/auth_html.py`
- Routing/edge layer: `deploy/nginx/nginx.conf`, `deploy/nginx/nginx.dev.conf`

### Что уже видно по архитектуре

- `shopfront` обслуживает home, marketing pages, catalog/search/categories, brands/collections, PDP, vendor/store pages, favorites/compare/lists, cart, checkout и payment flows.
- `users.urls_html` держит buyer account, seller cabinet и browser auth.
- `body` в shopfront уже работает через глобальный `hx-boost`, поэтому HTMX встроен в базовую модель навигации, а не только в отдельные виджеты.
- SEO централизовано в Django: `title`, `description`, `canonical`, `robots`, `OG`, `Twitter`, `JSON-LD`, `robots.txt`, `sitemap.xml`.
- Search и recommendations уже вынесены в серверные подсистемы и сервисы; их нельзя переносить во frontend.

## Первый вывод по ролям

### architect

- Идём только волнами: `foundation -> public storefront -> auth/cart/account -> checkout -> seller surfaces`.
- Используем strangler pattern через route-level proxy на одном домене.
- Django/DRF остаётся source of truth для бизнес-логики, checkout, orders, auth, seller flows.

### frontend

- Целевой frontend должен появиться как отдельный Next.js App Router application с route groups для marketing/public discovery, auth/account, checkout и seller surfaces.
- Первыми нужно переносить read-heavy SSR surfaces, а не HTMX-heavy flows.
- Home, static pages, catalog/search/category/brand/collection дают лучший баланс между бизнес-ценностью и migration risk.

### backend

- Текущие DRF endpoints покрывают только часть storefront-потребностей.
- Уже есть базовые read APIs для catalog и часть authenticated APIs для commerce/orders.
- Критические пробелы для Next storefront: browser auth contract, cart API, полноценный catalog/search contract, PDP contract, checkout bootstrap/submit/payment contract.

### uiux

- Foundation нужно строить от единого storefront language, а не от локального порта старых шаблонов.
- На первых волнах важно удержать mobile-first information architecture для home, catalog, PDP и search.
- UX-heavy seller surfaces и checkout нельзя переносить до стабилизации контрактов и состояний.

### qa_metrics

- Нужен route parity matrix между Django и Next по status code, metadata и redirect behavior.
- Критические сценарии будущих quality gates: home, catalog, search, PDP, cart, auth, checkout, account.
- Нужно сохранить parity по analytics/observability: search feedback, recommendation feedback, checkout events, browser error monitoring.

### devops

- Edge routing уже централизован в `nginx`, значит route-level migration реалистична без смены домена.
- Нужен явный rollback path: каждый маршрут должен откатываться обратно на Django через config switch.
- Отдельный frontend runtime придётся встроить в Docker/CI/CD без ломки текущего backend-first deploy.

## Стартовая последовательность волн

### Wave 1. Foundation

- Поднять отдельный Next.js storefront runtime.
- Ввести route switch на уровне `nginx`.
- Зафиксировать URL parity и правила ownership маршрутов.
- Сохранить Django как default renderer для всех путей.

### Wave 2. Public storefront

Переносим сначала:

- `/`
- `/about/`
- `/buyers/`
- `/suppliers/`
- `/delivery/`
- `/payment/`
- `/returns/`
- `/contacts/`
- `/faq/`
- `/brands/`
- `/collections/`
- `/promotions/`
- `/blog/`

Потом:

- `/catalog/`
- `/search/`
- `/categories/<path>/`
- `/brands/<slug>/`
- `/collections/<slug>/`
- `/products/<slug>/`
- `/vendors/<slug>/`

### Wave 3. Auth / Cart / Account

- `/account/login/`
- `/account/register/`
- `/account/confirm-email/`
- `/cart/`
- `/favorites/`
- `/compare/`
- `/lists/**`
- `/saved-searches/`
- buyer-side `/account/**`

### Wave 4. Checkout

- `/checkout/`
- `/checkout/success/**`
- `/payments/**`
- guest checkout flows

### Wave 5. Seller surfaces

- `/account/seller/**`

## Стартовые API требования

### Уже частично пригодно

- `GET /api/catalog/brands/`
- `GET /api/catalog/series/`
- `GET /api/catalog/categories/`
- `GET /api/catalog/products/`
- `GET/POST/... /api/commerce/delivery-addresses/`
- lookup endpoints в `commerce`
- `GET/POST /api/orders/`
- `GET /api/users/me/`
- analytics ingest endpoints из `shopfront`

### Нужно добавить или усилить

- browser auth/session contract для web storefront
- catalog/search API с `q`, facets, sort, pagination, seller facets, price stats, rewrite/provider metadata
- PDP API по `slug` с offers, seller data, breadcrumbs, reviews summary, recommendations
- live search JSON contract
- cart API
- checkout bootstrap/preview/submit/payment contract
- buyer account API для orders, memberships, preferences, notifications

## Главные риски

- SEO regression на canonical, robots, JSON-LD, sitemap и legacy redirects
- расхождение state между Django session cart и новым frontend state
- browser auth gap между HTML session flows и DRF JWT-oriented APIs
- деградация search relevance при попытке вынести query logic во frontend
- потеря analytics и observability parity
- слишком ранний перенос checkout или seller surfaces

## Как проверяем

- route parity matrix
- metadata parity matrix
- OpenAPI/schema diff для новых контрактов
- Playwright smoke на home/catalog/PDP/cart/auth/checkout/account
- regression набор поисковых запросов
- Sentry/PostHog parity
- rollback rehearsal на уровне `nginx`

## Что сознательно НЕ делаем в этом запуске

- не трогаем `admin`
- не трогаем `bot`
- не переписываем всё сразу
- не переносим бизнес-логику в Next.js
- не начинаем с checkout
- не начинаем с seller surfaces

## Следующий исполнимый шаг

Подготовить `foundation packet`:

1. frontend: target `app/` structure и route groups
2. backend: storefront API gap list в формате `ready / needs work / blocker`
3. devops: схема route switching и rollback
4. qa_metrics: стартовый parity gate
5. architect: единая migration board по волнам

## Актуальный backlog

Текущий рабочий backlog до полного покрытия storefront зафиксирован отдельно:

- `docs/STOREFRONT_NEXT_BACKLOG.md`
