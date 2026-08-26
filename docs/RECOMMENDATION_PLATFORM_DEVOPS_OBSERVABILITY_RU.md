# Recommendation Platform DevOps Observability

Дата: 2026-03-28  
Роль: `devops`

## Цель

Зафиксировать практический `platform/devops` план для recommendation-системы Servio в реальном стеке:

- `Django` как gateway и source of truth для rollout
- `FastAPI recommendation-api` как отдельный serving layer
- `Postgres`, `Redis`, `OpenSearch`
- `Grafana`, `Loki`, `Prometheus`, `Alertmanager`, `GlitchTip`

Документ не описывает идеальный абстрактный future-state. Он фиксирует то, что нужно для безопасного роста и rollout recommendation-platform в текущей инфраструктуре.

## 1. Observability plan

### 1.1. Общая цель наблюдаемости

Нужно видеть не только `up/down`, но и поведение recommendation-системы по каждому surface:

- что запросили
- какой runtime ответил
- сколько заняло времени
- был ли fallback
- почему блок пустой
- потерялись ли attribution/correlation поля

### 1.2. Request/response logging

Structured logs обязательны и в `Django gateway`, и в `recommendation-api`.

Минимальные поля логирования:

- `timestamp`
- `service`
- `environment`
- `request_id`
- `trace_id` или `traceparent`
- `surface`
- `source`
- `variant`
- `provider`
- `strategy`
- `user_id_present=true|false`
- `session_id_present=true|false`
- `product_id` или `seed_product_ids_count`
- `latency_ms`
- `status_code`
- `outcome=ok|empty|fallback|timeout|error|partial`
- `fallback_reason`
- `candidate_count`
- `returned_items_count`
- `eligible=true|false`
- `cache_hit=true|false`
- `rollout_mode=django-inline|shadow|canary|fastapi`
- `rollout_label`

Что не логировать:

- сырой PII
- полный session payload
- полные recommendation payload bodies в постоянный info-log

Payload sampling допустим только:

- для `error`
- для `shadow parity mismatch`
- для небольшой debug-sample доли

### 1.3. Correlation IDs

Единый correlation contract обязателен:

- внешний `X-Request-ID` генерируется или пробрасывается на Django gateway
- дальше тот же `request_id` прокидывается в `recommendation-api`
- `traceparent` сохраняется, если уже есть
- `surface`, `source`, `variant`, `strategy` должны быть одинаковы в request log, response log и analytics events

Минимум для связности:

- `request_id` fill rate `>= 99%`
- `surface/source` fill rate `>= 99.5%`
- `variant` fill rate `>= 99%`

### 1.4. Latency

Нужно считать latency по двум слоям:

- `gateway latency`: сколько занял recommendation-block в Django
- `service latency`: сколько занял вызов `recommendation-api`

Отдельно нужны:

- `p50`
- `p95`
- `p99`
- timeout count
- fallback count

Критично отделять:

- network/connect latency
- serving latency
- cache lookup latency
- OpenSearch latency
- DB lookup latency

### 1.5. Error tracking

Ошибки должны идти в две системы:

- `Prometheus` для rates/alerts
- `GlitchTip` для stack traces, payload context и группировки

Отдельные error classes:

- `timeout`
- `connect_error`
- `schema_mismatch`
- `empty_required_section`
- `gateway_contract_error`
- `upstream_500`
- `cache_error`
- `background_refresh_error`

### 1.6. Empty/fallback tracking

Для recommendations это критично.

Нужно считать отдельно:

- `eligible_request_total`
- `empty_section_total`
- `fallback_total`
- `fallback_due_timeout_total`
- `fallback_due_error_total`
- `fallback_due_empty_total`
- `partial_section_total`

Важно отличать:

- surface реально не eligible
- рекомендация есть, но сервис вернул пусто
- FastAPI вернул пусто и gateway подставил fallback
- оба слоя вернули пусто по честной причине

## 2. Какие метрики и логи должны собираться

## 2.1. На recommendation service

Prometheus metrics:

- `servio_reco_requests_total{surface,variant,outcome,mode}`
- `servio_reco_errors_total{surface,error_type,mode}`
- `servio_reco_latency_seconds_bucket{surface,mode}`
- `servio_reco_candidate_count_bucket{surface,strategy}`
- `servio_reco_items_returned_bucket{surface}`
- `servio_reco_empty_surface_total{surface,reason}`
- `servio_reco_fallback_hints_total{surface,reason}`
- `servio_reco_cache_hits_total{surface,cache_layer}`
- `servio_reco_cache_misses_total{surface,cache_layer}`
- `servio_reco_opensearch_latency_seconds_bucket{query_kind}`
- `servio_reco_db_latency_seconds_bucket{query_kind}`
- `servio_reco_background_jobs_total{job_name,outcome}`
- `servio_reco_shadow_diff_total{surface,diff_kind}`

Loki logs:

- request summary log на каждый запрос
- error log с `request_id`
- sampled parity/shadow diff log
- background refresh log

GlitchTip:

- timeout exceptions
- response schema mismatch
- repeated empty required sections
- retry storm / queue failures

## 2.2. На Django gateway

Prometheus metrics:

- `servio_recommendation_gateway_requests_total{surface,mode,outcome}`
- `servio_recommendation_gateway_latency_seconds_bucket{surface,mode}`
- `servio_recommendation_gateway_fallback_total{surface,reason}`
- `servio_recommendation_gateway_empty_section_total{surface,reason}`
- `servio_recommendation_gateway_eligible_total{surface}`
- `servio_recommendation_gateway_shadow_requests_total{surface}`
- `servio_recommendation_gateway_shadow_mismatch_total{surface,diff_kind}`
- `servio_recommendation_gateway_canary_requests_total{surface,variant}`
- `servio_recommendation_gateway_contract_errors_total{surface,error_type}`
- `servio_recommendation_clicks_total{surface,source,variant}`
- `servio_recommendation_add_to_cart_total{surface,source,variant}`
- `servio_recommendation_attributed_orders_total{surface,source,variant}`
- `servio_recommendation_attributed_revenue_total{surface,source,variant}`

Loki logs:

- gateway request log по каждому recommendation surface
- fallback decisions
- shadow diff summary
- canary routing decision

GlitchTip:

- remote service failure after retries
- malformed payload from service
- rendering failure на стороне storefront bridge

## 2.3. Что должно быть в dashboard

Минимум 4 operational dashboard блока в `Grafana`:

1. `Availability and latency`
- gateway p50/p95/p99
- service p50/p95/p99
- error rate
- timeout rate

2. `Fill and quality`
- empty section share
- section fill rate
- returned item count
- candidate count

3. `Rollout`
- mode split
- shadow diff rate
- canary request share
- fallback share

4. `Business bridge`
- CTR
- add-to-cart from reco
- attributed orders
- attributed revenue

## 3. Что нужно для shadow/canary/rollback

## 3.1. Shadow

Нужно:

- `RECOMMENDATION_SERVICE_MODE=shadow`
- `RECOMMENDATION_SERVICE_SHADOW_ENABLED=1`
- `RECOMMENDATION_SERVICE_SHADOW_SURFACES=...`
- sampled duplicate calls из Django gateway
- отдельный shadow diff log
- сравнение:
  - top-k overlap
  - empty/non-empty parity
  - candidate count delta
  - latency delta

Shadow нельзя включать без:

- request correlation
- отдельного shadow metrics namespace
- ограничения по surfaces

## 3.2. Canary

Нужно:

- `RECOMMENDATION_SERVICE_MODE=canary`
- `RECOMMENDATION_SERVICE_CANARY_ENABLED=1`
- `RECOMMENDATION_SERVICE_CANARY_SURFACES=home,pdp`
- `RECOMMENDATION_SERVICE_CANARY_PERCENT=1..10`

Canary должен быть:

- только по surface allowlist
- только с быстрым rollback в `django-inline`
- только после зелёного shadow parity

Минимальные stop-signals для canary:

- p95 latency выросла > `20%`
- `empty_section_share` > `5%` на обязательных секциях
- error rate > `1%`
- attributed orders/revenue деградировали > согласованного порога

## 3.3. Rollback

Rollback path должен быть операционно тривиальным:

- вернуть `RECOMMENDATION_SERVICE_MODE=django-inline`
- отключить `*_SHADOW_ENABLED` или `*_CANARY_ENABLED`
- пересоздать только `backend`, без обязательного hard stop всего стека

Дополнительно нужно:

- rollback runbook
- dashboard row именно для rollback-signals
- логировать факт rollback с причиной и временем

## 4. Где нужен cache, precompute, queue/background refresh

## 4.1. Cache

`Redis` нужен в трёх местах:

1. short-lived response cache
- `home`
- `pdp`
- `catalog/search-recovery`
- TTL короткий, чтобы не законсервировать плохую выдачу

2. candidate cache
- популярное
- часто используемые related/substitute pools
- cross-sell seeds

3. rollout/cache shield
- защита от повторного вычисления при всплеске одинаковых запросов

Что нельзя кешировать агрессивно:

- персонализированные рекомендации без user segmentation key
- `checkout/cart` surfaces без привязки к корзине

## 4.2. Precompute

Precompute нужен для:

- `popular`
- `new/promoted`
- category-brand candidate pools
- reorder suggestions
- simple related-products graph

Precompute должен писать результаты в `Redis` и при необходимости в `Postgres` materialized tables или feature-store таблицы, а не вычисляться на каждый request заново.

## 4.3. Queue / background refresh

Нужен `Celery` или эквивалентный background path для:

- refresh candidate pools
- refresh recommendation features
- backfill attribution
- rebuild hot recommendation caches
- prewarm популярных surfaces

Обязательные фоновые джобы:

- `refresh_home_reco_candidates`
- `refresh_pdp_related_candidates`
- `refresh_reorder_candidates`
- `reconcile_reco_attribution_events`
- `shadow_diff_aggregator`

## 5. Readiness к росту нагрузки и bottlenecks текущей схемы

## 5.1. Текущие bottlenecks

В текущей схеме узкие места такие:

1. `Django gateway` остаётся orchestration point
- при росте трафика именно gateway первым станет bottleneck по latency и fallback orchestration

2. `recommendation-api` пока в основном ходит обратно в backend/catalog
- это увеличивает hop count
- создаёт зависимость от backend readiness
- усиливает cascading failure pattern

3. `OpenSearch` и `Postgres` используются как shared infrastructure
- search/reco spikes могут ударять по общему backend path

4. без нормального response cache recommendation path становится слишком чувствителен к burst traffic

5. без precompute `home/pdp/cart` surfaces начинают конкурировать за одинаковые candidate lookups

## 5.2. Что нужно для роста нагрузки

- разделить `gateway latency` и `service latency`
- ограничить synchronous upstream hops
- ввести Redis cache на hot surfaces
- увести тяжёлые candidate refresh в background
- иметь protection на timeout/fallback storm
- иметь per-surface timeout budgets
- иметь circuit breaker semantics на gateway

## 5.3. Практические лимиты текущей схемы

До полноценного scale-up опасно:

- увеличивать `canary` выше `10-15%`
- включать сразу все surfaces
- переводить `cart`, `checkout`, `reorder` без cache/precompute и стабильного attribution

Сначала безопаснее:

- `home`
- затем `pdp`
- только потом `cart`
- `checkout` и `reorder` последними

## 6. Production readiness checklist

## 6.1. Infra/runtime

- есть `recommendation-api /health`
- есть `recommendation-api /ready`
- есть `backend /health`
- `docker-compose.metrics.yml` поднят и стабилен
- `Prometheus`, `Loki`, `Grafana`, `Alertmanager`, `GlitchTip` доступны

## 6.2. Logging/metrics

- structured logs включены и проверены
- `request_id` проходит через gateway и service
- есть отдельные gateway/service latency metrics
- есть empty/fallback metrics
- есть shadow/canary routing metrics
- есть business bridge metrics по clicks/add-to-cart/orders/revenue

## 6.3. Rollout safety

- default остаётся `django-inline`
- есть surface allowlist
- есть percent-based canary
- есть быстрый env rollback
- есть stop-signals и alert rules

## 6.4. Data/quality

- `section_fill_rate >= 95%` на обязательных surfaces
- `empty_section_share <= 5%`
- request/event/order attribution не теряет связность
- shadow parity metrics в пределах согласованных дельт

## 6.5. Operations

- есть runbook на incident/fallback storm
- есть owner на dashboard/alerts
- есть smoke сценарии перед cutover step
- есть post-release watch window минимум `2-4` часа

## 7. Что обязательно нужно до этапов 1/2/3

Ниже этапы относятся к эволюции recommendation-platform, а не к идеальному future-state.

## 7.1. До этапа 1

Этап 1: baseline observability и controlled shadow.

Обязательно:

- единый `request_id`
- structured logs в `Django gateway` и `recommendation-api`
- Prometheus metrics для latency/error/empty/fallback
- Grafana dashboard по surfaces
- GlitchTip error grouping
- shadow env/flags и allowlist surfaces
- smoke для:
  - `home`
  - `pdp`
  - `search-recovery`

Без этого shadow запускать нельзя.

## 7.2. До этапа 2

Этап 2: canary на read-heavy surfaces.

Обязательно:

- зелёный shadow parity
- `top-k overlap` и `empty_surface_delta` под контролем
- canary routing metrics
- rollback по env без redeploy всей системы
- cache на `home` и `pdp`
- alert rules на:
  - p95 latency
  - error rate
  - empty section share
  - fallback spike

Без этого `home/pdp canary` нельзя расширять.

## 7.3. До этапа 3

Этап 3: расширение на `cart/checkout/reorder` и подготовка к прямому `fastapi` mode.

Обязательно:

- background refresh/precompute jobs
- cache strategy для cart-like surfaces
- стабильное attribution linkage
- подтверждённая нагрузочная ёмкость Redis/OpenSearch/backend
- circuit breaker semantics на gateway
- отдельный incident runbook для fallback storm
- business metrics gates:
  - CTR
  - add-to-cart
  - attributed orders
  - attributed revenue

Без этого нельзя безопасно включать heavy transactional surfaces и нельзя идти в более широкий cutover.

## Итог

Recommendation-platform readiness для Servio сейчас должна строиться вокруг трёх простых принципов:

- `Django gateway` остаётся контроллером rollout и fallback
- `recommendation-api` должен быть прозрачен по latency, empty/fallback и errors
- решение о canary/cutover должно приниматься не только по uptime, но и по quality/business metrics

Главная операционная цель: сделать recommendation-serving наблюдаемым, обратимым и ограниченным по blast radius.
