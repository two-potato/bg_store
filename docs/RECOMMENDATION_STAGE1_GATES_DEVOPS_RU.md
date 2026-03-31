# Recommendation Stage 1 Gates: DevOps Checklist

Дата: 2026-03-28  
Роль: `devops`  
Пакет: backlog `065`

## Цель

Зафиксировать минимальный `rollout / alerts / observability` gate для recommendation platform Servio после Stage 1 contract freeze.

Документ нужен не для “идеального future-state”, а для честного production-safe baseline:

- видно ли, что отвечает `Django gateway` или `recommendation-api`
- видно ли `fallback`, `empty`, `timeout`, `schema mismatch`
- можно ли безопасно включать `shadow` и `canary`
- можно ли честно переходить к Stage 2 preparation

## 1. Stage 1 rollout, alerts и observability checklist

### 1.1. Обязательные runtime prerequisites

- `X-Request-ID` или эквивалентный `request_id` проходит через gateway и recommendation service
- `surface`, `variant`, `strategy`, `source`, `service_source`, `engine_source` доступны в логах и метриках
- `fallback_source` и `empty_reason` видны в payload и в logs
- `latency_ms` измеряется на gateway и service уровне
- `recommendation_id` и `impression_id` не теряются в downstream paths
- `shadow` и `canary` запускаются только по allowlist surfaces

### 1.2. Обязательные rollout modes

- `django-inline` как baseline
- `shadow` как параллельное измерение без влияния на user-visible output
- `canary` как ограниченный production rollout
- `fastapi` только после зелёных parity и QA gates

### 1.3. Обязательные alert types

- `timeout` alert
- `upstream_500` alert
- `schema_mismatch` alert
- `empty_required_section` alert
- `fallback_explosion` alert
- `shadow_diff_spike` alert
- `latency_p95/p99` alert
- `cache_miss_spike` alert
- `candidate_count_drop` alert

### 1.4. Обязательные dashboards

- `Availability and latency`
- `Fill and quality`
- `Rollout`
- `Business bridge`

Эти дашборды должны быть доступны для:

- `Django gateway`
- `recommendation-api`
- `shadow` / `canary` compare view

## 2. Minimum logging / metrics / alerts

### 2.1. Minimum logging

Structured log минимум:

- `timestamp`
- `service`
- `environment`
- `request_id`
- `surface`
- `variant`
- `source`
- `service_source`
- `engine_source`
- `strategy`
- `latency_ms`
- `outcome`
- `fallback_reason`
- `candidate_count`
- `returned_items_count`
- `cache_hit`
- `rollout_mode`

Нельзя логировать как standard info:

- сырой PII
- полный session payload
- полный recommendation response body

### 2.2. Minimum metrics

На gateway и service уровне должны быть видны:

- request count
- error count
- timeout count
- latency `p50/p95/p99`
- fallback count
- empty section count
- candidate count
- returned items count
- shadow diff count
- canary request count
- attributed click/add_to_cart/order/revenue counts

### 2.3. Minimum alerts

Alert должен срабатывать, если:

- `fallback_rate` внезапно растёт
- `empty_required_section` растёт по обязательным surfaces
- `p95` или `p99` latency выходит за budget
- появляется `schema_mismatch`
- `shadow_diff` резко расходится с baseline
- gateway начинает массово терять `request_id` или `variant`

## 3. Rollback / shadow / canary prerequisites

### 3.1. Shadow prerequisites

- shadow включается только на allowlist surfaces
- shadow не влияет на user-visible payload
- shadow сравнивает:
  - top-k overlap
  - empty/non-empty parity
  - candidate count delta
  - latency delta
- shadow log содержит `request_id` и diff summary

### 3.2. Canary prerequisites

- canary только после зелёного contract baseline
- canary только если `fallback_rate`, `empty_rate`, `latency` и `schema` в пределах guardrails
- canary rollout должен иметь быстрый rollback switch на gateway level
- canary нельзя включать без owner on-call

### 3.3. Rollback prerequisites

- rollback должен быть одномоментным через `RECOMMENDATION_SERVICE_MODE`
- fallback path на Django должен оставаться рабочим всегда
- rollback criteria должны быть формализованы до запуска canary
- rollback не должен требовать миграций или ручного data repair

## 4. Достаточен ли baseline для Stage 2

Честная оценка:

- для `Stage 2 preparation` baseline уже достаточен
- для `Stage 2 rollout` baseline ещё недостаточен без QA gates и rollout compare rules
- для перехода к `shadow/canary` нам уже хватает contract freeze, truth-model и label matrix, но не хватает полноценных Stage 2 quality gates

Вывод:

- Stage 1 baseline уже годится как operational foundation
- Stage 2 можно начинать готовить, но не считать готовым к production rollout до закрытия `qa_metrics` gates

## 5. Что ещё надо до Stage 2

- `qa_metrics` dashboard/spec и go/no-go rules
- confirmation, что `shadow` diff и rollback telemetry реально видны
- surface allowlist и rollout owner map
- alerting по empty/fallback/latency/schema mismatch

## 6. Итог

Stage 1 DevOps gate считается закрываемым только если:

- baseline logging есть
- baseline metrics есть
- baseline alerts есть
- shadow/canary/rollback prerequisites формализованы
- Stage 2 readiness не перепутан с Stage 2 go-live

`065` не закрываю, пока не готова QA-часть Stage 1 gates.
