# ADR 0001: Modular Shopfront Boundaries

- Статус: Accepted
- Дата: 2026-03-20

## Контекст

`shopfront` вырос до крупного домена и начал смешивать HTTP-слой, бизнес-логику и интеграции в одном месте. Это увеличивало стоимость изменений и риск регрессий.

## Решение

Принят паттерн:

- `shopfront/views/**` — thin HTTP adapters.
- `shopfront/*_service.py` — orchestration/use-case слой.
- `shopfront/searching/**` и `shopfront/recommendation/**` — предметные подсистемы.
- Сохранение совместимости старых import-путей только как временный migration layer.

## Последствия

- Плюсы: ниже связность, проще unit-тесты сервисов, проще переносить тяжелые операции в async.
- Минусы: больше модулей и явных контрактов, выше требования к дисциплине import-paths.

## Следующие шаги

- Довести декомпозицию `discovery.py` и `pages.py` до уровня thin adapters.
- Снижать размер больших функций в `users/views/helpers.py` и management commands.
