# Recommendation Platform Metrics & QA

Дата: 2026-03-28  
Роль: `qa_metrics`

## 1. Цель

Зафиксировать recommendation platform как измеряемую бизнес-систему, а не как набор “рекомендации есть/нет”.

Документ нужен для трёх задач:

- управлять качеством recommendation surfaces по бизнес-эффекту
- отделять проблемы retrieval / ranking / UI / stock / labeling
- дать честный `go/no-go` для rollout и A/B экспериментов

Опора на текущую архитектуру:

- `backend/shopfront/recommendation/service.py`
- `backend/shopfront/recommendation/selectors.py`
- `backend/shopfront/recommendation/ranker.py`
- `backend/shopfront/recommendation/scoring_service.py`
- `backend/shopfront/recommendation/ml.py`
- `backend/shopfront/recommendation/feature_store.py`
- `backend/shopfront/recommendation/observability.py`
- `backend/shopfront/recommendation/attribution_service.py`
- `backend/shopfront/views/analytics.py`

## 2. Recommendation surfaces, которые считаем платформой

Измерять нужно не “рекомендации в целом”, а по конкретным surfaces:

- `home`
  - `recommended_for_you`
  - `recently_viewed`
  - `watchlist`
  - `popular`
  - `replenishment`
- `pdp`
  - `similar_products`
  - `accessory_products`
  - `substitute_products`
- `cart`
  - `cross_sell`
- `checkout`
  - `cross_sell`
- `reorder`
  - `reorder`
- `catalog`
  - `search_recovery`

Все метрики ниже должны считаться минимум в разрезах:

- `surface`
- `section key`
- `recommendation_source`
- `variant`
- `strategy`
- `source`
  - `django-inline`
  - `fastapi`
  - `django-inline-fallback`

## 3. Продуктовые метрики recommendation sections

## 3.1. Основные outcome-метрики

### CTR

Формула:

- `recommendation_click / recommendation_impression`

Считать отдельно:

- по `surface`
- по `section`
- по `position`
- по `variant`
- по `source`

Зачем:

- показывает, замечают ли блок и кажется ли он релевантным

### Add-to-cart rate

Формула:

- `add_to_cart / recommendation_click`
- вторично: `add_to_cart / recommendation_impression`

Зачем:

- отделяет “кликнули из любопытства” от “товар действительно подходит”

### CVR

Формула:

- `purchase / recommendation_click`
- вторично: `purchase / recommendation_impression`

Зачем:

- главный маркер того, что блок не просто привлекает внимание, а двигает заказ

### Repeat purchase uplift

Формула:

- доля повторных заказов у пользователей, взаимодействовавших с `reorder` / `replenishment`
- среднее число дней до следующего заказа после exposure/click

Зачем:

- особенно важна для `reorder`, `replenishment`, `watchlist`

### GMV influence

Не путать с “полностью атрибутированная выручка”.

Считать:

- `attributed GMV`
- `assisted GMV`
- `attach GMV`

Определения:

- `attributed GMV`: заказ/позиция связаны с recommendation attribution chain
- `assisted GMV`: рекомендация была до покупки, но не была последним кликом
- `attach GMV`: дополнительная выручка от cross-sell к базовой корзине

### Coverage

Считать:

- доля eligible requests, где section вообще отрисован
- доля eligible requests, где section непустой
- доля SKU-каталога, которые вообще получают exposure в recommendations
- user coverage: доля активных пользователей, которые видели персональные sections

### Diversity

Считать:

- seller diversity
- brand diversity
- category diversity
- source diversity

Метрики:

- unique sellers / 1000 impressions
- unique brands / 1000 impressions
- средний `intra-list diversity`
- доля листов, где один seller занимает > `50%`

### Novelty

Считать:

- доля рекомендованных товаров, которых пользователь ещё не видел
- доля рекомендованных товаров, которых не было в прошлых `N` заказах
- доля exposure из long-tail против head SKUs

Зачем:

- рекомендация без новизны превращается в повторение текущего каталога или истории

### Empty-rate

Формула:

- `empty section responses / eligible requests`

Разрезы:

- `surface`
- `section`
- `source`
- `variant`

### Fallback-rate

Формула:

- `django-inline-fallback / all fastapi-eligible requests`

Разрезы:

- `surface`
- `section`
- `service`

## 3.2. Нормы и пороги для продуктовых метрик

Это не универсальные продуктовые KPI, а operational guardrails для platform rollout.

### Guardrails

- `CTR`: падение против baseline не более `10%`
- `add-to-cart rate`: падение не более `10%`
- `CVR`: падение не более `12%`
- `repeat purchase uplift`: не хуже baseline более чем на `10%`
- `GMV influence`: не хуже baseline более чем на `12%`
- `empty-rate`: не выше `5%` для обязательных sections
- `fallback-rate`: `< 1% / 15m`, `< 0.1% / 24h`
- `coverage`: не ниже `django-inline - 5pp`
- `diversity`: не хуже baseline более чем на `15%`
- `novelty`: не хуже baseline более чем на `10%`

## 4. Технические метрики platform-уровня

## 4.1. Request/serving metrics

### Latency

Считать:

- `p50`
- `p95`
- `p99`

Разрезы:

- `surface`
- `section`
- `source`
- `variant`
- `service`

Рекомендованные budget’ы:

- `home`, `cart`, `checkout`: `p95 <= 0.7s`
- `pdp`, `reorder`, `catalog recovery`: `p95 <= 0.8s`
- internal service hop: `p95 <= 250ms`

### Error-rate

Считать:

- share of non-2xx responses
- malformed payload share
- serialization/normalization errors
- internal exceptions by service mode

### Timeout-rate

Считать отдельно:

- transport timeouts
- downstream backend/API timeouts
- scoring/ranker timeouts

### Cache hit-rate

Обязательные слои, где нужен cache visibility:

- materialized `RecommendationSet`
- feature snapshot cache
- section-level cache
- popular/replenishment snapshots

Если cache есть, но hit-rate не измеряется, значит cache operationally “слепой”.

Минимум:

- `cache_hits_total`
- `cache_misses_total`
- `cache_stale_total`
- `cache_fill_latency`

### Candidate-count

Нужно видеть:

- raw candidate count до ranking
- eligible candidate count после фильтров
- final selected count

Это уже частично покрывается `servio_recommendation_candidate_count`, но для platform QA нужно расширение по sections и source stage.

### Ranker input/output health

Нужно считать:

- пустые/аномальные feature vectors
- missing feature rate
- blocked product share
- filtered-out by stock share
- filtered-out by policy share
- selected list length
- duplicate product rate
- score distribution drift

### Feature store health

Для ML и hybrid ranking нужен мониторинг:

- freshness feature snapshots
- missing user snapshot rate
- missing product snapshot rate
- expired snapshot usage
- active model availability by surface
- model artifact status

## 4.2. Что уже есть и чего не хватает

### Уже есть

- `servio_recommendation_selections_total`
- `servio_recommendation_candidate_count`
- `servio_recommendation_events_total`
- `servio_recommendation_attributed_orders_total`
- `servio_recommendation_attributed_revenue_total`
- request-linked `RecommendationEvent`
- `request_id`, `variant`, `strategy`, `model_version`, `reason_codes`, `candidate_sources` в payload

### Пока не хватает

- latency histogram именно для recommendation surfaces
- fallback-rate metric как отдельная first-class метрика
- cache hit-rate
- ranker input/output health
- feature freshness dashboards
- section empty-rate dashboards
- retrieval/ranking stage split

## 5. Как валидировать релевантность и отслеживать деградацию качества

## 5.1. Offline relevance validation

Нужен golden набор:

- `50-100` PDP seeds
- `20-50` cart seeds
- `20-50` checkout seeds
- `20-50` reorder users
- `50+` home personas:
  - anonymous cold start
  - authenticated light buyer
  - repeat buyer
  - subscribed/watchlist-heavy

Для каждого кейса проверять:

- section coverage
- top-N overlap с baseline
- reason-code plausibility
- stock/status validity
- novelty
- diversity
- no duplicates

### Relevance review rubric

Каждый лист оценивать по 4 шкалам:

- `relevance`
- `buyability`
- `diversity`
- `explainability`

Шкала:

- `0` — плохо
- `1` — сомнительно
- `2` — приемлемо
- `3` — хорошо

`Go` по offline relevance только если:

- средняя оценка `>= 2.2`
- доля кейсов с оценкой `< 2` не выше `10%`

## 5.2. Online degradation monitoring

Качество recommendation platform деградирует по-разному. Нужно отслеживать не один KPI, а набор сигналов:

- `CTR drift`
- `ATC drift`
- `CVR drift`
- `GMV influence drift`
- `coverage drift`
- `empty-rate drift`
- `fallback-rate drift`
- `diversity drift`
- `novelty drift`
- `stock-availability drift`

### Принцип

Нельзя считать quality деградацией только падение CTR.  
CTR может расти, если блок стал слишком “кликбейтным”, но CVR и GMV influence падают.

### Минимальный набор detection правил

- рост `CTR` при падении `ATC/CVR` -> проблема labeling/UI bait или нерелевантного ranking
- рост `coverage`, но падение `CTR` и `diversity` -> retrieval стал слишком широким и однообразным
- рост `empty-rate` и `fallback-rate` -> retrieval/service issue
- рост `CTR`, но purchase без изменений -> UI placement есть, продуктовая ценность низкая
- падение `CVR` только на out-of-stock heavy segments -> stock contamination

## 6. Как строить dashboards для recommendation surfaces

## 6.1. Принцип

Нужен не один “recommendations overview”, а набор связанных dashboards:

1. `Executive / product impact`
2. `Surface performance`
3. `Serving / platform health`
4. `Retrieval / ranking diagnostics`
5. `Experiment / variant dashboard`

## 6.2. Executive dashboard

Что показывать:

- impressions
- clicks
- add-to-cart
- purchases
- attributed GMV
- attach GMV
- repeat purchase uplift
- coverage
- empty-rate

Разрезы:

- `surface`
- `section`
- `variant`
- `source`

## 6.3. Surface performance dashboard

Отдельные табы или панели по:

- `home`
- `pdp`
- `cart`
- `checkout`
- `reorder`
- `catalog recovery`

Панели:

- impressions
- CTR
- add-to-cart rate
- CVR
- average position click curve
- section fill-rate
- unique products / brands / sellers
- stock share

## 6.4. Serving/platform dashboard

Показывать:

- availability
- p50/p95/p99 latency
- error-rate
- timeout-rate
- fallback-rate
- service mode split
- health/readiness
- internal dependency failures

## 6.5. Retrieval/ranking diagnostics dashboard

Показывать:

- candidate count by source stage
- selected count
- duplicate rate
- blocked/policy filtered rate
- out-of-stock filtered rate
- score distribution
- feature snapshot freshness
- active model version
- reason code distribution
- candidate source distribution

## 6.6. Experiment dashboard

Показывать:

- traffic split by variant
- sample ratio mismatch
- CTR / ATC / CVR by variant
- GMV influence by variant
- novelty/diversity by variant
- latency and fallback by variant

## 7. Как отличать retrieval / ranking / UI placement / labeling / stock проблемы

## 7.1. Retrieval problem

Сигналы:

- высокий `empty-rate`
- низкий `candidate-count`
- резкая просадка coverage
- одинаковые SKU на многих surfaces
- poor diversity уже до ranking

Смысл:

- мы не нашли достаточный пул кандидатов

## 7.2. Ranking problem

Сигналы:

- candidate-count нормальный, а CTR/CVR падают
- топ позиций нерелевантны, низ позиции “лучше” топа
- score distribution drift
- overlap с baseline сильно падает без изменения retrieval

Смысл:

- хорошие кандидаты есть, но ранжируются плохо

## 7.3. UI placement problem

Сигналы:

- section fill-rate нормальный
- relevance review нормальный
- latency нормальная
- но impression -> click низкий именно на конкретной странице/позиции

Что смотреть:

- ниже ли fold
- перекрывается ли sticky UI
- слишком ли поздно загружается блок
- отличается ли mobile/desktop

## 7.4. Labeling problem

Сигналы:

- section технически работает
- CTR отличается между одинаковыми товарами при разном title/subtitle/source-label
- клики есть, но add-to-cart слабый

Смысл:

- пользователь не понимает, почему ему это показывают, или title обещает одно, а товары про другое

## 7.5. Stock problem

Сигналы:

- CTR нормальный, add-to-cart или purchase падают
- высокий share `stock_qty <= 0`
- рост lead time / MOQ friction
- падение только у sections с inventory-sensitive товарами

Смысл:

- рекомендация релевантна, но не buyable

## 7.6. Краткая диагностическая матрица

- `empty-rate ↑`, `candidate-count ↓` -> retrieval
- `candidate-count ok`, `CTR/CVR ↓`, overlap ↓ -> ranking
- `impressions ok`, `CTR ↓`, только на одном placement -> UI placement
- `CTR weird`, `ATC/CVR ↓`, titles отличаются -> labeling
- `CTR ok`, `ATC/purchase ↓`, stock share ↑ -> stock

## 8. A/B test prerequisites

A/B для recommendation platform нельзя запускать “просто потому что есть variant”.

## 8.1. Обязательные prerequisites

- стабильный event contract:
  - `recommendation_impression`
  - `recommendation_click`
  - `add_to_cart`
  - `purchase`
  - `recommendation_dismiss`
- обязательные поля в событиях:
  - `request_id`
  - `surface`
  - `recommendation_source`
  - `experiment_variant`
  - `strategy`
  - `model_version`
  - `item_id`
  - `position`
- единый assignment logic без sample ratio mismatch
- no silent fallback between variants
- power analysis и минимальный ожидаемый эффект
- guardrail metrics определены заранее
- holdout/control сохраняется
- отдельный план rollback

## 8.2. Что должно быть запрещено

- запускать A/B без impression event
- запускать A/B без purchase linkage
- смешивать одновременно изменения retrieval, ranking и UI placement без factor design
- менять title/placement и ranking в одном непрозрачном эксперименте
- запускать variant, если fallback-rate у него уже нестабилен

## 8.3. Минимальный набор guardrails для A/B

- latency
- fallback-rate
- empty-rate
- CTR
- add-to-cart rate
- CVR
- attributed GMV
- diversity
- stock share

## 9. Go/No-Go зрелость по этапам 1/2/3

## 9.1. Этап 1 — Foundation / instrumentation readiness

### Что считается зрелостью

- все surfaces и sections описаны единообразно
- есть impression/click/add_to_cart/purchase telemetry
- есть request-level attribution
- есть базовые counters по selection/events/orders/revenue
- можно руками восстановить path от section до заказа

### Go

- события полные и стабильные
- section keys и source naming не хаотичны
- basic dashboards есть
- можно считать CTR, ATC, CVR, coverage, empty-rate

### No-Go

- нет stable impression tracking
- нет request_id linkage
- нет purchase attribution
- источники и section keys плавают между релизами

## 9.2. Этап 2 — Platform observability readiness

### Что считается зрелостью

- есть serving dashboard
- есть retrieval/ranking diagnostics
- видны fallback, latency, candidate-count, empty-rate
- можно отделить retrieval issue от ranking issue
- есть baseline и drift monitoring

### Go

- p95/p99 и fallback наблюдаемы
- есть recommendation-specific alerts
- cache/feature freshness видны
- есть quality guardrails по каждому surface

### No-Go

- recommendation latency/error-rate не видны
- нет diagnostics stage split
- нет alerting для empty/fallback/CTR/CVR drift
- деградацию можно заметить только по жалобам или падению заказов

## 9.3. Этап 3 — Experimentation / rollout readiness

### Что считается зрелостью

- есть корректный variant assignment
- есть power-ready event model
- есть holdout/control
- можно запускать canary и A/B без слепых зон
- full cutover контролируется по business guardrails

### Go

- `A/B prerequisites` из раздела 8 выполнены
- offline relevance и online guardrails зелёные
- fallback-rate стабилен
- ranking/retrieval changes можно проверять независимо
- есть clear rollback runbook

### No-Go

- variant assignment нестабилен
- sample ratio mismatch не отслеживается
- business guardrails не посчитаны
- UI, ranking и retrieval смешаны в одном тесте
- нет уверенности, что uplift/просадка вызваны именно recommendation platform

## 10. Честный текущий статус Servio

### Уже хорошо

- recommendation platform в коде уже разделена на:
  - retrieval
  - ranking
  - scoring contract
  - experiments
  - feature store
  - attribution
- есть `RecommendationEvent`
- есть `strategy`, `variant`, `model_version`, `reason_codes`, `candidate_sources`
- есть order attribution и session linkage

### Пока слабо

- нет recommendation-specific dashboards уровня search funnel
- нет зрелого alerting по recommendation quality
- нет отдельной метрики latency/fallback/empty-rate как first-class standard
- нет платформенного parity/quality job для recommendations
- cache hit-rate и ranker input/output health пока operationally слепые

### QA verdict

Recommendation platform уже вышла из стадии “просто блока на странице”, но ещё не вышла в стадию полной измеримости как бизнес-система.  
До Stage 3 нужны dashboards, alerting, drift detection и diagnostics по retrieval/ranking/stock/UI.

