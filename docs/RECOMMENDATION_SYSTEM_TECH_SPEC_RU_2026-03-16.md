# Техническое задание: рекомендательная система Servio

## Статус

Исходное ТЗ закрыто.

На 16 марта 2026 в `servio` реализованы:

- recommendation foundation models, materialized sets, popularity snapshots и affinity edges
- recommendation service / selectors / ranker / event payload layer
- home / PDP / cart / checkout recommendation surfaces
- reorder surfaces в `account home`, `orders`, `order detail` и empty cart
- search recovery surfaces для `zero-results` и слабой выдачи
- server-side ingest для `recommendation_impression`, `recommendation_click`, `favorite_add`, `saved_list_add`
- recommendation attribution pipeline до `add_to_cart` и `purchase`
- recommendation observability: structured logs, Prometheus counters, attributed order/revenue metrics
- dedicated refresh tasks для:
  - popularity
  - product affinities
  - user affinities
  - replenishment / reorder profiles
  - recommendation sets
- A/B path через `control` и `ranked_v2`
- OpenSearch enrichment для recommendation/B2B retrieval:
  - `seller_rating`
  - `seller_is_verified`
  - `has_fast_delivery`
  - `procurement_fit_score`
- admin и management command refresh
- тесты на analytics ingest, reorder UI, search recovery, tasks и OpenSearch document

## Что осталось

Обязательных незакрытых пунктов по этому ТЗ не осталось.

Дальше возможны только итерационные улучшения, а не обязательный delivery backlog:

- tuning ranking weights по реальным production-метрикам
- расширение experiment matrix beyond `control` / `ranked_v2`
- более глубокий vector / embedding stage поверх текущего hybrid recall
- richer company-fit signals, если в доменной модели появятся новые procurement поля

## Acceptance

Recommendation subsystem можно считать внедрённой, потому что:

- funnel измеряется end-to-end
- recommendation source связывается с cart и order conversion
- reorder сценарии доступны пользователю в UI
- search recovery работает как продуктовая поверхность
- ranking и experiments можно улучшать на данных, а не вручную вслепую
