# ADR 0002: ML Dependencies as Optional Extra

- Статус: Accepted
- Дата: 2026-03-20

## Контекст

`scikit-learn` увеличивал размер runtime-окружения backend, хотя основная web-нагрузка может работать без полного ML-стека.

## Решение

- Перенести ML-зависимости в optional extra:
  - `[project.optional-dependencies].ml`
- Базовый web-runtime остается без обязательной установки `scikit-learn`.
- ML-функции, где библиотека недоступна, работают через fallback/ограниченный функционал.

## Последствия

- Плюсы: легче runtime image, быстрее cold start и deploy.
- Минусы: для ML-training окружений нужно явное `uv sync --extra ml`.

## Правило эксплуатации

- Для production web: базовый `uv sync`.
- Для jobs/experiments ML: `uv sync --extra ml`.
