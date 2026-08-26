# Recommendation Platform Audit / Roadmap

Дата: 2026-03-28
Пакет: backlog `052` + часть `054`
Область: recommendation platform

## 1. Executive assessment

### Что уже хорошо

- В `backend/shopfront/recommendation/*` уже есть не пустая recommendation-система, а рабочий движок:
  `candidate generation`, `ranking`, `feature snapshots`, `materialized sets`, `surface contracts`, `tasks`, `attribution`, `Prometheus metrics`.
- Система уже умеет обслуживать несколько поверхностей:
  `home`, `product`, `cart`, `checkout`, `reorder`, `search recovery`.
- Есть дисциплина по контрактам:
  внутренние и публичные recommendation endpoints разделены, есть `contracts.py`, режимы `django-inline` и `fastapi`.
- Есть базовая observability:
  `recommendation_selection`, `recommendation_event`, attributed orders/revenue, trace fields в payload.
- Есть ML scaffold:
  `ml.py`, `scoring_service.py`, training tasks, model artifacts, gating по variant.

### Что является временной заглушкой

- `services/recommendation-api/app/main.py` пока не является полноценным recommendation platform service.
  По факту это bootstrap-scaffold с простыми секциями поверх catalog API и strategy `fastapi_bootstrap`.
- FastAPI recommendation service сейчас нельзя считать production-parity заменой Django recommendation engine.
- Часть recommendation surfaces в продуктовой подаче выглядит сильнее, чем их фактическая интеллектуальная база.

### Что является архитектурным долгом

- Recommendation logic, feature generation, materialization, contracts и serving всё ещё в основном сидят в Django-монолите.
- Нет полноценного выделенного recommendation serving plane с доказанной parity относительно Django.
- Нет потоковой event-платформы и near-real-time feature layer.
- Нет зрелого experimentation layer для decisioning, а не только variant bucket.
- Документы и код уже начинают расходиться:
  platform docs описывают более зрелую FastAPI story, чем реально реализовано в recommendation service.

### Что вводит пользователя и бизнес в заблуждение

- Нельзя выдавать многие текущие surfaces за "настоящую персонализацию", если они собраны из:
  `popular`, `watchlist`, `reorder`, `favorites`, `recently viewed`, `materialized heuristics`.
- `ranked_v2` это heuristic reranking, а не полноценный ML ranker.
- Наличие `ml_v1` в коде не означает, что продукт уже работает как зрелая personalized recommendation platform.
- Формулировки вида "для вас" допустимы только там, где реально доказан user-specific signal contribution, а не просто cold-start/popularity blend.

### Почему это далеко от Amazon-like stack

- Нет online feature store.
- Нет streaming event backbone.
- Нет multi-stage retrieval stack с независимыми candidate generators.
- Нет зрелого ranking/re-ranking pipeline с отдельными latency budgets и SLO.
- Нет industrial experimentation platform.
- Нет доказанной модели управления GMV/CTR/ATC/CVR/repeat purchase на уровне platform loops.
- Нет независимого production-grade recommendation service, который реально является owner serving path.

Вывод:
текущая система годится как marketplace recommendation foundation, но не как Amazon-like recommendation platform. Это хорошая база, но не тот уровень, который можно честно продавать как зрелую персонализацию.

## 2. Оценка зрелости

| Измерение | Оценка | Комментарий |
| --- | --- | --- |
| Product maturity | 2.5 / 5 | Surface coverage есть, но value доказан не по всем зонам и часть UX-labeling завышает интеллектуальность системы |
| Architecture maturity | 3 / 5 | В Django есть реальная модульность, но serving plane и ownership ещё не выделены до конца |
| Load readiness | 2 / 5 | Batch/materialized модель есть, но нет доказанной высокой независимой отказоустойчивости recommendation serving |
| A/B tests maturity | 1.5 / 5 | Есть variant gating, но нет зрелой платформы экспериментов, статистической дисциплины и rollout governance |
| Personalization maturity | 2 / 5 | Есть user-aware heuristics и feature snapshots, но это ещё не strong personalized recommender |
| Observability maturity | 3 / 5 | Метрики и атрибуция есть, но нужны parity dashboards, service SLO и жёсткая склейка с cutover governance |

## 3. Gap analysis

| Текущая возможность | Проблема | Влияние на бизнес | Приоритет | Owner |
| --- | --- | --- | --- | --- |
| Recommendation surfaces уже работают в Django | FastAPI recommendation service не parity-ready | Риск ложного cutover и продуктового проседания | P0 | architect + backend |
| Есть heuristic ranking | Heuristics местами подаются как personalization | Потеря trust и неверные управленческие ожидания | P0 | uiux + frontend + architect |
| Есть ML scaffold | ML не является системно доминирующим serving path | Нельзя обещать ML-driven uplift | P0 | backend |
| Есть internal/public contracts | Документы и реализация расходятся | Риск неверных решений по платформе и rollout | P0 | architect |
| Есть attribution и metrics | Нет platform-grade KPI dashboard по surfaces и variants | Сложно принимать решения по cutover и развитию | P0 | qa_metrics |
| Есть candidate sources | Нет явной платформенной карты candidate generation tiers | Невозможно прозрачно управлять recall/relevance | P1 | backend |
| Есть batch tasks | Нет near-real-time event/feature loop | Слабая реакция на свежие сигналы пользователя | P1 | backend + devops |
| Есть contracts.py fallback | Ownership serving path ещё размазан | Сложнее rollback и incident response | P1 | architect + devops |
| Есть surface-specific logic | Нет строгой taxonomy бизнес-правил и merchandising constraints | Риск нерелевантных или коммерчески вредных выдач | P1 | backend + uiux |
| Есть selection metrics | Нет полного experiment governance | Сложно валидировать uplift по CTR/ATC/CVR/GMV | P1 | qa_metrics |
| Есть internal recommendation APIs | Нет чёткой public/internal OpenAPI карты для recommendation platform | Рост интеграционного хаоса | P1 | architect + backend |
| Есть dismissed products policy | Нет сильного user control layer и trust UX | Потеря доверия к рекомендациям | P2 | uiux + frontend |

## 4. Целевая архитектура

### 4.1 Data sources

- Orders
- Cart events
- Checkout events
- Product views
- Search events
- Favorites / watchlist
- Brand/category subscriptions
- Catalog metadata
- Seller metadata
- Inventory / stock / lead time
- Pricing / promo state

### 4.2 Event tracking

- Единая taxonomy recommendation events:
  `impression`, `click`, `add_to_cart`, `checkout_start`, `order_attributed`, `dismiss`, `hide`, `conversion_window_expired`.
- Обязательные поля:
  `request_id`, `surface`, `section`, `variant`, `strategy`, `model_version`, `candidate_source`, `reason_codes`, `user_id/session_id`, `product_id`, `seller_id`.
- Источник истины по events:
  backend + analytics pipeline, без разрыва между frontend payload и backend attribution.

### 4.3 Feature generation

- Offline batch features:
  popularity, co-view, co-purchase, replenishment, user-category affinity, user-brand affinity, seller affinity.
- Nearline features:
  session intent, recent search intent, recent cart intent, recent product chain.
- Online features:
  минимальный phase-2 target, полноценный phase-3 target.

### 4.4 Candidate generation

- Surface-specific candidate generators:
  `home`, `pdp similar`, `pdp substitute`, `cart cross-sell`, `checkout attach`, `reorder`, `search recovery`.
- Candidate sources:
  materialized sets, collaborative signals, content similarity, seller substitution, popularity, replenishment, session intent.
- Каждый source должен иметь:
  owner, freshness SLA, recall target, fallback policy.

### 4.5 Ranking

- Stage 1:
  deterministic candidate blending + stronger heuristic ranker + explainability.
- Stage 2:
  learning-to-rank / marketplace-aware model.
- Stage 3:
  separate ranker and re-ranker with business policy layer.

### 4.6 Re-ranking

- Diversity by seller / brand / category.
- Inventory and fulfillment guardrails.
- Price band and MOQ sanity.
- Overshow control.
- User trust filters:
  hidden products, low stock traps, stale offers.

### 4.7 Business rules

- Не рекомендовать то, что нельзя быстро купить.
- Не продавливать промо в ущерб базовой релевантности.
- Ограничивать seller dominance.
- Явно отделять "популярное" от "для вас".
- Не выдавать внутренние fallback-гипотезы за personalization.

### 4.8 Experimentation

- Единая surface/variant registry.
- Rollout flags.
- Holdout cohorts.
- KPI dashboard:
  `CTR`, `ATC`, `CVR`, `GMV`, `repeat purchase`, `dismiss rate`, `trust proxy metrics`.
- Shadow mode и canary для platform changes.

### 4.9 Observability

- Service SLO по latency/error/fallback rate.
- Parity dashboards между Django и FastAPI.
- Candidate volume / empty rate / attributed GMV dashboards.
- Alerting по:
  empty surfaces, zero-attribution drift, latency spikes, fallback explosion, contract mismatch.

## 5. Roadmap в 3 этапа

### Этап 1. MVP cleanup

Цель:
перестать врать себе и продукту о текущем уровне recommendation platform.

Что делаем:

- Сводим код, документы и naming к одной правде.
- Формально фиксируем:
  что в recommendation реально heuristic, что personalized, что bootstrap.
- Выносим ложные claims из UX и продуктовых формулировок.
- Замораживаем surface contracts.
- Делаем FastAPI recommendation service честным:
  либо proxy/parity layer к Django internal contracts,
  либо официально оставляем bootstrap-only и не используем как primary serving path.
- Собираем platform KPI dashboard.
- Фиксируем owners и rollback owner.

Ожидаемый результат:
управляемая, честная и наблюдаемая recommendation foundation без ложной зрелости.

### Этап 2. Strong marketplace recommender

Цель:
довести систему до сильного marketplace recommender, который реально влияет на CTR / ATC / CVR / GMV.

Что делаем:

- Нормализуем candidate generators по surfaces.
- Усиливаем user/item/seller features.
- Строим устойчивый ranking contract между Django и FastAPI.
- Запускаем FastAPI recommendation serving в shadow -> canary -> partial rollout.
- Добавляем real experiment governance.
- Вводим business-rule layer и explainability discipline.
- Делаем surface-by-surface uplift measurement.

Ожидаемый результат:
система уже не "набор умных эвристик", а сильный marketplace recommender с измеримым эффектом.

### Этап 3. Near-Amazon architecture

Цель:
построить recommendation platform высокого класса, но только после доказанной бизнес-пользы этапа 2.

Что делаем:

- Вводим streaming events backbone.
- Строим online feature store.
- Делаем multi-stage retrieval / ranking / re-ranking.
- Добавляем embeddings / ANN / session-aware models там, где это даёт прибыль, а не ради AI.
- Строим platform-grade experiment stack и policy engine.
- Разводим independent service SLO и operational ownership.

Ожидаемый результат:
масштабируемая recommendation platform enterprise-уровня, близкая по архитектурной дисциплине к Amazon-like stack, но только после доказанного product fit.

## 6. Agent task board

| Агент | Зона ответственности | Ближайший пакет |
| --- | --- | --- |
| architect | truth model, contract map, ownership, rollout gates | Зафиксировать единую recommendation truth map и убрать docs/code drift |
| backend | Django engine, internal contracts, ranking, feature generation | Привести recommendation engine и FastAPI parity path к одной модели serving |
| devops | service topology, deploy, observability, rollback | Поднять rollout-safe recommendation service path с SLO, flags и parity dashboards |
| qa_metrics | KPI, parity, experiments, attribution quality | Настроить dashboards и gating по `CTR/ATC/CVR/GMV/fallback/empty rate` |
| frontend | surface instrumentation, honest labeling, payload integrity | Убрать ложную персонализацию из UI и выровнять telemetry payload |
| uiux | wording, placement, trust, user control | Переписать recommendation UX так, чтобы "popular" и "for you" не смешивались |

## 7. Definition of Done по этапам

### DoD — Этап 1

- Документы и код больше не противоречат друг другу.
- Для каждой recommendation surface есть owner, contract и truth label.
- FastAPI recommendation service либо parity-capable proxy, либо официально bootstrap-only.
- В UI нет ложных claims о персонализации.
- Есть единый KPI dashboard по surfaces и variants.
- Есть rollback-ready cutover policy.

### DoD — Этап 2

- FastAPI recommendation serving прошёл shadow/parity и частичный rollout.
- Есть измеримый uplift или не хуже baseline по ключевым business metrics.
- Candidate generation и ranking contracts стандартизованы.
- Experiment governance работает не формально, а операционно.
- Recommendation incidents и degradations видны в observability до жалоб бизнеса.

### DoD — Этап 3

- Event pipeline и feature platform работают в near-real-time там, где это оправдано.
- Multi-stage recommendation stack даёт стабильный business uplift.
- Service ownership, SLO, rollback и experimentation соответствуют platform-grade уровню.
- Система управляет не только CTR, но и downstream quality:
  `ATC`, `CVR`, `GMV`, `repeat purchase`, `trust`.

## Финальный вывод

Servio уже имеет рабочее recommendation ядро, но это ещё не recommendation platform высокого класса.

Главная управленческая проблема сейчас не в отсутствии кода, а в расхождении между:

- фактической зрелостью Django recommendation engine,
- уровнем честности продуктовых формулировок,
- и тем, как платформа описана в FastAPI roadmap-документах.

Приоритет №1:
навести правду, ownership и parity discipline.

Без этого любой разговор про "персонализацию" и "FastAPI cutover" будет не инженерным управлением, а самообманом.
