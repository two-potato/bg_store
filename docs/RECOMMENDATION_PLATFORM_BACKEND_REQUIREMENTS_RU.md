# Recommendation Platform Backend Requirements (Backlog 053 + backend/data-search 054)

Дата: 2026-03-28  
Фокус: backend-аудит текущей recommendation-системы на базе реального кода

## Scope и фактическая база аудита

Аудит основан на текущем коде:

- `backend/shopfront/recommendation/*`
- `backend/shopfront/views/analytics.py`
- `backend/shopfront/tasks.py`
- `backend/shopfront/models.py`
- `backend/API.md`
- `docs/SEARCH_RECO_CONTRACT_SLICE_044_046.md`

Дополнительно учтены связанные backend-модули search-attribution/observability, потому что часть recommendation surfaces зависит от search сигналов.

---

## 1) Текущие data sources и event sources recommendation-системы

### 1.1 Транзакционные и справочные источники

- Каталог и атрибуты товара: `Product` (brand/category/seller/price/stock/is_new/is_promo/lead_time/min_order_qty).
- Заказы: `Order`, `OrderItem` (покупки, co-purchase, replenishment, reorder).
- Пользовательские сущности:
  - `FavoriteProduct`
  - `RecentlyViewedProduct`
  - `BrandSubscription`
  - `CategorySubscription`
  - `SavedSearch`
  - `PersistentCart`

### 1.2 Recommendation storage / materializations

- `RecommendationEvent` (сырые события feedback + purchase attribution).
- `RecommendationPopularitySnapshot` (global/category/brand/seller по окну `7d/30d`).
- `RecommendationProductAffinity` (`co_purchase`, `similar`, `substitute`, `accessory`).
- `RecommendationUserAffinity` (brand/category/seller/tag/price_band).
- `RecommendationReplenishmentProfile` (повторяемость покупки, интервал, score).
- `RecommendationSet` (materialized подборки по kind/scope с TTL).
- `RecommendationFeatureSnapshot` (user/product/global фичи с TTL).
- `RecommendationTrainingDataset`, `RecommendationModelArtifact` (offline ML контур).

### 1.3 Event sources (как сигналы реально попадают в систему)

- Frontend → backend ingest:
  - `POST /shopfront/analytics/recommendation-feedback/`
  - `POST /shopfront/analytics/search-feedback/`
- Server-side запись recommendation событий:
  - `record_recommendation_event(...)` из cart/checkout/discovery/saved-list flows.
- Checkout attribution:
  - session attribution собирается в checkout orchestration.
  - `emit_checkout_recommendation_feedback` пишет `purchase` в `RecommendationEvent`.
- Synthetic/backfill источники:
  - management commands `backfill_*` создают импрессии/клики/конверсии для наполнения датасета.

### 1.4 Candidate/data-search источники внутри recommendation

- Materialized sets (`RecommendationSet`) с fallback.
- Popularity snapshots (`RecommendationPopularitySnapshot`).
- Affinity edges (`RecommendationProductAffinity`).
- User affinity profile (`RecommendationUserAffinity`).
- Replenishment profile (`RecommendationReplenishmentProfile`).
- Semantic candidates через search provider (`get_search_provider(...).live_bundle`) для:
  - `opensearch_similar_products`
  - `opensearch_substitute_products`
  - `search_recovery_candidate_ids`

---

## 2) Что реально есть из сигналов, а чего нет/слабое

### 2.1 Что есть и используется

- Exposure и feedback:
  - `recommendation_impression`
  - `recommendation_click`
  - `add_to_cart`
  - `remove_from_cart`
  - `purchase`
  - `recommendation_dismiss`
  - `favorite_add`
  - `saved_list_add`
- Search-side сигналы для recovery и attribution:
  - `search`
  - `search_result_click`
  - `purchase` через checkout attribution task.
- Контекст для обучения/ранжирования:
  - reason_codes/candidate_sources/score_hint в payload.
  - surface/source/variant/strategy/model_version.

### 2.2 Слабые места и пропуски

- Нет стабильного `impression_id`/`exposure_id` для жёсткой связи click/add_to_cart/purchase с конкретным показом.
- Нет idempotency ключа события ingest уровня клиента.
- Session-based attribution ограничен TTL и браузером; междевайсная атрибуция неполная.
- Нет явных сигналов quality/negative feedback кроме `dismiss` и неявного no-click.
- Нет нормализованного события «видимость в viewport» (есть лишь отправленный impression payload).
- Нет latency/error telemetry по recommendation generation в contract response как first-class поля.
- Synthetic backfill-события потенциально смешиваются с «боевыми» при обучении без жёсткого hard-filter в dataset builder.

---

## 3) Где сегодня heuristics/fallback, а не честная personalization

### 3.1 Home personalization

- Есть персонализация через user affinity/favorites/recent/watchlist/replenishment.
- Но сильная зависимость от heuristic mixing и popularity fallback.
- `RecommendationSet` используется как materialization, но при отсутствии set идёт рантайм fallback.

### 3.2 PDP / substitutes / accessories

- Similar/substitutes сильно зависят от semantic search + affinity edges.
- Accessories в основном same-seller cross-sell.
- Это гибрид эвристик и контекстных правил, а не end-to-end learned personalization.

### 3.3 Cart/Checkout

- Cross-sell на базе same-seller + popularity/replenishment, затем heuristic/ML rerank.
- Персонализация ограничена доступными affinity/replenishment признаками.

### 3.4 Reorder/Search recovery

- Reorder: materialized profile + fallback на order history.
- Search recovery: semantic query candidates + hybrid affinity + global popular.

### 3.5 FastAPI parity-факт

- Backend contracts поддерживают `django-inline|fastapi` и fallback.
- По docs заявлена parity-hardening стадия.
- При этом recommendation-service слой всё ещё имеет bootstrap-эвристики (не полная эквивалентность Django engine), что означает: full parity для recommendations пока не достигнута.

---

## 4) Какие новые API и поля нужны

Нужен эволюционный контракт без breaking changes: добавляем поля как optional.

### 4.1 Public recommendations envelope (`/api/recommendations/*`)

Добавить:

- `request_id` (echo).
- `recommendation_id` (идентификатор выдачи/решения).
- `generated_at` (UTC ISO).
- `generation_mode` (`materialized` | `online` | `fallback`).
- `latency_ms` (backend generation latency).
- `experiment` объект:
  - `variant`
  - `model_version`
  - `strategy`

### 4.2 Section-level поля

- `candidate_count` (до ранжирования).
- `selected_count` (после ранжирования).
- `fallback_applied` (bool).
- `freshness_ttl_sec` (для materialized sections).

### 4.3 Product-level explainability (optional)

- `rank_score` (float).
- `reason_codes` (list[str]).
- `candidate_sources` (list[str]).
- `score_hint` (float).

Важно: можно отдавать только при `debug=1`/internal mode, чтобы не раздувать payload на public-path.

### 4.4 Internal service contract (`/api/internal/recommendations/*`)

Добавить входные поля:

- `session_key` (optional).
- `exclude_product_ids` (list[int]).
- `surface_context` (page/seller/category/search_query/cart_size).
- `schema_version`.

Добавить выходные поля:

- `contract_version`.
- `engine_source`.
- `service_source`.
- `service_mode`.

---

## 5) Какие события нужно собирать обязательно

Минимально обязательная event taxonomy v1 (для рекомендаций):

- `recommendation_impression`
- `recommendation_click`
- `recommendation_add_to_cart`
- `recommendation_remove_from_cart`
- `recommendation_purchase`
- `recommendation_dismiss`
- `recommendation_hide` (явно скрыт/заменён блок)
- `recommendation_detail_open` (опционально для B2B длинных карточек)

Обязательные поля для каждого recommendation события:

- `event_id` (uuid, idempotency)
- `occurred_at` (client_ts + server_ts)
- `request_id`
- `recommendation_id`
- `surface`
- `section_key`
- `recommendation_source`
- `strategy`
- `variant`
- `model_version`
- `product_id`
- `position`
- `price_at_event`
- `stock_at_event`
- `candidate_sources`
- `reason_codes`

Обязательная связка с search (для data-search 054):

- `search_term`
- `search_origin`
- `search_provider`
- `search_rewrite_kind`

---

## 6) Какие модели данных/таблицы/индексы/TTL/materializations нужны

### 6.1 Что оставляем как основу

- Текущие таблицы recommendation-платформы уже покрывают базовый контур и не требуют rewrite.
- Индексы в `models.py` в целом достаточны для стартовой нагрузки.

### 6.2 Точечные расширения (эволюционно)

Расширить `RecommendationEvent`:

- добавить поля:
  - `event_id` (UUID, unique/index)
  - `recommendation_id` (CharField, index)
  - `impression_id` (UUID/index)
  - `parent_impression_id` (UUID/index)
  - `engine_source`
  - `service_source`
  - `service_mode`
  - `latency_ms`
  - `rank_score`
- добавить индексы:
  - `(recommendation_id, event, created_at)`
  - `(impression_id, event, created_at)`
  - `(request_id, product_id, event, created_at)`

### 6.3 Retention/TTL

- Session attribution:
  - search: 6h (как сейчас), recommendation: 24h (как сейчас), dismiss: 14d.
- Raw `RecommendationEvent`:
  - hot retention: 90-180 дней.
  - затем агрегаты + архив/удаление.
- `RecommendationSet`:
  - home/pdp/cart: 1-2h.
  - reorder: 6h.
  - stale cleanup ежедневно.
- `RecommendationFeatureSnapshot`:
  - user/product: 6h.
  - global: 3h.

### 6.4 Materializations (не раздувая платформу)

Нужны 3 устойчивых materialized слоя:

1. `popularity_daily` (global/category/brand/seller; 7d/30d).
2. `affinity_edges_daily` (co_purchase/similar/substitute/accessory).
3. `user_affinity_daily` + `replenishment_daily`.

Текущее поведение с full delete/rebuild в tasks нужно эволюционно перевести на incremental upsert и windowed refresh.

---

## 7) Business-rules и ограничения, которые должны учитываться

- Не ломаем backend как source of truth; рекомендации остаются domain-driven в Django.
- Не переносим критическую бизнес-логику в frontend/Next.
- Ограничения ранжирования из текущего кода должны сохраняться:
  - anti-duplication по seller/brand/category.
  - исключение товаров из cart при cart/checkout recos.
  - `require_in_stock=True` почти везде, кроме substitutes-сценариев.
  - учёт lead-time/min-order-qty в scoring.
  - учёт dismiss-policy (14 дней).
  - `reorder` требует auth.
- Учитывать B2B-ограничения:
  - MOQ/stock/lead-time имеют коммерческий приоритет над «красивым rank score».
  - избегать рекомендаций с заведомо плохой доступностью для checkout surfaces.

---

## 8) Как должна выглядеть связка Django ↔ recommendation service

### 8.1 Текущее корректное ядро

- Public API: `/api/recommendations/*` (Django DRF).
- Internal API: `/api/internal/recommendations/*` (token-protected, force `django-inline`).
- Runtime bridge:
  - `RECOMMENDATION_SERVICE_MODE=django-inline|fastapi`
  - fallback на Django при service-error.

### 8.2 Целевая связка (эволюционно)

1. Django остаётся policy/ranking source of truth.
2. Recommendation-service сначала выступает как thin orchestration/proxy к internal contracts.
3. Затем постепенно забирает candidate retrieval/ranking части по surfaces, но:
   - контракты и business-rules синхронизируются через parity tests.
   - fallback path всегда доступен.
4. Cutover только через staged rollout:
   - shadow
   - canary
   - surface-by-surface enablement
   - rollback по feature flag.

### 8.3 Контрактная дисциплина

- Public schema не включает internal routes.
- Internal contract versioning обязателен.
- Для каждого surface — parity тесты `django-inline` vs `fastapi`.

---

## 9) Strategy block (эволюционный путь к сильной marketplace recommendation system)

### 9.1 Candidate source map (v1)

- `home_for_you`:
  - personalized candidates
  - hybrid affinity
  - session context
  - global popular (cold-start fallback)
- `home_watchlist`:
  - brand/category subscriptions
  - fallback global popular
- `home_replenishment`:
  - replenishment profile
- `pdp_similar`:
  - semantic similar
  - co-view/similar affinity
- `pdp_substitutes`:
  - semantic substitute
  - substitute affinity
- `pdp_accessories`:
  - same-seller cross-sell
- `cart/checkout`:
  - same-seller + fast-stock
  - replenishment/profile
- `search_recovery`:
  - semantic query candidates
  - hybrid affinity
  - popular fallback

### 9.2 Ranking v1

- Базовый scorer:
  - heuristic ranked (`ranker.py`) как стабильный baseline.
- ML option:
  - `ml_v1` с rollout-percent и per-surface enable.
- Multi-objective приоритизация:
  - relevance + conversion + availability + quality.
- Обязательный fallback:
  - при ошибке сервиса или model-unavailable возвращаем deterministic heuristic.

### 9.3 Popularity model v1

- Текущая формула (purchase/favorite/view + promo/new/stock) остаётся baseline.
- Эволюция:
  - time-decay
  - seller/category normalization
  - separate popularity для B2B checkout surfaces.

### 9.4 Substitutes logic v1

- Обязательные факторы:
  - category/material/purpose semantic similarity
  - price-distance penalty/bonus
  - stock & lead-time guardrails
  - MOQ compatibility.

### 9.5 Accessories logic v1

- База:
  - co-purchase graph + same-seller cross-sell.
- Улучшения:
  - order-basket lift,
  - sequence-aware compatibility,
  - исключение конфликтующих SKU.

### 9.6 Personalization roadmap

Wave 1 (короткий цикл):

- Укрепить event taxonomy и idempotent ingestion.
- Добавить recommendation_id/impression_id.
- Перевести full-rebuild tasks на incremental refresh.

Wave 2 (средний цикл):

- Довести parity service mode по recommendations.
- Включить стабильные per-surface rankers с explainability.
- Ввести strict parity gates в CI.

Wave 3 (дальше):

- Продвинутый multi-objective ranking (margin/availability/service level).
- Cross-session identity stitching.
- Surface-level policy optimization (home/pdp/cart/checkout отдельно).

### 9.7 Event taxonomy (минимум для продакшена)

- Exposure: impression, viewport_impression.
- Engagement: click, detail_open.
- Commerce intent: add_to_cart, remove_from_cart, save/favorite.
- Conversion: purchase.
- Negative feedback: dismiss/hide.
- Attribution bridge: recommendation_id, impression_id, request_id.

### 9.8 Offline/online metrics

Offline:

- AUC
- logloss
- precision@k
- mrr@k
- ndcg@k
- recall@k
- purchase/reorder positives.

Online:

- CTR per surface/source/variant
- add_to_cart_rate
- checkout_attach_rate
- purchase_conversion_rate
- attributed_revenue / attributed_orders
- fallback_rate (`django-inline-fallback`)
- latency p50/p95/p99
- zero-result recovery uplift (для search_recovery).

---

## Рекомендуемое решение по 053/054 (без раздувания)

1. Сохранить Django как ядро orchestration/policy и source of truth.
2. Закрыть контрактные и event-gaps (request/recommendation/impression identity) до расширения ML.
3. Перейти от full rebuild к incremental materialization.
4. Довести FastAPI parity для recommendations только после контрактной и метрик-дисциплины.
5. Запускать rollout по surfaces, а не «всё сразу».

Это даст реальный рост качества рекомендаций без дорогого и рискованного rewrite-пути.
