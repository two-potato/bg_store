# Search/Recommendations Contract Slice (Backlog 044/046)

Дата: 2026-03-28  
Роль: backend

## 1) API audit и gap-list

### Что было до среза

- В backend уже были:
  - `GET /api/catalog/products/` с параметром `q` и мета-хедерами поиска.
  - HTML/HTMX search/recommendation surfaces в `shopfront` (catalog/live-search/PDP/cart/checkout).
  - доменная логика поиска и рекомендаций в:
    - `backend/shopfront/searching/*`
    - `backend/shopfront/recommendation/*`
- Чего не хватало:
  - стабильного page-level контрактного API для Next storefront по search/recommendations.
  - явного bridge-режима `django-inline` vs external service.
  - отражения search/reco сервисной карты в Swagger/OpenAPI docs.

### Gap-list (закрываемый этим срезом)

1. Нет единого `/api/search/*` contract layer.  
2. Нет единого `/api/recommendations/*` contract layer.  
3. Нет runtime bridge-переключателя `django-inline`/`service` для search/reco.  
4. Нет чёткой doc-карты: что external/public, а что internal/service-only.  
5. FastAPI search/reco как отдельные сервисы не были оформлены отдельными пакетами.

## 2) Swagger/OpenAPI map

### Django OpenAPI (external/public API)

- Schema: `/api/schema/`
- Swagger: `/api/docs/`
- Redoc: `/api/redoc/`

Новые публичные contract endpoints:

- `GET /api/search/query/`
- `GET /api/search/suggestions/`
- `GET /api/recommendations/home/`
- `GET /api/recommendations/products/{product_id}/`
- `GET /api/recommendations/products/{product_id}/sections/{section}/`
- `POST /api/recommendations/cart/`
- `POST /api/recommendations/checkout/`
- `GET /api/recommendations/reorder/`
- `GET /api/recommendations/search-recovery/`

Новые OpenAPI tags:

- `Search`
- `Recommendations`

### FastAPI service OpenAPI (internal/service-only)

- Search service:
  - OpenAPI: `http://localhost:18110/openapi.json`
  - Swagger: `http://localhost:18110/docs`
- Recommendation service:
  - OpenAPI: `http://localhost:18111/openapi.json`
  - Swagger: `http://localhost:18111/docs`

## 3) Первый рабочий internal contract для search/recommendations

Добавлен контрактный слой в Django (DRF), который отдает единый response envelope для storefront:

- search contract:
  - query/effective_query/rewritten_query/rewrite_kind/provider
  - product cards
  - suggestions/corrections/countries
  - facets (brands/categories/availability/price)

- recommendation contract:
  - surface/variant/sections[]
  - section: key/title/source/strategy/tracking_payload/products[]

Это первый стабильный transport-contract для миграции Next storefront без переноса бизнес-логики из Django.

## 4) Backend bridge: `django-inline` / `service`

### Search bridge

- `SEARCH_SERVICE_MODE=django-inline|fastapi`
- `SEARCH_SERVICE_URL=http://search-api:8010`
- `SEARCH_SERVICE_TIMEOUT_SECONDS=0.8`

Поведение:

- `django-inline` (default): используется текущая доменная логика Django.
- `fastapi`: запрос уходит в search FastAPI service.
- если FastAPI недоступен/ошибочен: автоматический fallback на Django (`source=django-inline-fallback`).

### Recommendations bridge

- `RECOMMENDATION_SERVICE_MODE=django-inline|fastapi`
- `RECOMMENDATION_SERVICE_URL=http://recommendation-api:8011`
- `RECOMMENDATION_SERVICE_TIMEOUT_SECONDS=0.8`

Поведение аналогично: service-first в режиме `fastapi` и безопасный fallback на Django.

## 5) Границы API: external/public vs internal/service-only

### External/Public (контракт для storefront и интеграций)

- Только Django DRF endpoints:
  - `/api/search/*`
  - `/api/recommendations/*`
  - и уже существующие `/api/catalog/*`, `/api/orders/*`, `/api/commerce/*`, `/api/users/*`

### Internal/Service-only

- FastAPI сервисы:
  - `search-api` (`/v1/search/*`)
  - `recommendation-api` (`/v1/recommendations/*`)
- Django internal inline contracts (token-protected):
  - `/api/internal/search/*`
  - `/api/internal/recommendations/*`
- Эти маршруты предназначены для service-to-service bridge слоя.
- Source-of-truth бизнес-логики остаётся Django/DRF.

## Update 049: parity hardening

В рамках parity hardening:

1. FastAPI сервисы переведены на проксирование Django internal inline contracts, а не на эвристики по catalog API.  
2. Добавлены source markers для прозрачности:
   - `source` (режим ответа для публичного API),
   - `service_source` (какой service обработал запрос),
   - `engine_source` (какой backend engine фактически построил payload).  
3. Добавлен `user_id` passthrough для внутренних recommendation contracts, чтобы уменьшить расхождение персональных surfaces между режимами.

## Риски и следующий шаг

### Риски текущего среза

1. FastAPI сервисы в этом шаге дают bootstrap-эвристику (не полная parity с Django recommendation engine).  
2. В режиме `fastapi` качество выдачи зависит от зрелости external service; mitigation — fallback на Django.  
3. Нужна отдельная devops-волна для production routing, SLO и rollback-процедур platform-services.

### Следующий шаг (после этого среза)

1. Довести parity сервисов по ranking/facets/attribution контрактам.  
2. Добавить contract-tests между Django bridge и FastAPI payload schema.  
3. Включить staged rollout `fastapi` mode по процентам/поверхностям с метриками качества.
