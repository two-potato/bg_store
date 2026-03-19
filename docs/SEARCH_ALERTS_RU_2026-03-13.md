# Search Alerts: что значат и что делать

Этот файл нужен как короткая operational-памятка по новым alert'ам поиска в Prometheus/Grafana.

## Где смотреть

- Общий обзор: Grafana dashboard `Executive Summary 2026`
- Детальный поиск: Grafana dashboard `Search Funnel`
- Логи: Grafana Explore, Loki

Полезные поисковые structured logs:

- `search_response_ready`
- `search_zero_results`
- `search_query_rewritten`
- `search_order_attributed`

## Alert: `SearchZeroResultsHigh`

Что это значит:

- доля zero-result выдачи держится выше `25%` больше `10 минут`
- пользователи ищут, но не находят товары

Частые причины:

- нет нужных товаров в индексе
- сломалась или устарела индексация
- запросы приходят в неожиданной раскладке или формулировке
- слишком агрессивные фильтры
- плохие synonyms / normalizers

Что проверить:

1. Dashboard `Search Funnel`: панели `Zero Result Share`, `Search Requests`, `Latency p95`
2. Loki по `search_zero_results`
3. Loki по `search_query_rewritten`
4. Состояние OpenSearch и свежесть индексирующих задач

Что делать:

1. Посмотреть, какие именно запросы чаще всего уходят в zero-results.
2. Проверить, есть ли эти товары в каталоге и в индексе OpenSearch.
3. Проверить не сломан ли rewrite/query normalization.
4. Если проблема точечная, добавить synonyms / alias terms.
5. Если проблема массовая, разбирать indexing pipeline и freshness индекса.

## Alert: `SearchLatencyP95High`

Что это значит:

- p95 latency поиска выше `0.8s` больше `10 минут`

Частые причины:

- деградация OpenSearch
- тяжелые запросы или слишком широкие aggregations
- CPU / memory pressure
- network issues между backend и OpenSearch

Что проверить:

1. Dashboard `Search Funnel`: `Search Latency p95`
2. Overview dashboard: host/container CPU и memory
3. Loki по `search_response_ready` и сравнить `latency_ms`, `provider`, `surface`
4. Логи OpenSearch и backend

Что делать:

1. Проверить, не деградировал ли только один `provider` или `surface`.
2. Проверить resource pressure на `opensearch` и `backend`.
3. Проверить последние изменения в query-building и фильтрах.
4. При необходимости временно упростить запросы или отключить тяжелые search features.

## Alert: `SearchClicksMissing`

Что это значит:

- поиск отдает результаты, но `search_result_click` events не приходят `15 минут`

Частые причины:

- сломан frontend analytics dispatch
- click tracking отвалился после изменения шаблона/DOM
- результаты рендерятся, но элементы не несут нужный tracking context
- backend ingest `/analytics/search-feedback/` не принимает события

Что проверить:

1. Dashboard `Search Funnel`: `Search Requests / 1h` и `Search Clicks / 1h`
2. Browser console и network на storefront search pages
3. Loki по:
   - `search_feedback_invalid_payload`
   - `search_feedback_rejected`
   - `search_response_ready`
4. Ответы endpoint `/analytics/search-feedback/`

Что делать:

1. Проверить, отправляет ли фронт `search_result_click`.
2. Проверить, есть ли `search_context` у карточек и ссылок выдачи.
3. Проверить JSON-контракт ingest endpoint.
4. Если broken только на одной поверхности, смотреть конкретный template/HTMX fragment.

## Alert: `SearchAttributedOrdersMissing`

Что это значит:

- клики по поиску есть, но attributed orders нет при заметном объеме search-click traffic

Частые причины:

- потеря session attribution между search и checkout
- разрыв между cart и order attribution
- баг в purchase analytics payload
- реальные UX-проблемы после search, а не telemetry bug

Что проверить:

1. Dashboard `Search Funnel`:
   - `Search Clicks`
   - `Attributed Orders`
   - `Attributed Revenue`
   - `Search Conversion`
2. Loki по:
   - `search_order_attributed`
   - `search_feedback_event`
3. Checkout/cart flow на storefront
4. Session lifecycle, guest checkout, cart mutation path

Что делать:

1. Проверить, сохраняется ли attribution после click и add-to-cart.
2. Проверить, попадает ли `search_attribution` в payment/order payload.
3. Проверить guest/auth сценарии отдельно.
4. Если telemetry цела, значит проблема уже продуктовая: search leads плохого качества или checkout UX режет conversion.

## Минимальный порядок реакции

1. Открыть `Executive Summary 2026` и понять, это локальная search-проблема или часть общей деградации.
2. Открыть `Search Funnel` и определить тип сбоя: качество, latency, tracking, conversion.
3. Через Loki найти соответствующие structured logs за тот же период.
4. После локализации причины уже идти в backend, OpenSearch, HTMX/template flow или indexing pipeline.

## Что считать нормой

- zero-result share не должен долго держаться выше `15-20%`
- p95 latency желательно держать ниже `0.5-0.8s`
- при стабильном search traffic должны идти clicks
- при meaningful click volume должны появляться attributed orders и attributed revenue
