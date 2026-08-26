# FastAPI Search / Recommendation Cutover Plan

Дата: 2026-03-28  
Роль: `architect`

## 1. Цель

Подготовить безопасный parity/cutover план для вынесения `search` и `recommendations` из Django-монолита Servio в отдельные FastAPI-сервисы без поломки storefront, seller flows, checkout и platform API.

Задача плана:

- описать shadow mode
- определить parity metrics
- зафиксировать rollout stages
- зафиксировать rollback criteria
- развести ownership границ
- определить blocking и non-blocking сигналы

Главный принцип:

- `search` и `recommendations` режутся не одновременно
- `Django/DRF` остаётся public API owner и fallback path
- cutover идёт через измеряемую parity, а не через “включили и посмотрим”

## 2. Базовая рамка cutover

Целевая схема:

1. Браузер / Next / storefront BFF обращается в `Django`.
2. `Django` вызывает внутренний `FastAPI search service` или `FastAPI recommendation service`.
3. `FastAPI` возвращает `ids + metadata`.
4. `Django` гидрирует canonical данные и формирует публичный response.

Это означает:

- public contract не меняется на первом этапе
- пользовательский трафик не знает о внутреннем разрезании
- rollback остаётся в `Django`

## 3. Ownership границ

### Django / DRF owner

Владение остаётся здесь:

- auth / session / permissions
- users / commerce / orders / checkout
- catalog как source of truth
- storefront bridge и public API
- analytics ingest с браузера
- session/order attribution
- fallback implementation search/reco

### FastAPI Search owner

Владение у search service:

- query normalization
- rewrites / suggestions
- retrieval against OpenSearch
- facet aggregation
- search ranking metadata
- service health / readiness / internal docs

### FastAPI Recommendation owner

Владение у recommendation service:

- candidate generation
- ranking / reranking
- personalization
- model versioning
- reason codes / explainability metadata
- internal recommendation events ingest для learning loops

### QA / Metrics owner

Владение:

- parity dashboards
- sampled diff analysis
- rollout readiness gates
- business metric comparison

### DevOps owner

Владение:

- deployment topology
- routing / service discovery
- timeout / retry policy
- dashboards / alerts / rollback runbook

## 4. Shadow mode

Shadow mode обязателен и идёт отдельно для `search` и `recommendations`.

### 4.1. Search shadow mode

`Django`:

- продолжает отвечать пользователю старым search path
- параллельно отправляет тот же internal request в FastAPI search service
- сохраняет diff между:
  - `product_ids`
  - `suggestions`
  - `facets`
  - `rewrite_kind`
  - `provider`
  - latency

Важное ограничение:

- shadow result не влияет на user response
- shadow не должен ломать latency пользовательского запроса
- если shadow call падает, пользовательский path остаётся успешным

### 4.2. Recommendation shadow mode

`Django`:

- продолжает отдавать рекомендации из текущего `shopfront/recommendation/*`
- параллельно вызывает FastAPI recommendation service
- сравнивает:
  - `product_ids`
  - `reason_codes`
  - `variant`
  - `strategy`
  - `candidate_count`
  - latency

### 4.3. Где сохранять diff

Минимально:

- structured logs
- Prometheus counters / histograms
- sampled parity payloads в короткоживущем storage или таблице аудита

Shadow mode должен быть:

- sampling-based
- surface-aware
- отключаемым по feature flag

## 5. Parity metrics

## 5.1. Search parity metrics

Технические:

- `search_shadow_requests_total`
- `search_shadow_errors_total`
- `search_shadow_latency_delta_ms`
- `search_top_k_overlap@5`
- `search_top_k_overlap@10`
- `search_zero_results_delta`
- `search_suggestions_overlap`
- `search_facets_presence_delta`
- `search_rewrite_kind_match_rate`

Продуктовые:

- CTR search results
- zero-results rate
- add-to-cart after search
- order attribution from search
- search abandonment rate

## 5.2. Recommendation parity metrics

Технические:

- `reco_shadow_requests_total`
- `reco_shadow_errors_total`
- `reco_shadow_latency_delta_ms`
- `reco_top_k_overlap@5`
- `reco_top_k_overlap@10`
- `reco_candidate_count_delta`
- `reco_reason_code_presence_rate`
- `reco_empty_surface_delta`

Продуктовые:

- recommendation CTR
- add-to-cart from reco
- reorder conversion
- attributed orders
- attributed revenue
- dismiss rate

## 5.3. Почему parity не равно identity

Для `recommendations` и `search` нельзя требовать 100% совпадения выдачи.

Нужно требовать:

- контролируемое расхождение
- объяснимость
- отсутствие деградации бизнес-сигналов

Иначе мы просто зацементируем старую реализацию вместо перехода на новый serving layer.

## 6. Rollout stages

## 6.1. Общий порядок

Сначала `search`, потом `recommendations`.

Запрещено:

- одновременный полный cutover двух сервисов
- cutover без shadow parity
- cutover без горячего rollback path

## 6.2. Search rollout stages

### Stage 0. Contract freeze

- фиксируем internal request/response schema
- фиксируем timeout budget
- фиксируем parity metrics

### Stage 1. Shadow 0%

- 0% user impact
- sampled duplicate calls
- dashboards и diff logs

### Stage 2. Read-only canary

Включаем FastAPI search для ограниченного набора surfaces:

- live search suggestions
- search suggestions API

User impact:

- низкий
- быстро откатывается

### Stage 3. Catalog/search canary

- 1–5% трафика на `/search` и `catalog query surfaces`
- `Django fallback` остаётся активным

### Stage 4. Search partial rollout

- 10% -> 25% -> 50%
- переход только при прохождении parity и business gates

### Stage 5. Search primary

- 100% serving from FastAPI search
- `Django` fallback path остаётся живым

## 6.3. Recommendation rollout stages

### Stage 0. Contract freeze

- фиксируем internal reco schemas
- фиксируем parity metrics по surfaces

### Stage 1. Shadow 0%

- sampled duplicate recommendation calls
- diff logging по surfaces

### Stage 2. Low-risk surfaces

Начинаем с:

- `home`
- `search recovery`
- non-critical PDP sections

Не начинаем с:

- checkout recommendations
- reorder-critical flows

### Stage 3. PDP / cart canary

- 1–5% surfaces
- only selected blocks

### Stage 4. Reco partial rollout

- 10% -> 25% -> 50%
- отдельно по surface, а не глобально

### Stage 5. Reco primary

- 100% serving from FastAPI recommendation
- `Django` fallback path остаётся

## 7. Rollback criteria

Rollback должен быть:

- мгновенным через feature flags
- отдельным для `search` и `recommendations`
- отдельным по surface

## 7.1. Search rollback criteria

Немедленный rollback:

- `5xx` rate выше baseline более чем на `+0.5 pp`
- `p95 latency` выше SLO или рост больше `+150ms`
- `zero-results rate` хуже baseline больше чем на `10% relative`
- `top_k_overlap@10` устойчиво ниже `0.55`
- search CTR падает больше чем на `5%`
- add-to-cart after search падает больше чем на `5%`

## 7.2. Recommendation rollback criteria

Немедленный rollback:

- `5xx` rate выше baseline более чем на `+0.5 pp`
- `empty recommendation surfaces` растут более чем в `2x`
- recommendation CTR падает больше чем на `7%`
- attributed orders / revenue падают больше чем на `5%`
- reorder path показывает заметный рост `none|partial` outcomes
- candidate_count collapse на ключевых surfaces

## 7.3. Rollback horizon

Rollback decision должен приниматься:

- на canary — в течение минут / часов
- на partial rollout — в течение часов
- на 100% rollout — в течение одного операционного окна

Нельзя ждать “несколько дней”, если блокирующий сигнал уже устойчиво горит.

## 8. Блокирующие сигналы

Блокирующими считаем:

- рост `5xx`
- рост timeout / saturation
- zero-results spike в search
- empty surfaces spike в recommendations
- CTR / add-to-cart / attributed revenue деградация выше agreed threshold
- broken fallback path
- broken traceability: нет `request_id`, нет parity logs, нет объяснимости diff
- divergence без объяснения на ключевых surfaces
- несоблюдение source-of-truth границы

Также блокирующим считаем:

- невозможность быстро откатить traffic
- потерю same-origin analytics ingest связи с order attribution

## 9. Неблокирующие сигналы

Неблокирующими считаем:

- неполный `top_k` identity при сохранении бизнес-метрик
- minor suggestion wording drift
- small latency delta, если SLO не нарушен
- minor reason-code distribution drift
- расхождение rank order внутри top-10 при стабильных CTR/conversion
- разница по отдельным long-tail queries без массовой деградации

Неблокирующее не значит “игнорируем”.

Это означает:

- фиксируем
- наблюдаем
- добавляем в backlog
- не останавливаем rollout автоматически

## 10. Практический план внедрения

### Шаг 1. Search cutover track

- подготовить internal search contract
- поднять search shadow mode
- измерить parity на sampled traffic
- включить low-risk canary
- довести до primary serving с живым Django fallback

### Шаг 2. Recommendation cutover track

- подготовить internal reco contract
- поднять recommendation shadow mode
- начать с low-risk surfaces
- двигаться surface-by-surface
- довести до primary serving с живым Django fallback

### Шаг 3. Operations hardening

- dashboards
- alerts
- runbooks
- feature flags
- fallback drills

### Шаг 4. Decommission decision

Старый Django-internal serving path нельзя удалять сразу после cutover.

Удаление возможно только после:

- стабильного окна работы
- пройденных rollout stages
- отсутствия blocking signals
- подтверждённой observability completeness

## Короткий вывод

Правильный cutover для Servio выглядит так:

- `search` и `recommendations` режутся отдельно
- сначала shadow mode
- потом canary
- потом staged rollout
- rollback держится в Django
- блокирующие сигналы завязаны не только на latency/error rate, но и на business metrics

Главная инженерная граница:

- `FastAPI` становится serving engine
- `Django` остаётся public owner, policy owner и rollback owner
