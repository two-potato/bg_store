# API Platform Plan: FastAPI Search + Recommendation Services

Дата: 2026-03-28  
Роль: `architect`

## 1. Цель

Пересобрать API-платформу Servio так, чтобы:

- Django/DRF осталось source of truth для доменной логики и публичного platform API
- search и recommendations были вынесены в отдельные FastAPI-сервисы
- переход был контрактным, поэтапным и обратимым
- storefront, Next BFF и seller/account/checkout не ломались в процессе

Итоговая целевая модель:

- `Django/DRF` — доменные данные, auth, orders, commerce, checkout, storefront bridge, публичные API
- `FastAPI search service` — query processing, retrieval, suggestions, facets, ranking metadata
- `FastAPI recommendation service` — candidate generation, ranking, personalization, recommendation metadata

## 2. Почему это важно

Текущий контур уже показывает естественную точку разделения:

- в `shopfront/searching/*` собрана отдельная search-orchestration логика
- в `shopfront/recommendation/*` собрана отдельная recommendation-orchestration логика
- обе зоны имеют собственные observability helpers, event handling, ranking logic и operational hot spots

Дальше держать их глубоко внутри Django-монолита становится всё менее выгодно:

- search и reco имеют свой latency profile
- требуют отдельного жизненного цикла моделей, индексов и ранжирования
- нуждаются в независимой observability и capacity tuning
- будут расти быстрее, чем остальной CRUD/API слой

При этом выносить всё из Django нельзя, потому что:

- cart / checkout / orders / auth / legal entity access остаются доменной логикой платформы
- session, permissions и transactional correctness завязаны на Django-модель
- storefront и Next migration уже опираются на bridge и платформенные API

## 3. Текущая карта API

## 3.1. Текущая публичная API-карта

Корневой роутинг:

- `/api/users/*`
- `/api/commerce/*`
- `/api/catalog/*`
- `/api/orders/*`
- `/api/schema/`, `/api/docs/`, `/api/redoc/` через `drf-spectacular`
- storefront/HTML и bridge endpoints через `shopfront.urls`

### `users`

- `GET /api/users/me/`
- `POST /api/users/auth/tg-webapp/`

Назначение:

- профиль текущего пользователя
- Telegram WebApp auth

### `commerce`

- `POST /api/commerce/check-inn/`
- `GET /api/commerce/lookup/party/`
- `GET /api/commerce/lookup/party_preview/`
- `GET /api/commerce/lookup/revgeo/`
- `GET /api/commerce/lookup/bank/`
- `POST /api/commerce/membership-requests/`
- CRUD `/api/commerce/delivery-addresses/`

Назначение:

- legal entities
- membership requests
- addresses
- external lookups

### `catalog`

- `GET /api/catalog/brands/`
- `GET /api/catalog/series/`
- `GET /api/catalog/categories/`
- `GET /api/catalog/collections/`
- `GET /api/catalog/products/`
- `GET /api/catalog/products/{id}/`

Назначение:

- публичный catalog API
- discovery filters и product lookup
- базовая search/discovery интеграция уже в `ProductViewSet`

### `orders`

- `GET /api/orders/`
- `GET /api/orders/{id}/`
- `POST /api/orders/`
- `POST /api/orders/{id}/approve/`
- `POST /api/orders/{id}/reject/`

Назначение:

- order lifecycle
- approval flow
- downstream checkout/payments context

### `shopfront bridge` и storefront-side JSON/BFF

- `/api/storefront/session/bootstrap/`
- `/api/storefront/cart/*`
- `/api/storefront/orders/{id}/`
- `/api/storefront/orders/{id}/reorder/`
- `/api/storefront/account/*`
- `/api/storefront/tools/*`
- `/api/storefront/analytics/ingest/`

Назначение:

- Next storefront bridge
- browser/session-aware BFF surface
- same-origin buyer/cart/account tooling

### storefront analytics ingest

- `POST /analytics/search-feedback/`
- `POST /analytics/recommendation-feedback/`

Назначение:

- first-party feedback signals
- attribution memory
- observability and conversion linkage

## 3.2. Внутренние search/recommendation зоны уже существуют

### Search

- `backend/shopfront/searching/service.py`
- `backend/shopfront/searching/backend.py`
- `backend/shopfront/searching/attribution.py`
- `backend/shopfront/searching/observability.py`

Там уже есть:

- query normalization
- synonym/query rewrite
- OpenSearch provider
- DB fallback provider
- live search bundle
- search attribution
- Prometheus/log observability

### Recommendations

- `backend/shopfront/recommendation/service.py`
- `backend/shopfront/recommendation/ranker.py`
- `backend/shopfront/recommendation/selectors.py`
- `backend/shopfront/recommendation/feature_store.py`
- `backend/shopfront/recommendation/observability.py`
- `backend/shopfront/recommendation/events.py`

Там уже есть:

- candidate collection
- heuristic/ML ranking
- personalized recommendations
- feature-store usage
- impression/click attribution payloads
- Prometheus/log observability

Вывод: выделение в FastAPI не начинается “с нуля”; логические границы уже подготовлены внутри монолита.

## 4. Что остаётся в Django/DRF

В Django/DRF должны остаться:

- auth и session
- permissions / RBAC
- users / profiles / seller access
- commerce / legal entities / addresses
- catalog как canonical source of truth
- orders / checkout / payments / claims / support
- cart и browser-aware storefront bridge
- public API gateway layer
- storefront HTML compatibility
- analytics ingress на границе браузера
- session-based attribution and order linkage
- API docs aggregator entrypoint

Принцип:

- Django остаётся владельцем доменной истины
- Django не отдаёт владение transaction logic ни search, ни reco сервисам
- Django/BFF решает, кто может видеть какие данные и какие поля сериализуются наружу

## 5. Что уезжает в FastAPI search service

В search service должны уехать:

- query normalization / rewrite pipeline
- lexical + semantic retrieval orchestration
- OpenSearch query execution
- autocomplete / suggestions
- facets / aggregations
- ranking metadata
- provider fallback policy
- search health / readiness / internal metrics

Целевая зона ответственности search service:

- принять внутренний query contract
- вернуть ranked product ids и search metadata
- не сериализовать полный product detail как platform source of truth

Рекомендуемый внутренний контракт search service:

- `POST /internal/search/query`
- `POST /internal/search/live`
- `POST /internal/search/suggest`
- `POST /internal/search/facets`
- `GET /internal/search/health`
- `GET /internal/search/ready`
- `GET /internal/search/openapi.json`

Что search service не должен брать на себя:

- auth
- session
- cart/checkout logic
- canonical product serialization
- permission checks
- order attribution finalization

Рекомендуемый response shape:

- `product_ids`
- `facets`
- `suggestions`
- `countries`
- `provider`
- `effective_query`
- `rewritten_query`
- `rewrite_kind`
- `query_variants`
- `duration_ms`

## 6. Что уезжает в FastAPI recommendation service

В recommendation service должны уехать:

- candidate retrieval
- materialized recommendation sets
- personalized ranking
- heuristic + ML scoring
- recommendation explainability metadata
- feature lookup / recommendation feature-store serving
- recommendation experiment / variant serving
- recommendation health / readiness / model version exposure

Целевая зона ответственности recommendation service:

- принять normalized context от Django/BFF
- вернуть ranked `product_ids` и explanation metadata
- не владеть cart/order/user transactions

Рекомендуемый внутренний контракт recommendation service:

- `POST /internal/recommendations/home`
- `POST /internal/recommendations/pdp`
- `POST /internal/recommendations/cart`
- `POST /internal/recommendations/reorder`
- `POST /internal/recommendations/seller`
- `POST /internal/recommendations/rank`
- `POST /internal/recommendations/events` для async/offline ingest
- `GET /internal/recommendations/health`
- `GET /internal/recommendations/ready`
- `GET /internal/recommendations/openapi.json`

Рекомендуемый response shape:

- `product_ids`
- `surface`
- `source`
- `variant`
- `strategy`
- `model_version`
- `scores_by_product`
- `reason_codes_by_product`
- `candidate_sources_by_product`
- `trace`

Что recommendation service не должен брать на себя:

- favorites/saved lists ownership
- session storage
- order creation
- product canonical serialization
- storefront HTML/Next response assembly

## 7. Как связать это через contracts и observability

## 7.1. Контрактная схема

Связка должна идти так:

1. Браузер / Next вызывает Django/DRF или storefront bridge.
2. Django/BFF собирает:
   - user/session context
   - permission scope
   - catalog filters
   - surface name
   - request id / trace id
3. Django вызывает внутренний FastAPI service по private contract.
4. FastAPI возвращает `ids + metadata`.
5. Django гидрирует canonical product data из собственного catalog layer.
6. Django собирает публичный response.

Ключевой принцип:

- FastAPI services отдают ranking/retrieval result
- Django остаётся public contract owner

## 7.2. Contract discipline

Для обоих сервисов обязательны:

- versioned request/response schemas
- Pydantic/OpenAPI schemas
- таймауты и circuit breakers на стороне Django caller
- fallback policy
- request id propagation
- explicit error taxonomy

Рекомендуемые transport headers:

- `X-Request-ID`
- `traceparent`
- `X-Internal-Token`
- `X-Caller-Service`
- `X-User-ID` только если это допустимо по privacy policy

## 7.3. Observability

Нужно связать:

- Prometheus metrics
- Loki/structured logs
- Sentry traces/errors
- first-party analytics ingest

Минимальный observability contract:

- единый `request_id`
- единый `surface`
- единый `provider`/`source`
- `variant`
- `strategy`
- latency
- outcome
- zero-results / partial-results
- model_version

Public ingest остаётся в Django:

- browser events принимаются на same-origin endpoints
- Django сохраняет session attribution
- дальше либо синхронно, либо через Celery/outbox форвардит нормализованные events в search/reco services для offline learning и dashboards

## 8. Как выглядит Swagger/OpenAPI карта

Целевая карта OpenAPI должна стать трёхслойной.

### 8.1. Публичная платформа

Остаётся в Django:

- `/api/schema/`
- `/api/docs/`
- `/api/redoc/`

Содержит:

- `users`
- `commerce`
- `catalog`
- `orders`
- `storefront bridge`

### 8.2. Internal Search OpenAPI

Отдельно у search service:

- `/internal/search/openapi.json`
- `/internal/search/docs`

Содержит:

- query
- live
- suggest
- facets
- health / ready

### 8.3. Internal Recommendation OpenAPI

Отдельно у recommendation service:

- `/internal/recommendations/openapi.json`
- `/internal/recommendations/docs`

Содержит:

- home/pdp/cart/reorder/seller surfaces
- generic rank endpoint
- event ingest / model info / health

### 8.4. Aggregated platform map

Для эксплуатации нужен index-document:

- `Public Platform API`
- `Internal Search API`
- `Internal Recommendation API`

Важно:

- публичная документация не должна случайно открывать internal service contracts наружу
- internal contracts должны быть отдельным operational layer

## 9. Риски

### 1. Ложный микросервисный выигрыш

Риск: вынести код физически, но сохранить сильную синхронную связанность.  
Последствие: операционная сложность вырастет, а выигрыш не появится.

### 2. Размывание source of truth

Риск: FastAPI начнёт сериализовать product truth или принимать доменные решения.  
Последствие: рассинхрон каталога и storefront.

### 3. Потеря attribution и observability

Риск: search/reco serving уедет, а request/event связность потеряется.  
Последствие: деградация relevance без объяснимости.

### 4. Ломка storefront latency

Риск: добавить два новых hop без timeout/fallback discipline.  
Последствие: каталог и PDP станут медленнее.

### 5. Преждевременный cutover

Риск: перевести traffic до shadow mode и parity metrics.  
Последствие: ухудшение search relevance и conversion.

### 6. Неправильная data dependency

Риск: FastAPI services будут читать transactional Django DB напрямую как основной рабочий интерфейс.  
Последствие: сильная связность и проблемы масштабирования.

## 10. Этапы внедрения

### Этап 0. Contract-first audit

- зафиксировать текущие search/reco boundaries
- описать internal request/response schemas
- определить parity metrics

### Этап 1. Вынести interfaces внутри монолита

- оставить существующий Python code в репо
- отделить caller contracts от view logic
- подготовить adapter layer `Django -> internal service`

### Этап 2. FastAPI search service в shadow mode

- поднять search service
- подключить OpenSearch access
- дублировать search requests из Django в shadow mode
- сравнивать:
  - ids
  - suggestions
  - zero-results rate
  - latency

### Этап 3. Search cutover

- перевести catalog/search/live-search на search service
- сохранить Django fallback
- наблюдать parity и rollback path

### Этап 4. FastAPI recommendation service в shadow mode

- поднять reco service
- вынести candidate/ranking path
- дублировать recommendation selection requests
- сравнивать selected ids, scores, variants, attributed orders

### Этап 5. Recommendation cutover

- перевести recommendation surfaces на internal reco service
- сохранить rollback в Django implementation
- контролировать conversion and attribution parity

### Этап 6. Event and learning loop hardening

- нормализовать event ingest forwarding
- подключить offline feature refresh / model update contracts
- сделать dashboards по search/reco quality

### Этап 7. OpenAPI + operations hardening

- развести public/internal docs
- закрепить health/ready/error taxonomy
- зафиксировать SLO / alerts / rollback runbooks

## Короткий вывод

Правильная целевая модель для Servio:

- `Django/DRF` остаётся platform core и public API owner
- `FastAPI search service` становится retrieval/ranking engine для search
- `FastAPI recommendation service` становится retrieval/ranking engine для recommendations

Вынос должен быть не “переписыванием ради микросервисов”, а контрактным отделением двух уже сформированных подсистем с сохранением:

- Django source of truth
- storefront BFF boundaries
- observability
- rollback path
