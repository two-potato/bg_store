# FastAPI Search/Recommendations Parity QA Gates

Дата: 2026-03-28  
Роль: `qa_metrics`

## 1. Цель

Зафиксировать quality gates для сравнения `django-inline` vs `fastapi` по `search/recommendations`, чтобы cutover:

- не ломал storefront contract
- не ухудшал relevance, zero-results и conversion
- не терял attribution и observability
- был обратимым и операционно контролируемым

Документ опирается на текущие контракты и telemetry в:

- `backend/shopfront/searching/contracts.py`
- `backend/shopfront/recommendation/contracts.py`
- `backend/shopfront/searching/observability.py`
- `backend/shopfront/recommendation/observability.py`
- `deploy/prometheus/search_rules.yml`
- `deploy/prometheus/alerts.yml`
- `docs/API_PLATFORM_PLAN_FASTAPI_SEARCH_RECO_RU.md`
- `docs/SEARCH_RECO_CONTRACT_SLICE_044_046.md`

## 2. Честный текущий статус

### Что уже есть

- стабильный публичный contract layer: `/api/search/*`, `/api/recommendations/*`
- bridge-режимы `django-inline`, `fastapi`, `django-inline-fallback`
- search-specific Prometheus rules и базовые alerts
- first-party analytics ingest для `search-feedback` и `recommendation-feedback`
- service health/readiness endpoints у `search-api` и `recommendation-api`

### Что пока недостаточно зрелое

- `search-api` пока работает как `backend-catalog-bridge`, а не как полноценный search engine parity-уровня
- `recommendation-api` пока отдаёт `fastapi_bootstrap`-эвристику, а не parity с текущим Django recommendation engine
- для recommendations нет такого же зрелого alerting/dashboards слоя, как для search
- нет автоматизированного shadow diff слоя между `django-inline` и `fastapi`

### Вывод

На текущем состоянии можно запускать `shadow/canary`, но нельзя делать полный cutover.  
`No-go` до выполнения backlog `049/050`: ranking, facets, rewrite, attribution и recommendation quality ещё не доведены до parity.

## 3. Что сравниваем в payload

Сравнение должно идти в трёх слоях:

1. `Schema parity`  
   Поля есть, типы стабильны, обязательные ключи не пропадают.
2. `Semantic parity`  
   Смысл ответа сохраняется: те же surfaces, section keys, допустимые rewrite/facet semantics, валидные tracking payloads.
3. `Quality parity`  
   Результаты не деградируют по relevance, zero-results, CTR, add-to-cart и attributed orders.

### 3.1. Поля, которые сравниваем строго по схеме

#### Search query: `GET /api/search/query/`

- `ok`
- `query`
- `source`
- `service_source`
- `engine_source`
- `effective_query`
- `rewritten_query`
- `rewrite_kind`
- `provider`
- `product_ids[]`
- `products[]`
- `suggestions[]`
- `corrections[]`
- `countries[]`
- `facets.brands[]`
- `facets.categories[]`
- `facets.availability.in_stock`
- `facets.availability.out_of_stock`
- `facets.price.min`
- `facets.price.max`
- `service_error`

#### Search suggestions: `GET /api/search/suggestions/`

- `ok`
- `query`
- `source`
- `service_source`
- `engine_source`
- `provider`
- `effective_query`
- `rewritten_query`
- `rewrite_kind`
- `suggestions[]`
- `corrections[]`
- `countries[]`
- `service_error`

#### Recommendations: все `/api/recommendations/*`

- `ok`
- `source`
- `service_source`
- `engine_source`
- `surface`
- `variant`
- `sections[]`
- `sections[].key`
- `sections[].title`
- `sections[].source`
- `sections[].strategy`
- `sections[].tracking_payload`
- `sections[].products[]`
- `service_error`
- `error`

#### Product card внутри search/recommendations

- `id`
- `slug`
- `sku`
- `name`
- `image_url`
- `price`
- `stock_qty`
- `min_order_qty`
- `brand_name`
- `seller_name`
- `rating_avg`
- `rating_count`
- `is_new`
- `is_promo`

### 3.2. Поля, которые должны совпадать строго

- `ok`
- обязательные top-level keys
- типы всех полей
- `surface`
- `sections[].key`
- отсутствие дубликатов в `product_ids[]`
- соответствие `product_ids[]` и `products[].id`
- ограничение `limit`
- корректные коды ошибок:
  - `401` для `/api/recommendations/reorder/` без auth
  - `404` для PDP recommendations при несуществующем `product_id`

### 3.3. Поля, где допустима не абсолютная идентичность, а parity-метрика

#### Search

- `effective_query`
- `rewritten_query`
- `rewrite_kind`
- `provider`
- порядок `product_ids[]`
- `suggestions[]`
- `corrections[]`
- `countries[]`
- facet counts и facet ordering

#### Recommendations

- `variant`
- `sections[].title`
- `sections[].source`
- `sections[].strategy`
- `sections[].tracking_payload`
- порядок продуктов внутри секций

### 3.4. Правила семантического сравнения

#### Search

- Top-10 overlap по `product_ids` между `django-inline` и `fastapi`: не ниже `0.70`
- Top-5 overlap по `product_ids`: не ниже `0.60`
- Совпадение `rewrite_kind`: не ниже `95%` на golden query set
- Совпадение `effective_query`: не ниже `95%`
- Непустой `provider` в `100%` успешных ответов
- `facets.availability` и `facets.price` не должны расходиться более чем на `5%`
- Top facet labels по `brands/categories`: overlap не ниже `0.80`

#### Recommendations

- Наличие обязательных секций по surface:
  - `home`: `recommended_for_you`, `recently_viewed`, `watchlist`, `popular`, `replenishment`
  - `pdp`: `similar_products`, `accessory_products`, `substitute_products`
  - `cart|checkout`: `cross_sell`
  - `reorder`: `reorder`
  - `catalog` recovery: `search_recovery`
- Доля пустых обязательных секций в `fastapi` не выше `django-inline + 5pp`
- Top-N overlap по продуктам в обязательной секции: не ниже `0.50` для bootstrap-этапа, целевой порог `0.70`
- `tracking_payload` должен присутствовать и быть не пустым везде, где он есть в `django-inline`; допустимая потеря на bootstrap-этапе не более `2%`, для full cutover `0%`

## 4. SLA, latency и quality metrics

## 4.1. Обязательные request SLI/SLO

### Search public contract

- availability: `>= 99.9%`
- fallback rate `fastapi -> django-inline-fallback`: `< 1%` за `15m`, `< 0.1%` за `24h`
- `p95 latency`:
  - `/api/search/query/` `<= 0.8s`
  - `/api/search/suggestions/` `<= 0.35s`
- `p99 latency`:
  - `/api/search/query/` `<= 1.2s`
  - `/api/search/suggestions/` `<= 0.6s`

### Recommendations public contract

- availability: `>= 99.9%`
- fallback rate `fastapi -> django-inline-fallback`: `< 1%` за `15m`, `< 0.1%` за `24h`
- `p95 latency`:
  - `/api/recommendations/home/` `<= 0.7s`
  - `/api/recommendations/products/*` `<= 0.8s`
  - `/api/recommendations/cart/` `<= 0.7s`
  - `/api/recommendations/checkout/` `<= 0.7s`
  - `/api/recommendations/reorder/` `<= 0.8s`
- `p99 latency` для reco surfaces: `<= 1.2s`

### Internal FastAPI services

- `/health`: `200`
- `/ready`: `200`
- `p95 latency` на service-to-service calls: `<= 250ms` на steady state
- transport errors/timeouts: `< 0.5%`

## 4.2. Search quality metrics, которые блокируют cutover

- `zero_result_share`
  - абсолютный потолок: `< 25%`
  - drift против `django-inline`: не хуже чем `+3pp`
- `click-through rate` по `search_result_click / search`
  - падение против baseline: не более `10%`
- `attributed_orders_rate`
  - падение против baseline: не более `10%`
- `attributed_revenue_rate`
  - падение против baseline: не более `12%`
- `rewrite coverage`
  - доля запросов с ожидаемым rewrite-поведением не ниже `django-inline - 2pp`
- `suggestion coverage`
  - не ниже `django-inline - 5pp`

## 4.3. Recommendation quality metrics, которые блокируют cutover

- `section_fill_rate`
  - обязательные секции непустые не менее чем в `95%` eligible requests
- `recommendation_ctr`
  - `recommendation_click / recommendation_impression`
  - падение против baseline: не более `10%`
- `recommendation_add_to_cart_rate`
  - `add_to_cart / recommendation_click`
  - падение против baseline: не более `10%`
- `recommendation_purchase_rate`
  - `purchase / recommendation_click`
  - падение против baseline: не более `12%`
- `attributed_orders` и `attributed_revenue`
  - падение против baseline: не более `12%`
- `empty_section_share`
  - не выше `5%` для обязательных секций

## 4.4. Attribution и data completeness metrics

Cutover блокируется, если теряется связность request/event/order:

- `request_id` fill rate: `>= 99%`
- `source` / `surface` fill rate: `>= 99.5%`
- `variant` fill rate для reco: `>= 99%`
- `item_id` fill rate для click/add_to_cart/purchase: `>= 99.5%`
- attributed order linkage:
  - search: `search_result_click -> order attribution`
  - recommendations: `recommendation_click|add_to_cart -> purchase attribution`
- mismatch между event payload и contract payload по `source/variant/surface`: `< 1%`

## 5. Smoke, contract и parity tests

## 5.1. Smoke tests, обязательные перед каждым cutover-step

### Search smoke

1. `GET /api/search/query/?q=кофе`
2. `GET /api/search/query/?q=сироп&limit=24`
3. `GET /api/search/query/?q=zzz-no-result`
4. `GET /api/search/suggestions/?q=кофе`
5. fallback smoke: в режиме `fastapi` искусственно уронить service и убедиться в `source=django-inline-fallback`

Проверять:

- `200`
- валидный contract shape
- нет `service_error` в healthy path
- есть `service_error` и fallback в degraded path
- `product_ids` согласованы с `products`

### Recommendation smoke

1. `GET /api/recommendations/home/`
2. `GET /api/recommendations/products/{product_id}/`
3. `GET /api/recommendations/products/{product_id}/sections/fbt/`
4. `POST /api/recommendations/cart/`
5. `POST /api/recommendations/checkout/`
6. `GET /api/recommendations/reorder/` без auth -> `401`
7. `GET /api/recommendations/reorder/` с auth -> `200`
8. `GET /api/recommendations/search-recovery/?q=zzz-no-result`
9. fallback smoke для `recommendation-api`

Проверять:

- наличие обязательных секций
- non-empty `products[]` там, где surface eligible
- валидность `tracking_payload`
- ожидаемые `401/404` error semantics

## 5.2. Contract tests, которые должны стать gate

Минимальный обязательный набор:

- schema snapshot tests для каждого endpoint в обоих режимах
- type/required-field tests для всех top-level и nested fields
- duplicate guards:
  - no duplicated `product_ids`
  - no duplicated `sections[].key`
- auth/error tests для `401/404/400`
- fallback tests:
  - timeout
  - malformed payload
  - remote `500`
- analytics linkage tests:
  - search click -> attribution memory -> order attribution
  - recommendation impression/click -> add_to_cart -> purchase attribution

## 5.3. Shadow parity suite, без которой нельзя делать full cutover

Нужен nightly или hourly parity job на фиксированном наборе:

- `100-300` golden search queries
- `50-100` PDP seeds
- `20-50` cart seeds
- `20-50` checkout seeds
- `20-50` reorder users/seeds

Для каждого кейса сравнивать:

- schema validity
- top-N overlap
- rewrite parity
- facets parity
- section coverage
- tracking payload completeness
- fallback absence в healthy run

Выход parity job:

- `% exact-schema-pass`
- `% semantic-pass`
- `top-10 overlap`
- `zero-result drift`
- `section-fill drift`
- список worst offenders

`Go` только если parity suite зелёный минимум `3` последовательных прогона.

## 6. Alerting и dashboards, которые должны блокировать cutover

## 6.1. Что уже есть и должно использоваться

Уже заведены:

- `SearchZeroResultsHigh`
- `SearchLatencyP95High`
- `SearchClicksMissing`
- `SearchAttributedOrdersMissing`

Уже есть dashboard:

- `deploy/grafana/dashboards/search_funnel.json`

## 6.2. Что обязательно добавить до full cutover

### Search alerts

- `SearchFastapiFallbackSpike`
  - если `source=django-inline-fallback` или `service_error` растут выше порога
- `SearchTopKOverlapLow`
  - если shadow parity job показывает Top-10 overlap `< 0.70`
- `SearchRewriteParityLow`
  - если `rewrite_kind` совпадает хуже `95%`
- `SearchFacetParityLow`
  - если brand/category facet overlap `< 0.80`

### Recommendation alerts

- `RecommendationServiceDown`
  - `/ready` не проходит
- `RecommendationFastapiFallbackSpike`
  - fallback rate `> 1% / 15m`
- `RecommendationEmptySectionsHigh`
  - обязательные секции пустые `> 5%`
- `RecommendationCTRDrop`
  - CTR ниже baseline более чем на `10%`
- `RecommendationAddToCartDrop`
  - add-to-cart rate ниже baseline более чем на `10%`
- `RecommendationAttributedOrdersDrop`
  - attributed orders/revenue ниже baseline более чем на `12%`
- `RecommendationAttributionMissing`
  - клики есть, а purchase attribution отсутствует

## 6.3. Dashboard minimum

### Search dashboard

Должен показывать по разрезам:

- `surface`
- `provider`
- `source`
- `mode`

Обязательные панели:

- requests, errors, fallback rate
- p50/p95/p99 latency
- zero-result share
- rewrite coverage
- top-K overlap shadow diff
- clicks, attributed orders, attributed revenue

### Recommendation dashboard

Сейчас отдельного зрелого dashboard нет; это gap.

Минимальные панели:

- selection executions
- candidate count
- empty-section share
- impressions, clicks, add_to_cart, purchase
- CTR / ATC / purchase rate
- attributed orders / revenue
- surface/source/variant split
- fallback rate
- p50/p95/p99 latency

## 7. Cutover go/no-go

## 7.1. `Go` только если одновременно выполнено всё

- contract tests зелёные в `django-inline` и `fastapi`
- parity suite зелёный `3` прогона подряд
- fallback rate в healthy shadow/canary `< 1%`
- search zero-result drift в допуске
- recommendation section coverage в допуске
- conversion/attribution drift в допуске
- dashboards и alerts реально подключены и шумят адекватно
- rollback проверен и занимает не больше одного operational step

## 7.2. `No-go`, если происходит хотя бы одно

- `service_error`/fallback spike
- top-K overlap ниже порога
- rewrite/facet parity разваливается
- zero-results выросли выше порога
- CTR / ATC / attributed orders падают больше допустимого
- теряется `request_id` или attribution linkage
- empty mandatory sections > `5%`
- на recommendations нет отдельного dashboard и alerts

## 8. Что нужно проверить вручную

1. Включить `fastapi` mode только на shadow/canary.
2. Прогнать одинаковый набор search queries и PDP/cart/checkout seeds в обоих режимах.
3. Проверить `source`, `service_source`, `engine_source`, `service_error`.
4. Проверить, что в healthy path нет fallback.
5. Проверить Grafana:
   - search funnel
   - service health
   - fallback/error rates
6. Проверить GlitchTip/Loki на transport/payload errors.
7. Проверить analytics ingest:
   - `/analytics/search-feedback/`
   - `/analytics/recommendation-feedback/`
8. Проверить order attribution после реального add-to-cart/purchase сценария.

## 9. Итог для backlog 051

### Решение QA

- `search`: можно двигаться в shadow/canary при условии подключения parity diff gates
- `recommendations`: full cutover блокируется до усиления metrics/alerts/dashboards и доведения качества `fastapi` до parity

### Главный инженерный вывод

Сейчас правильный путь не “включить FastAPI”, а:

1. сначала добавить parity telemetry
2. затем прогнать shadow diff
3. потом выдержать canary на реальном трафике
4. и только после этого переводить surfaces с `django-inline` на `fastapi`

