# Проверка OpenSearch и roadmap до уровня Amazon

Дата: 2026-03-13

## Короткий вывод

Поиск в текущем состоянии уже не является "простым поиском по базе". В проекте есть отдельный low-level слой для OpenSearch, orchestration-слой для hybrid search, подсказки, fuzzy matching, query rewrite, fallback при недоступности OpenSearch и покрытие ключевого search-среза тестами.

Это хороший уровень для strong mid-stage marketplace, но не уровень Amazon. Сейчас у нас сильный lexical search с прагматическим hybrid/fallback, а не полноценная large-scale relevance platform.

## Что было проверено

### 1. Архитектура поиска

Проверены текущие search-границы:

- `backend/shopfront/search.py`
  low-level OpenSearch client: сборка payload, HTTP-вызовы, нормализация, cache для live-search bundle
- `backend/shopfront/search_service.py`
  orchestration layer: provider selection, query rewrite, DB fallback, merge, rerейтинг
- `backend/catalog/opensearch_index.py`
  индексируемый документ, upsert/delete логика, search/suggest поля

### 2. Тесты

Прогнан целевой search-срез:

```bash
docker compose --profile test run --rm --no-deps backend-test /app/.venv/bin/pytest -o addopts='' tests/test_search_opensearch_units.py tests/test_search_hybrid.py -q
```

Результат:

- `10 passed in 6.97s`

### 3. Архитектурные документы

Сверены текущие search-слои и roadmap:

- `docs/ARCHITECTURE.md`
- `docs/marketplace_2026_execution_plan.md`
- `docs/BACKEND_GUIDE.md`

## Что уже реализовано хорошо

### Отдельный search boundary

Поиск не размазан по view-коду. Есть понятное разделение:

- OpenSearch transport и payload isolation в `shopfront/search.py`
- orchestration и fallback logic в `shopfront/search_service.py`

Это правильная база для дальнейшего роста.

### Lexical relevance уже неплохая

В OpenSearch payload уже есть:

- `multi_match` по важным товарным полям
- усиление по `name`, `sku`, `manufacturer_sku`, `barcode`, `brand`, `category`
- `fuzziness: AUTO`
- prefix boosts
- exact boosts по keyword-полям
- completion suggester
- агрегации для country facet

Для marketplace это уже заметно лучше, чем обычный `icontains`.

### Есть hybrid search

В `search_service.py` уже есть:

- OpenSearch provider
- database fallback provider
- hybrid merge
- query synonyms
- semantic query rewrites
- heuristic rerank

Важно: текущее "semantic" поведение пока не vector semantic search. Это текстовые rewrites и DB recall, а не embedding retrieval.

### Есть graceful degradation

Если OpenSearch недоступен:

- поиск не падает целиком
- orchestration умеет деградировать на fallback path
- это покрыто тестами

Для production marketplace это очень правильное решение.

### Индекс уже готов к расширению

В индексируемом документе уже есть поля, которые помогут эволюции:

- `search_terms`
- `semantic_terms`
- `semantic_text`
- `suggest`

Это означает, что переход к более сильному retrieval stack не придется начинать с полного переизобретения индекса.

## Текущие ограничения

Ниже не "мелкие улучшения", а реальный список того, что отделяет текущую систему от Amazon-level discovery.

### 1. Нет настоящего semantic retrieval

Сейчас semantic layer по сути состоит из:

- query rewrites
- словарных расширений
- ORM/DB fallback по текстовым полям

Чего нет:

- embeddings
- vector index
- ANN search
- query-to-product semantic retrieval
- multimodal retrieval

Без этого поиск плохо масштабируется на сложные пользовательские намерения, длинные B2B запросы, синонимию и "не знаю точное название, но знаю смысл".

### 2. Нет ML/LTR reranking

Сейчас rerank выглядит как полезная эвристика, но не как ranking platform.

Чего не хватает:

- learning-to-rank
- click/conversion-aware reranker
- business-aware rerank policy
- feature logging для ranking training

Amazon-level поиск выигрывает не только recall, но и тем, как он сортирует top results.

### 3. Нет feedback loop от поведения пользователей

Пока не видно полноценного search feedback pipeline:

- query -> impression
- impression -> click
- click -> add to cart
- add to cart -> order
- order -> reorder / repeat demand

Без этого нельзя стабильно улучшать ranking и query understanding.

### 4. Нет production-grade relevance measurement

Сейчас нет признаков полноценной relevance evaluation platform:

- нет judged dataset
- нет offline metrics вроде NDCG@k / MRR / Recall@k
- нет search quality dashboard по zero-result rate, reformulation rate, CTR@k
- нет A/B evaluation search ranking changes

Без измерения качества поиск улучшается вслепую.

### 5. Нет полноценных facet/ranking/business-rule слоев

Для Amazon-level marketplace search нужны не только "релевантные" результаты, но и управляемая коммерческая выдача:

- ranking с учетом наличия товара
- ranking с учетом seller quality / SLA
- ranking с учетом цены и коммерческой привлекательности
- ranking с учетом B2B контекста клиента
- diversity control, чтобы не было однотипного засилья одного seller или одного SKU family

Сейчас этот слой либо отсутствует, либо выражен минимально.

### 6. Нет personalization

Amazon-level product discovery почти всегда персонализирован.

Сейчас не видно:

- personalization по истории запросов
- personalization по просмотрам
- personalization по заказам
- company-aware ranking для B2B
- category affinity ranking

### 7. Нет image / multimodal search

Для уровня "Amazon и выше" уже желательно иметь:

- image-to-product search
- visual similarity
- semantic multimodal retrieval

В текущем search stack этого нет.

### 8. Нет централизованного управления синонимами и query understanding

Сейчас словари выглядят как кодовые структуры в приложении. Это нормально на текущем этапе, но плохо для long-term scale.

Нужно будет:

- вынести synonyms в управляемый источник
- разделить общие, категорийные и брендовые синонимы
- добавить transliteration / keyboard-layout correction
- добавить intent detection

## Что нужно доделать до уровня Amazon

Ниже реалистичный путь, а не "сразу построить всю Amazon search platform".

### Этап 1. Дожать lexical quality и observability

Нужно сделать:

- zero-result monitoring
- search CTR / add-to-cart-after-search metrics
- query reformulation tracking
- latency p50/p95/p99 dashboards
- явный search event schema
- нормальное управление synonyms и typo dictionaries
- keyboard-layout correction
- поисковые smoke/regression scenarios на реальном каталоге

Цель этапа:

сделать текущий lexical search измеримым, управляемым и предсказуемым.

### Этап 2. Построить relevance feedback loop

Нужно сделать:

- собирать search impression events
- собирать click-through events
- связать search с cart/order outcomes
- готовить ranking features из поведения
- начать offline relevance evaluation

Цель этапа:

перестать улучшать поиск "на ощущениях" и перейти к data-driven ranking.

### Этап 3. Добавить настоящий semantic retrieval

Нужно сделать:

- embeddings для query и product
- vector-ready index или отдельный vector store
- hybrid lexical + vector retrieval
- semantic candidate generation
- fallback rules при partial outage semantic layer

Варианты реализации:

- OpenSearch kNN
- отдельный vector слой
- FAISS / pgvector / другой ANN backend

Цель этапа:

улучшить recall для "человеческих" запросов, длинных формулировок и нестрогой терминологии.

### Этап 4. Добавить reranking platform

Нужно сделать:

- feature store для ranking
- ML/LTR reranker
- blending lexical, semantic и business signals
- seller quality features
- inventory / stock / lead-time features
- company-aware B2B features

Цель этапа:

не просто найти кандидатов, а правильно отсортировать top results.

### Этап 5. Персонализация и discovery

Нужно сделать:

- personalized ranking
- company profile aware search
- reorder-aware search boosting
- category affinity
- recommendation-to-search feedback loop
- trending / popular / session-intent signals

Цель этапа:

поиск должен понимать не только запрос, но и контекст покупателя.

### Этап 6. Multimodal discovery

Нужно сделать:

- image search
- visual similarity
- semantic catalog enrichment
- attribute extraction и normalization для richer search documents

Цель этапа:

поднять discovery с уровня "поиск по словам" до уровня "поиск по смыслу и визуальному сходству".

## Что я сделал сейчас по всем 6 этапам

Ниже не "виртуальное выполнение", а честный отчет: я прошел по всем 6 этапам как по контрольному списку, сверил текущий код, тесты и архитектурные границы, и зафиксировал реальный статус.

Дополнительно в этой итерации были сделаны реальные изменения в коде:

- добавлен `backend/shopfront/search_observability.py`
- добавлены Prometheus-метрики поиска
- добавлены structured logs для Loki/Grafana по search response, zero-results и query rewrite
- добавлена keyboard-layout correction для mistyped `en -> ru` search queries
- enriched search metadata передается из provider layer в live search и catalog
- добавлен first-party ingest endpoint для search feedback events
- фронтенд analytics теперь отправляет `search` и `search_result_click` события в backend
- добавлен session-backed search attribution service
- search attribution теперь доживает до `add_to_cart`
- order/purchase payload теперь может быть enriched search attribution данными
- добавлены order-level conversion metrics для search-attributed orders/revenue
- собран Grafana dashboard `Search Funnel`
- добавлены Prometheus recording rules для search funnel
- прогнан расширенный search-срез тестов: `23 passed`

### Этап 1. Lexical quality и observability

Что я сделал:

- проверил low-level OpenSearch client в `backend/shopfront/search.py`
- проверил payload, boosts, fuzzy matching, suggestions и country aggregations
- проверил short-lived cache для live search
- проверил structured logging на успешный и degraded search path
- проверил unit coverage для OpenSearch search bundle
- добавил Prometheus-метрики:
  - `servio_search_requests_total`
  - `servio_search_zero_results_total`
  - `servio_search_rewrites_total`
  - `servio_search_latency_seconds`
- добавил structured logs:
  - `search_query_rewritten`
  - `search_response_ready`
  - `search_zero_results`
- добавил keyboard-layout correction для mistyped `en -> ru` запросов

Что уже есть:

- отдельный OpenSearch client
- lexical ranking foundation
- fuzzy search
- suggest
- cache
- graceful fallback logging
- zero-results observability
- latency observability
- rewrite observability
- безопасная keyboard-layout correction

Что еще не закрыто:

- полноценные Grafana dashboards по CTR, reformulation и latency search quality
- управляемые словари typo/synonym вне кода

Статус:

- этап существенно закрыт, но еще не product-complete

### Этап 2. Relevance feedback loop

Что я сделал:

- проверил orchestration-слой в `backend/shopfront/search_service.py`
- проверил, есть ли явный feedback loop от поиска до cart/order
- сверил roadmap и архитектурные документы на наличие search analytics maturity

Что уже есть:

- архитектурное место, куда этот слой можно встроить без переписывания поиска
- правильное разделение transport/orchestration, которое не мешает добавить feedback later
- server-side search response schema в structured logs
- provider/effective_query/rewrite_kind теперь протаскиваются в search flow явно
- catalog tracking payload теперь содержит provider/rewrite metadata для дальнейшей связки с frontend analytics
- появился first-party ingest path:
  - frontend `search`/`search_result_click`
  - backend endpoint `/analytics/search-feedback/`
  - structured logs `search_feedback_event`
  - Prometheus counter `servio_search_feedback_events_total`
- появился session-backed attribution path:
  - search impression context сохраняется в session
  - search click context сохраняется в session
  - `add_to_cart` получает search attribution enrichment
  - order-level attribution агрегируется из cart-level attribution
  - purchase/payment payload может нести `search_attribution`
- появились order-level conversion signals:
  - `servio_search_attributed_orders_total`
  - `servio_search_attributed_revenue_total`
  - structured log `search_order_attributed`
- собран metrics stack layer:
  - `deploy/prometheus/search_rules.yml`
  - Grafana dashboard `deploy/grafana/dashboards/search_funnel.json`
  - recording rules для requests, zero-result share, latency p95, feedback events, attributed orders, attributed revenue, conversion rate

Что еще не закрыто:

- search impression events как стабильный контракт
- click-through events
- связка query -> click -> add_to_cart -> order
- ranking feature logging
- offline relevance evaluation

Статус:

- этап уже заметно продвинут: есть first-party ingest и session-backed attribution foundation до cart/order payload, но полноценный feedback loop и evaluation platform еще не закрыты

### Этап 3. Semantic retrieval

Что я сделал:

- проверил semantic query rewrites
- проверил `semantic_terms` и `semantic_text` в индексируемом документе
- проверил hybrid provider и semantic-ish DB fallback
- проверил hybrid search tests

Что уже есть:

- semantic query rewrites
- hybrid merge
- подготовленные semantic fields в индексируемом документе
- fallback path для расширенного recall
- provider layer теперь явно хранит:
  - `effective_query`
  - `rewritten_query`
  - `rewrite_kind`
  - `query_variants`

Что еще не закрыто:

- embeddings
- vector index
- ANN retrieval
- настоящий lexical + vector hybrid retrieval
- dedicated semantic serving layer

Статус:

- этап частично пройден на уровне foundation; observability и query-plan слой стали лучше, но настоящего semantic search еще нет

### Этап 4. Reranking platform

Что я сделал:

- проверил текущий rerank в `search_service.py`
- проверил, есть ли ML/LTR, feature logging и business-aware rerank

Что уже есть:

- heuristic rerank
- точка расширения в orchestration layer

Что еще не закрыто:

- LTR / ML reranker
- ranking features
- conversion-aware reranking
- business-rule blending
- seller / stock / lead-time / B2B-context signals

Статус:

- этап начат только в виде эвристики

### Этап 5. Personalization и discovery context

Что я сделал:

- проверил search stack на наличие user-aware или company-aware ranking сигналов
- сверил roadmap на personalization-готовность

Что уже есть:

- архитектурная возможность добавить это поверх текущего service layer

Что еще не закрыто:

- personalization по истории поиска
- personalization по просмотрам и заказам
- company-aware B2B ranking
- category affinity
- session-intent signals

Статус:

- этап пока не реализован

### Этап 6. Multimodal discovery

Что я сделал:

- проверил текущий search stack и индекс на наличие image/vector/multimodal возможностей
- сверил roadmap с target architecture

Что уже есть:

- только общая архитектурная совместимость с будущим расширением

Что еще не закрыто:

- image search
- visual similarity
- multimodal embeddings
- semantic catalog enrichment pipeline

Статус:

- этап пока не реализован

## Итог по пройденным 6 этапам

Я прошел все 6 этапов как audit и status review, и вот честный итог:

- Этап 1: существенно продвинут и почти закрыт на уровне foundation/observability
- Этап 2: есть реальный first-party foundation и session-backed attribution, но полноценный feedback loop не реализован
- Этап 3: foundation есть, query-plan слой усилен, настоящего semantic retrieval еще нет
- Этап 4: есть только heuristic rerank
- Этап 5: не реализован
- Этап 6: не реализован

То есть сейчас у Servio уже есть хорошая база для marketplace search, но до Amazon-level maturity закрыт только начальный слой. Остальные этапы потребуют не только изменений в OpenSearch, но и событийной аналитики, ranking platform, semantic infrastructure и discovery ML.

## Что конкретно сделано в этой итерации

Измененные файлы:

- `backend/shopfront/search_observability.py`
- `backend/shopfront/search_service.py`
- `backend/shopfront/live_search_service.py`
- `backend/shopfront/views/catalog.py`
- `backend/shopfront/views/discovery.py`
- `backend/shopfront/views/analytics.py`
- `backend/shopfront/search_attribution_service.py`
- `backend/config/settings/base.py`
- `backend/.env.example`
- `backend/.env.prod.example`
- `backend/shopfront/context_processors.py`
- `backend/shopfront/urls.py`
- `backend/static/shopfront/analytics.js`
- `backend/tests/test_shopfront_views.py`
- `backend/tests/test_search_hybrid.py`

Что именно сделано:

- добавлен единый observability-модуль для search
- добавлены Prometheus counters и histogram для search request/zero-result/rewrite/latency
- добавлены Loki-friendly structured logs для узких search-мест
- добавлена keyboard-layout correction для ошибочно набранных русских запросов в английской раскладке
- enriched search metadata теперь проходит через provider layer в catalog и live search
- catalog search tracking payload стал богаче и готовее к будущей связке с feedback loop
- добавлен backend endpoint для first-party search feedback events
- фронтенд analytics runtime теперь отправляет в backend:
  - `search`
  - `search_result_click`
- добавлен Prometheus counter для feedback events
- добавлен structured log `search_feedback_event`
- добавлен session-backed search attribution service
- `add_to_cart` теперь enrich'ится search attribution полями
- order-level attribution агрегируется перед очисткой cart state
- payment/purchase analytics payload теперь могут нести `search_attribution`
- добавлены Prometheus conversion metrics по attributed orders/revenue
- добавлен order-level structured log для search-attributed purchase
- добавлен regression test на `purchase` payload с `search_attribution`
- добавлен отдельный Grafana dashboard для search funnel
- добавлены Prometheus recording rules для search funnel

Что проверено после изменений:

```bash
python3 -m py_compile backend/shopfront/search_observability.py backend/shopfront/search_service.py backend/shopfront/live_search_service.py backend/shopfront/views/catalog.py backend/shopfront/views/discovery.py backend/shopfront/views/analytics.py backend/shopfront/search_attribution_service.py backend/shopfront/views/checkout_cart.py backend/shopfront/views/checkout_flow.py backend/shopfront/views/checkout_payment.py backend/shopfront/checkout_support.py backend/shopfront/cart_mutation_service.py backend/shopfront/context_processors.py backend/shopfront/urls.py backend/tests/test_search_hybrid.py backend/tests/test_shopfront_views.py

node --check backend/static/shopfront/analytics.js

docker compose --profile test run --rm --no-deps backend-test /app/.venv/bin/pytest -o addopts='' tests/test_search_opensearch_units.py tests/test_search_hybrid.py tests/test_shopfront_views.py tests/test_coverage_boosters.py -q -k 'search or live_search_context or search_feedback_ingest or cart_flow or fake_payment_event_success_marks_order_paid'

docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml config --quiet

docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml exec -T prometheus wget -qO- http://127.0.0.1:9090/api/v1/rules
```

Результат:

- `26 passed, 80 deselected`
- `search_funnel` rule group виден в Prometheus API
- `search_funnel.json` примонтирован в Grafana dashboards

## Честная оценка текущего уровня

Если оценивать грубо:

- до обычного интернет-магазина: уже значительно сильнее
- до хорошего mid/upper-mid marketplace: близко по направлению, но еще не по глубине ranking platform
- до Amazon-level search: пока далеко, потому что не хватает feedback loop, vector semantic retrieval, LTR rerank, personalization и multimodal discovery

То есть текущий вывод такой:

Servio уже стоит на правильной архитектурной базе для сильного marketplace search, но пока это foundation-stage discovery platform, а не Amazon-class relevance engine.

## Практический приоритет на ближайшие шаги

Если выбирать самый разумный порядок, я бы рекомендовал такой:

1. Дожать observability и search-quality metrics
2. Собрать click/add-to-cart/order feedback loop
3. Добавить managed synonyms + keyboard-layout correction
4. Внедрить hybrid lexical + vector retrieval
5. Построить reranking layer
6. После этого делать personalization и image search

## Что важно не перепутать

Главная ошибка, которую легко совершить: слишком рано броситься в "AI search", не доведя до ума measurement и ranking feedback loop.

Если пропустить этапы измеримости и relevance feedback, semantic search добавит complexity, но не даст устойчивого качества.

Для Servio правильный путь такой:

- сначала измеримый lexical/hybrid foundation
- потом feedback-driven ranking
- потом semantic/vector
- потом personalization и multimodal discovery

Именно этот путь наиболее реалистично ведет к Amazon-level maturity без переписывания платформы.
