# Recommendation Stage 1 Contract Baseline

Дата: 2026-03-28  
Роль: `backend`  
Пакет: backlog `063`

## Цель

Зафиксировать минимальный Stage 1 contract freeze recommendation platform без broad refactor:

- единый envelope для `/api/recommendations/*`
- обязательные Stage 1 поля
- event taxonomy baseline для analytics ingest
- честная граница между тем, что уже реально внедрено в runtime, и тем, что пока закреплено как contract baseline

## Обязательные поля Stage 1

### Envelope-level

- `recommendation_id`
- `source`
- `service_source`
- `engine_source`
- `fallback_source`
- `empty_reason`
- `latency_ms`
- `surface`
- `variant`

### Section-level

- `key`
- `title`
- `source`
- `strategy`
- `tracking_payload`
- `impression_id`
- `fallback_source`
- `empty_reason`
- `products[]`

## Что реально внедрено в runtime

### Public/internal recommendation contracts

В `backend/shopfront/recommendation/contracts.py` Stage 1 поля теперь реально формируются для contract payload:

- генерируется `recommendation_id`
- считается `latency_ms`
- на section level проставляется `impression_id`
- проставляются `fallback_source` и `empty_reason`
- `tracking_payload` обогащается `recommendation_id`, `impression_id`, `engine_source`, `service_source`, `fallback_source`, `empty_reason`, `latency_ms`

### API schema / serializers

В `backend/shopfront/api/serializers.py` Stage 1 поля закреплены в DRF schema/OpenAPI для recommendations.

### Analytics ingest baseline

В `backend/shopfront/views/analytics.py` и `backend/shopfront/recommendation/attribution_service.py` Stage 1 поля теперь проходят через ingest/session attribution baseline:

- `recommendation_id`
- `impression_id`
- `engine_source`
- `service_source`
- `fallback_source`
- `empty_reason`
- `latency_ms`

Дополнительно:

- downstream `recommendation_click` / `add_to_cart` path больше не теряет Stage 1 metadata при записи в `RecommendationEvent`
- targeted tests закрепляют и envelope-level поля, и analytics linkage

Важно: на Stage 1 эти поля сохраняются в `payload`/session attribution и не требуют schema-breaking model migration.

## Что пока зафиксировано только как baseline, но не доведено до полной platform-ready реализации

- нет отдельных DB columns/indexes для `recommendation_id` / `impression_id`
- нет полной end-to-end idempotency модели recommendation events
- нет гарантированной parity этих полей со всеми future FastAPI runtime payloads
- нет ещё отдельного recommendation-specific dashboard, который использует эти поля в production
- нет ещё полного storefront adoption этих полей на всех surfaces

## Event taxonomy baseline

Stage 1 recommendation event baseline:

- `recommendation_impression`
- `recommendation_click`
- `add_to_cart`
- `remove_from_cart`
- `purchase`
- `recommendation_dismiss`
- `favorite_add`
- `saved_list_add`

Минимальные Stage 1 metadata fields:

- `request_id`
- `recommendation_id`
- `impression_id`
- `recommendation_source`
- `surface`
- `experiment_variant`
- `strategy`
- `model_version`
- `engine_source`
- `service_source`
- `fallback_source`
- `empty_reason`
- `latency_ms`

## Честный итог

Stage 1 contract freeze внедрён эволюционно:

- recommendation envelope и schema теперь согласованы по обязательным полям
- ingest baseline умеет принять и протащить эти поля
- click/add-to-cart attribution path сохраняет эти поля в `RecommendationEvent.payload`
- без broad refactor и без миграции критичных таблиц

Но это ещё не full platform completion. Для Stage 2/3 останутся:

- indexed event model
- recommendation-specific dashboards/alerts
- storefront-wide adoption
- full parity serving между `django-inline` и `fastapi`
