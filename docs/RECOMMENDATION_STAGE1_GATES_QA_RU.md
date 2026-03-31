# Recommendation Stage 1 QA Gates

Дата: 2026-03-28  
Роль: `qa_metrics`  
Пакет: backlog `065`

## 1. Цель

Зафиксировать Stage 1 gates для recommendation platform так, чтобы можно было честно закрыть `MVP cleanup` и не перепутать его с Stage 2 зрелостью.

Этот документ дополняет:

- [RECOMMENDATION_STAGE1_TRUTH_MODEL_RU.md](./RECOMMENDATION_STAGE1_TRUTH_MODEL_RU.md)
- [RECOMMENDATION_STAGE1_LABEL_MATRIX_RU.md](./RECOMMENDATION_STAGE1_LABEL_MATRIX_RU.md)
- [RECOMMENDATION_STAGE1_CONTRACT_BASELINE_RU.md](./RECOMMENDATION_STAGE1_CONTRACT_BASELINE_RU.md)

## 2. Stage 1 dashboards/spec

### 2.1. Executive dashboard

Цель: увидеть, не врет ли платформа сама себе.

Обязательные панели:

- `recommendation surfaces coverage`
- `CTR / ATC / CVR` по `surface` и `section`
- `attributed GMV` и `assisted GMV`
- `empty-rate`
- `fallback-rate`
- `forbidden labels / truth violations`

### 2.2. Surface dashboard

Цель: управлять качеством по каждой recommendation surface.

Разрезы:

- `surface`
- `section_key`
- `recommendation_source`
- `variant`
- `strategy`
- `source`

Обязательные графики:

- `impression count`
- `click count`
- `add_to_cart count`
- `purchase count`
- `CTR`
- `ATC rate`
- `CVR`
- `empty-rate`
- `candidate_count`
- `selected_count`
- `coverage`

### 2.3. Serving dashboard

Цель: видеть runtime здоровье recommendation serving.

Обязательные графики:

- `p50 / p95 / p99 latency`
- `error-rate`
- `timeout-rate`
- `fallback-rate`
- `cache hit-rate`
- `partial response rate`
- `service mode split`

### 2.4. Parity dashboard

Цель: сравнивать `django-inline` и `fastapi` без самообмана.

Обязательные проверки:

- `top-k overlap`
- `empty/non-empty parity`
- `section label parity`
- `source / strategy parity`
- `latency delta`
- `fallback delta`

### 2.5. Experiment dashboard

Цель: держать Stage 1 готовым к Stage 2 shadow/canary.

Обязательные панели:

- `variant split`
- `holdout share`
- `exposure per variant`
- `surface-level uplift`
- `sample size`
- `statistical stability`

## 3. Метрики, thresholds, alerts

### 3.1. Hard blockers

Любой из пунктов ниже блокирует закрытие Stage 1:

- `forbidden labels > 0`
- `recommendation contract fields missing > 0`
- `empty-rate > 5%` для обязательных секций
- `fallback-rate > 1% / 15m`
- `fallback-rate > 0.1% / 24h`
- `p95 latency > 700ms` для `home`, `cart`, `checkout`
- `p95 latency > 800ms` для `pdp`, `reorder`, `catalog recovery`
- `error-rate > 1%`
- `timeout-rate > 0.5%`
- `malformed payloads > 0`
- `contract / analytics linkage mismatch > 0`

### 3.2. Product guardrails

Stage 1 считается здоровым только если относительно baseline:

- `CTR` не падает больше чем на `10%`
- `ATC rate` не падает больше чем на `10%`
- `CVR` не падает больше чем на `12%`
- `attributed GMV` не падает больше чем на `12%`
- `coverage` не ниже baseline более чем на `5pp`
- `diversity` не проседает больше чем на `15%`
- `novelty` не проседает больше чем на `10%`

### 3.3. Alerts

Обязательные alert rules:

- `contract fields missing`
- `forbidden label detected`
- `fallback spike`
- `empty required section`
- `latency p95 breach`
- `timeout spike`
- `error spike`
- `analytics linkage missing`
- `parity drift`

## 4. Parity checks

Stage 1 parity means, что `django-inline` и `fastapi` не обязаны быть идеальными близнецами, но обязаны быть предсказуемыми и объяснимыми.

### 4.1. Minimum parity checks

- contract schema parity: 100%
- required fields parity: 100%
- label parity: 100%
- empty/non-empty parity: разница не более `2pp`
- top-3 item overlap: не ниже `70%` для `home`, `pdp`, `cart`
- top-3 item overlap: не ниже `60%` для `search_recovery`
- source / strategy parity: 100% на уровне envelope
- analytics linkage parity: 100%

### 4.2. What is allowed to differ

- exact ordering внутри длинных листов
- score hints
- minor candidate tie-breaks
- latency

### 4.3. What is not allowed to differ

- обязательные поля envelope
- truth labels
- empty-state semantics
- fallback disclosure
- attribution linkage

## 5. Go / No-Go для Stage 1 closeout

### Go

Stage 1 можно закрывать, если:

- truth-model и label matrix утверждены
- contract baseline зелёный на targeted tests
- dashboards/spec описаны и согласованы
- alerts и parity checks определены
- forbidden labels = 0
- missing required fields = 0
- fallback и empty-state поведение прозрачно

### No-Go

Stage 1 нельзя закрывать, если:

- есть хотя бы один forbidden label
- contract payload теряет Stage 1 поля
- analytics linkage ломается
- parity drift не объяснён
- fallback превращается в silent replacement
- required surface пустой без честного empty state

## 6. Достаточно ли baseline для честного старта Stage 2

Да, для старта Stage 2 как `engineering track` и `shadow/canary preparation` текущего baseline достаточно.

Нет, для Stage 2 production rollout его пока недостаточно.

Честная формулировка такая:

- Stage 1 уже достаточно силён, чтобы начать Stage 2 workstream
- Stage 1 ещё недостаточно силён, чтобы считать Stage 2 безопасно включённым в production
- Stage 2 должен стартовать только после Stage 1 go и под `shadow` / `canary` дисциплиной

## 7. Итог

Stage 1 QA gates выполнены, если платформа:

- измеряется по surface/section/source/variant
- не врет labels и claims
- не теряет contract fields и attribution
- не скрывает fallback и empty states
- проходит parity checks на baseline уровне

Это и есть честная точка входа в Stage 2.
