# FastAPI Search/Recommendation Rollout Runbook

Дата: 2026-03-28  
Роль: `devops`

## Цель

Зафиксировать безопасную дисциплину включения отдельных `FastAPI` сервисов `search-api` и `recommendation-api` без ломки текущего default `django-inline`.

## Режимы

### `django-inline`

- default режим
- backend использует Django engine как source of truth для runtime-ответа
- platform-services могут быть вообще не подняты

### `shadow`

- backend остаётся в `django-inline` как runtime source
- отдельные FastAPI сервисы поднимаются и получают трафик только как shadow-контур
- сравнение payload/latency/ошибок идёт вне пользовательского ответа

### `canary`

- отдельные поверхности и небольшой процент трафика могут идти в FastAPI runtime
- обязательно включать только вместе с метками поверхностей и процентом
- rollback делается через env-возврат в `django-inline`

### `fastapi`

- прямой runtime mode
- не использовать без parity-пакета backend/qa

## Profiles

Сервисы `search-api` и `recommendation-api` теперь доступны под профилями:

- `platform-services`
- `platform-shadow`
- `platform-canary`

Примеры:

```bash
docker compose --profile platform-services -f docker-compose.yml -f docker-compose.dev.yml up -d search-api recommendation-api
docker compose --profile platform-shadow -f docker-compose.yml -f docker-compose.dev.yml up -d search-api recommendation-api
docker compose --profile platform-canary -f docker-compose.yml -f docker-compose.dev.yml up -d search-api recommendation-api
```

## Backend env discipline

### Search

- `SEARCH_SERVICE_MODE=django-inline|shadow|canary|fastapi`
- `SEARCH_SERVICE_URL=http://search-api:8010`
- `SEARCH_SERVICE_TIMEOUT_SECONDS=0.8`
- `SEARCH_SERVICE_SHADOW_ENABLED=0|1`
- `SEARCH_SERVICE_SHADOW_SURFACES=search-page,live-search`
- `SEARCH_SERVICE_CANARY_ENABLED=0|1`
- `SEARCH_SERVICE_CANARY_SURFACES=search-page`
- `SEARCH_SERVICE_CANARY_PERCENT=0..100`
- `SEARCH_SERVICE_ROLLOUT_LABEL=search-service`
- `SEARCH_SERVICE_OBSERVABILITY_LABEL=search-service`

### Recommendations

- `RECOMMENDATION_SERVICE_MODE=django-inline|shadow|canary|fastapi`
- `RECOMMENDATION_SERVICE_URL=http://recommendation-api:8011`
- `RECOMMENDATION_SERVICE_TIMEOUT_SECONDS=0.8`
- `RECOMMENDATION_SERVICE_SHADOW_ENABLED=0|1`
- `RECOMMENDATION_SERVICE_SHADOW_SURFACES=home,pdp,cart,checkout,reorder`
- `RECOMMENDATION_SERVICE_CANARY_ENABLED=0|1`
- `RECOMMENDATION_SERVICE_CANARY_SURFACES=home,pdp`
- `RECOMMENDATION_SERVICE_CANARY_PERCENT=0..100`
- `RECOMMENDATION_SERVICE_ROLLOUT_LABEL=recommendation-service`
- `RECOMMENDATION_SERVICE_OBSERVABILITY_LABEL=recommendation-service`

## Безопасное включение

### Shadow rollout

```bash
export SEARCH_SERVICE_MODE=shadow
export SEARCH_SERVICE_SHADOW_ENABLED=1
export RECOMMENDATION_SERVICE_MODE=shadow
export RECOMMENDATION_SERVICE_SHADOW_ENABLED=1
docker compose --profile platform-shadow -f docker-compose.yml -f docker-compose.dev.yml up -d backend search-api recommendation-api
```

### Canary rollout

```bash
export SEARCH_SERVICE_MODE=canary
export SEARCH_SERVICE_CANARY_ENABLED=1
export SEARCH_SERVICE_CANARY_PERCENT=5
export SEARCH_SERVICE_CANARY_SURFACES=search-page

export RECOMMENDATION_SERVICE_MODE=canary
export RECOMMENDATION_SERVICE_CANARY_ENABLED=1
export RECOMMENDATION_SERVICE_CANARY_PERCENT=5
export RECOMMENDATION_SERVICE_CANARY_SURFACES=home,pdp

docker compose --profile platform-canary -f docker-compose.yml -f docker-compose.dev.yml up -d backend search-api recommendation-api
```

## Observability

- platform services отдают rollout metadata через `/health`
- метки:
  - `mode`
  - `shadow_enabled`
  - `shadow_surfaces`
  - `canary_enabled`
  - `canary_surfaces`
  - `canary_percent`
  - `label`
  - `observability_label`

Это не заменяет backend parity metrics, но даёт быстрый operational срез текущего режима.

## Rollback

Самый быстрый rollback:

```bash
export SEARCH_SERVICE_MODE=django-inline
export SEARCH_SERVICE_SHADOW_ENABLED=0
export SEARCH_SERVICE_CANARY_ENABLED=0
export SEARCH_SERVICE_CANARY_PERCENT=0

export RECOMMENDATION_SERVICE_MODE=django-inline
export RECOMMENDATION_SERVICE_SHADOW_ENABLED=0
export RECOMMENDATION_SERVICE_CANARY_ENABLED=0
export RECOMMENDATION_SERVICE_CANARY_PERCENT=0

docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d backend
```

Если нужно убрать отдельные сервисы полностью:

```bash
docker compose --profile platform-services -f docker-compose.yml -f docker-compose.dev.yml stop search-api recommendation-api
docker compose --profile platform-services -f docker-compose.yml -f docker-compose.dev.yml rm -f search-api recommendation-api
```

## Обязательные проверки перед rollout

- `docker compose config` без профиля и с нужным профилем
- `backend /health`
- `search-api /health` и `/ready`
- `recommendation-api /health` и `/ready`
- подтверждение env в backend runtime
- подтверждение rollout metadata в `/health`
- отдельный parity-gate от `qa_metrics` перед реальным `canary/fastapi`
