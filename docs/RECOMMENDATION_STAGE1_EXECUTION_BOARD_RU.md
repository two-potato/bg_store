# Recommendation Stage 1 Execution Board

Дата: 2026-03-28  
Пакет: backlog `059`  
Цель: `MVP cleanup` recommendation platform

## 1. Что делаем в Stage 1

Синхронизируем правду между кодом, контрактами, UX-labeling и observability.

Stage 1 не про новый ML. Stage 1 про честную платформенную базу:

- фиксируем truth-model
- замораживаем section contracts
- убираем ложные claims из UI
- вводим event taxonomy
- поднимаем operational dashboards
- делаем FastAPI serving path прозрачным по режимам и fallback'ам

## 2. Задачи по ролям

| Роль | Задача | Deliverable | Зависимость |
| --- | --- | --- | --- |
| `architect` | Зафиксировать truth-model recommendation platform: что является heuristic, что materialized, что personalization, что bootstrap | `docs/RECOMMENDATION_STAGE1_TRUTH_MODEL_RU.md` или блок в execution doc | Нет, стартует первым |
| `backend` | Заморозить contract envelope и event taxonomy: `recommendation_id`, `impression_id`, `engine_source`, `service_source`, `fallback_source`, `empty_reason`, `latency_ms` | backend contract spec + точечные API/doc updates | `architect` truth-model |
| `uiux` | Утвердить честные labels и disclosure для `personalized/popular/recovery/substitutes/accessories/reorder` | label matrix + empty/disclosure rules | `architect` truth-model |
| `frontend` | Принять section contract, inventory states и instrumentation rules для surfaces | frontend integration plan / section map | `architect` + `backend` + `uiux` |
| `qa_metrics` | Определить Stage 1 dashboards, thresholds и parity checks | KPI/dashboards spec + go/no-go rules | `backend` contract fields |
| `devops` | Зафиксировать logging/metrics/alerting/rollback contract для recommendation serving | observability / rollout checklist | `backend` contract fields |

## 3. Что можно делать параллельно

- `architect` может идти первым и отдельно от всех.
- `backend` и `uiux` можно запускать параллельно сразу после truth-model.
- `qa_metrics` и `devops` можно готовить параллельно на базе текущих docs, но финализация зависит от contract freeze.
- `frontend` может заранее готовить slot map, но не должен финализировать integration без `backend + uiux`.

## 4. Что является blocker'ом

- Нет truth-model = нельзя честно назвать секции и состояния.
- Нет contract freeze = нельзя финализировать frontend/QA/devops packet.
- Нет event taxonomy = нельзя доверять CTR / ATC / CVR / fallback метрикам.
- Нет observability contract = нельзя безопасно включать shadow/canary.
- Нет state labeling rules = нельзя запускать rollout честно.

## 5. Минимальный order of execution

1. `architect` фиксирует truth-model.
2. `backend` и `uiux` параллельно замораживают contract + labels.
3. `qa_metrics` и `devops` параллельно закрепляют метрики, alerts и rollout gates.
4. `frontend` собирает integration plan по уже зафиксированным контрактам.
5. Stage 1 closeout только после сверки truth-model, contract freeze, dashboard spec и rollout checklist.

## 6. Первый пакет, который надо запускать немедленно

`architect + backend + uiux`.

Почему именно он:

- без truth-model нельзя отличить personalization от heuristic fallback
- без contract freeze нельзя честно строить frontend и observability
- без labels нельзя убрать product deception

После этого сразу подключаются `qa_metrics` и `devops`, чтобы не оставить Stage 1 без измеримости и rollout safety.

## 7. Definition of Done Stage 1

- Все recommendation sections имеют честные названия.
- Все surface contracts имеют версию и обязательные поля.
- Все fallback'и и empty states видимы в payload и dashboards.
- Нет claims о персонализации без user-specific signal contribution.
- Есть единый operational dashboard для `surface/source/variant/strategy`.
- Есть rollback-ready правила для `shadow` и `canary`.
