# Recommendation Stage 2 Execution Board

Дата: 2026-03-28  
Пакет: backlog `068`  
Статус: `Stage 2 Strong marketplace recommender`

## 1. Что делаем в Stage 2

Stage 2 не является production rollout. Это `engineering track` и `shadow/canary preparation`.

Цель Stage 2:

- собрать candidate normalization и ranking v1
- ввести business-rules layer v1
- подготовить shadow comparison поверх Stage 1 baseline
- подготовить controlled canary wiring
- доказать, что новый контур даёт uplift и не ломает базовую релевантность

## 2. Задачи по ролям

| Роль | Задача | Deliverable | Зависимость |
| --- | --- | --- | --- |
| `architect` | Зафиксировать Stage 2 scope, sequencing и boundary между engineering-track и rollout | Stage 2 scope board | Stage 1 closeout |
| `backend` | Собрать candidate normalization и ranking v1 baseline для recommendation surfaces | backend ranking baseline + tests | truth-model, contract baseline |
| `backend/uiux` | Собрать business-rules layer v1 для `substitutes`, `accessories`, `popular`, `personalized` | rules matrix + edge cases | label matrix, contract baseline |
| `qa_metrics` | Описать shadow parity, uplift measurement и gating rules | QA/metrics spec | contract baseline |
| `devops` | Подготовить shadow/canary wiring и rollout ownership | rollout checklist | QA/metrics spec |
| `frontend` | Подготовить storefront adoption plan и instrumentation rollout для Stage 2 surfaces | frontend integration plan | contract baseline, truth-model |
| `architect` | Зафиксировать Stage 2 closeout criteria | closeout criteria doc | Stage 2 execution results |

## 3. Минимальный первый пакет запуска

`architect + backend + qa_metrics`

Почему именно он:

- без `backend` нет ranking baseline
- без `qa_metrics` нельзя честно измерить shadow comparison и uplift
- без `architect` нельзя зафиксировать границу между экспериментом и rollout

`devops` и `frontend` подключаются сразу после базовой инженерной сборки, но не раньше.

## 4. Что можно делать параллельно

- `backend` может строить ranking baseline и rules layer параллельно с `qa_metrics` spec work
- `devops` может готовить rollout checklist параллельно с backend baseline
- `frontend` может готовить slot/instrumentation plan параллельно с business-rules layer
- `architect` может сопровождать все потоки как gatekeeper scope

## 5. Что является blocker'ом

- нет Stage 1 truth-model в качестве source-of-truth
- нет backend ranking baseline
- нет QA uplift plan и shadow parity rules
- нет production-safe canary ownership
- нет честного разделения `engineering-track` и `production-rollout`

## 6. Engineering track vs rollout gates

### Engineering track

Разрешено:

- candidate normalization
- ranking v1
- business-rules layer v1
- shadow comparison against Stage 1 baseline
- surface-by-surface integration planning
- instrumentation rollout planning

### Production rollout gates

Разрешено только после Stage 2 доказательств:

- измеримый uplift или не хуже baseline по ключевым метрикам
- подтверждённый shadow/canary parity
- production-safe rollback ownership
- QA/DevOps gates без открытых blockers
- честная observability по surfaces

Stage 2 completion нельзя называть, пока не выполнены rollout gates.

## 7. Минимальный order of execution

1. `architect` фиксирует Stage 2 scope и boundary.
2. `backend` собирает candidate normalization и ranking v1 baseline.
3. `qa_metrics` фиксирует shadow parity и uplift measurement.
4. `devops` подготавливает shadow/canary wiring.
5. `backend/uiux` доводит business-rules layer v1.
6. `frontend` готовит adoption plan и instrumentation rollout.
7. `architect` делает closeout и решает, можно ли двигаться к rollout gates.

## 8. Итог

Stage 2 можно запускать сейчас только как controlled engineering track.
Production rollout и Stage 2 completion возможны только после доказанного uplift и закрытых gates.
