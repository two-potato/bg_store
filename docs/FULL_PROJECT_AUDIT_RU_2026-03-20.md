# Полный аудит Servio — актуальный остаток

Дата актуализации: 2026-03-20  
Формат: этот файл теперь содержит только незакрытые пункты и текущий статус  
Правило ведения: закрытые задачи в файл не возвращаем

## Зачем файл переписан

Историческая версия аудита разрослась в журнал уже выполненного remediation-прохода. По запросу файл очищен от закрытых пунктов и оставлен как рабочий список того, что действительно еще остается сделать.

Если задача закрыта в коде, тестах, документации или CI, ее здесь больше нет.

## Текущее состояние проекта

По состоянию репозитория Servio уже находится сильно выше аварийной зоны:

- compatibility-blocker `shopfront` уже не актуален
- security hardening по ingest/upload уже не выглядит открытым риском
- docs-layer восстановлен
- backup/security/load automation уже заведены в репозиторий
- `CatalogView` и `CheckoutSubmitView` уже не соответствуют старым замечаниям из ранней версии аудита: сейчас они thin-adapter уровня и работают через service-слой

В этом проходе дополнительно сделано:

- убрано фактическое дублирование checkout context helper-логики между [checkout_common.py](/home/twopotato/dev/servio/backend/shopfront/checkout_common.py) и [utils_checkout.py](/home/twopotato/dev/servio/backend/shopfront/views/utils_checkout.py)
- приведен в порядок верхний import/helper block в [helpers.py](/home/twopotato/dev/servio/backend/users/views/helpers.py)
- сам audit-файл очищен от закрытых пунктов

## Что удалось перепроверить сейчас

- `ruff` на затронутых файлах проходит
- `backend/tests/test_shopfront_compat.py` стартует, но полноценный DB-backed тестовый срез из текущего shell не удалось подтвердить из-за ошибки окружения: не резолвится хост PostgreSQL `db`

Это значит, что текущий остаток ниже — это уже не "пожарный remediation", а нормальный инженерный backlog V2.

## Актуальные незакрытые пункты

### P1. Разделить монолитный management-command `humanize_names`

Файл: [humanize_names.py](/home/twopotato/dev/servio/backend/catalog/management/commands/humanize_names.py)

Что не нравится сейчас:

- в команде по-прежнему очень большой `handle()`
- большие словари/пулы имен живут прямо внутри команды
- команду трудно ревьюить и точечно менять без риска сломать генерацию

Что нужно сделать:

- вынести name-pools из `handle()` в отдельный data/helper layer
- оставить в `handle()` только orchestration
- при возможности покрыть хотя бы smoke-test на dry-run сценарий

Ожидаемый результат:

- команда перестает быть giant-method
- изменение словарей и алгоритма становится локальным и безопасным

### P1. Продолжить дробление `shopfront` по use-case boundaries

Зона: [backend/shopfront](/home/twopotato/dev/servio/backend/shopfront)

Что остается открытым:

- сам домен все еще очень большой
- часть orchestration уже вынесена, но `shopfront` как подсистема по-прежнему тяжеловесен для долгой эволюции
- границы между catalog, discovery, checkout, recommendation и page composition нужно укреплять дальше

Что нужно сделать дальше:

- продолжать сдвигать query-heavy и business-heavy логику в service/selectors/repository слои
- не возвращать новую доменную логику во view-файлы
- по возможности дробить длинные service-модули следующими вертикальными срезами, а не "по утилитам"

Ожидаемый результат:

- дешевле изменения в storefront
- меньше конфликтов между search, PDP, cart и checkout работами

### P1. Сузить ответственность `users/views/helpers.py`

Файл: [helpers.py](/home/twopotato/dev/servio/backend/users/views/helpers.py)

Что остается открытым:

- файл все еще объединяет buyer, seller, upload, import, order-sync и company-related helpers
- helper layer остается слишком широким для уверенного сопровождения

Что нужно сделать:

- вынести product import/export helpers в отдельный service
- вынести upload/media helpers в отдельный seller media service
- вынести order status/allocation synchronization в более явный domain helper/service

Ожидаемый результат:

- меньше скрытой связности между buyer и seller flows
- проще тестировать куски по отдельности

### P2. Подтянуть selective docstring/type coverage на публичных сервисах

Зона:

- [backend/shopfront](/home/twopotato/dev/servio/backend/shopfront)
- [backend/orders](/home/twopotato/dev/servio/backend/orders)
- [backend/users](/home/twopotato/dev/servio/backend/users)

Что остается открытым:

- после основного remediation проект уже читаем, но публичные сервисы и нестандартные management-команды еще не везде самодокументируемы

Что нужно делать:

- писать docstring не везде подряд, а только на public service entrypoints, orchestration methods и нетривиальных командах
- постепенно расширять typed-core, не пытаясь включить `mypy` на весь монолит за один шаг

Ожидаемый результат:

- ниже цена онбординга
- легче безопасно продолжать decomposition

### P2. Расширить performance budget beyond `/catalog/`

Сейчас baseline уже есть, но он еще слишком концентрирован вокруг каталога.

Что остается открытым:

- нужно зафиксировать бюджеты не только для catalog, но и для PDP / checkout / seller hotspots

Что делать:

- добавить еще 2-3 маршрута в query budget / lightweight performance regression слой
- особенно полезны PDP и seller-order detail

Ожидаемый результат:

- деградации будут ловиться ближе к месту возникновения, а не только на общем нагрузочном фоне

## Что считать закрытым и не возвращать в backlog

Сюда не возвращаем без новой регрессии:

- `shopfront` compatibility import blocker
- `csrf_exempt` на analytics ingest
- отсутствие server-side upload validation
- broken docs index и отсутствующие guide-файлы
- отсутствие backup/restore automation
- отсутствие security scan workflow
- lint debt уровня "ruff red"

## Следующий практический порядок работ

1. Добить `humanize_names.py` до нормального размера и структуры.
2. Разнести `users/views/helpers.py` по более узким сервисам.
3. Добавить еще несколько performance budgets для критичных маршрутов.
4. Переподтвердить полный backend suite в окружении, где резолвится PostgreSQL host `db`.

## Короткий вывод

Из полного remediation-аудита аварийных незакрытых пунктов больше не осталось.  
Текущий остаток — это уже не спасение проекта, а последовательное укрепление архитектуры и сопровождения.

## Версионная сводка

Файл: [FULL_PROJECT_AUDIT_RU_2026-03-20.md](/home/twopotato/dev/servio/docs/FULL_PROJECT_AUDIT_RU_2026-03-20.md)  
Статус: актуальный open-items only  
Последняя очистка закрытых пунктов: 2026-03-20
