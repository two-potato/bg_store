# Recommendation ML Platform

## Что реализовано

В проекте появился полноценный recommendation platform layer поверх существующей эвристической системы.

Сейчас платформа включает:

- event foundation: impression, click, add-to-cart, remove-from-cart, purchase, dismiss
- attribution trace: `reason_codes`, `candidate_sources`, `strategy`, `model_version`
- feature store snapshots для user/product/global
- offline dataset builder из exposure logs
- baseline trainer (`logistic_regression`)
- model registry в БД
- active model rollout через `ml_v1`
- online scoring contract с fallback на heuristic ranker
- guardrails: hidden/dismissed items, in-stock filtering, caps по seller/brand/category

## Основные файлы

- models: `backend/shopfront/models.py`
- feature store: `backend/shopfront/recommendation_feature_store.py`
- offline training + registry: `backend/shopfront/recommendation_ml.py`
- online scoring contract: `backend/shopfront/recommendation_scoring_service.py`
- ranker + guardrails: `backend/shopfront/recommendation_ranker.py`
- recommendation orchestration: `backend/shopfront/recommendation_service.py`
- policy / dismiss: `backend/shopfront/recommendation_policy.py`
- experiments / rollout: `backend/shopfront/recommendation_experiments.py`
- scheduled jobs: `backend/shopfront/tasks.py`

## Новые сущности

- `RecommendationFeatureSnapshot`
- `RecommendationTrainingDataset`
- `RecommendationModelArtifact`

Миграция:

- `backend/shopfront/migrations/0007_recommendation_ml_platform.py`

## Команды

Обновить feature snapshots:

```bash
docker compose exec backend /app/.venv/bin/python manage.py refresh_recommendation_features
```

Построить offline dataset:

```bash
docker compose exec backend /app/.venv/bin/python manage.py build_recommendation_training_dataset --surface home --label-kind purchase
```

Обучить и активировать модель:

```bash
docker compose exec backend /app/.venv/bin/python manage.py train_recommendation_ranker --surface home --label-kind purchase --activate
```

Полный refresh рекомендаций:

```bash
docker compose exec backend /app/.venv/bin/python manage.py refresh_recommendations
```

## Rollout

Настройки:

- `RECOMMENDATION_ML_ENABLED`
- `RECOMMENDATION_ML_ROLLOUT_PERCENT`
- `RECOMMENDATION_ML_SURFACES`
- `RECOMMENDATION_ML_TRAINING_WINDOW_DAYS`

Пример:

```env
RECOMMENDATION_ML_ENABLED=1
RECOMMENDATION_ML_ROLLOUT_PERCENT=100
RECOMMENDATION_ML_SURFACES=home,catalog
```

## Как это работает

1. storefront пишет recommendation exposure/events
2. snapshots считают user/product/global features
3. dataset builder собирает training rows из impressions + downstream outcomes
4. trainer обучает baseline-модель и сохраняет artifact + metrics
5. experiment layer может отправить surface в `ml_v1`
6. online scorer считает score для candidates
7. policy/ranker применяет business guardrails и diversity caps
8. если active model нет, используется heuristic fallback

## Что пока baseline, а не финальная ML-платформа

Сейчас модельный baseline намеренно простой:

- алгоритм: `logistic_regression`
- артефакты: JSON + запись в БД
- offline metrics: `logloss`, `auc`, `precision_at_5`

Следующий логичный шаг:

- заменить trainer на `LightGBM` или `XGBoost`
- добавить richer labels и multi-objective ranking
- расширить feature store и evaluation отчеты
