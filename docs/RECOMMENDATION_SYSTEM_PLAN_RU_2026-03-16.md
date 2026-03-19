# План внедрения рекомендательной системы в Servio

## Цель

Внедрить в `servio` зрелую recommendation-платформу по принципам Amazon:

- разные сценарии рекомендаций для разных поверхностей, а не одна общая лента
- data-driven ранжирование на основе просмотров, корзины, заказов, избранного и подписок
- асинхронный пересчет кандидатов через Celery
- явная аналитика impression, click, add-to-cart, purchase и uplift по каждому recommendation source
- постепенная эволюция: от эвристик и co-occurrence к scoring pipeline, без преждевременного ML-overkill

Документ опирается на текущую архитектуру `servio`, а не на абстрактный greenfield.

## Что в проекте уже есть

На сегодня в проекте уже реализован хороший фундамент:

- есть выделенный модуль [`backend/shopfront/recommendations.py`](../backend/shopfront/recommendations.py)
- на главной уже есть блоки `recommended_for_you`, `home_recently_viewed`, `watchlist_products`
- на PDP уже есть `frequently_bought_together` и `seller_cross_sell`
- в корзине и checkout уже есть cross-sell по продавцу
- просмотры товара пишутся в сессию и в `RecentlyViewedProduct`
- есть пользовательские сигналы интереса: `FavoriteProduct`, `SavedList`, `BrandSubscription`, `CategorySubscription`
- есть order history через `Order` и `OrderItem`, что позволяет строить co-purchase граф
- есть аналитика `recommendation_impression` и `recommendation_click`
- есть PostHog/Clarity runtime и серверная storefront-архитектура
- есть Redis, Celery и OpenSearch, то есть инфраструктура для async refresh уже готова

Ключевые текущие точки:

- [`backend/shopfront/recommendations.py`](../backend/shopfront/recommendations.py)
- [`backend/shopfront/models.py`](../backend/shopfront/models.py)
- [`backend/shopfront/views/pages.py`](../backend/shopfront/views/pages.py)
- [`backend/shopfront/views/product.py`](../backend/shopfront/views/product.py)
- [`backend/shopfront/views/helpers.py`](../backend/shopfront/views/helpers.py)
- [`backend/shopfront/views/checkout_cart.py`](../backend/shopfront/views/checkout_cart.py)
- [`backend/shopfront/views/checkout_flow.py`](../backend/shopfront/views/checkout_flow.py)
- [`backend/static/shopfront/analytics.js`](../backend/static/shopfront/analytics.js)

## Главный вывод по текущему состоянию

Сейчас в `servio` уже есть recommendation layer первого поколения, но она пока:

- считается в request-time, а не заранее
- почти полностью heuristic-driven
- не имеет единого event pipeline для recommendation quality
- не разделяет candidate generation и ranking
- не хранит готовые подборки/индексы для пользователя, товара, корзины, бренда, категории
- не учитывает negative signals: скрытие, игнор, повторяющееся непопадание в клик
- слабо использует B2B-контекст: тип покупателя, компания, отрасль, repeat procurement, сезонность, seller reliability

Иными словами: основа уже есть, но до Amazon-подхода не хватает именно recommendation platform, а не еще одного шаблонного блока в UI.

## Как делать "по опыту Amazon" в контексте Servio

Amazon-подход полезно разложить на 6 практических принципов:

### 1. Рекомендации зависят от контекста страницы

Нужны отдельные стратегии для:

- home page: personalized discovery
- PDP: substitute, similar, accessory, frequently bought together
- cart: basket expansion
- checkout: last-minute low-friction add-ons
- account/orders: reorder and replenish
- category/search zero-results: recovery recommendations

### 2. Нужны разные источники сигнала

Для ranking нужно объединять:

- view
- favorite
- add_to_cart
- remove_from_cart
- purchase
- repeat purchase
- saved list add
- brand/category subscription
- search click attribution

### 3. Candidate generation и ranking должны быть разделены

Сначала собираем несколько пулов кандидатов:

- same brand
- same category
- co-purchase
- same seller
- trending/popular
- user-affinity
- reorder

Потом считаем итоговый score.

### 4. Большая часть вычислений должна быть offline/async

Сложные подборки не должны собираться при каждом HTTP-запросе. В request path должно оставаться:

- взять готовый список candidate ids
- отфильтровать недоступные товары
- отрендерить блок

### 5. Каждая recommendation surface должна быть измеримой

По каждому source нужно видеть:

- impressions
- CTR
- add-to-cart rate
- purchase conversion
- revenue per impression
- AOV uplift

### 6. Для B2B-маркетплейса важен не только CTR

Для `servio` метрики важнее классического consumer e-commerce:

- repeat order rate
- reorder completion
- seller diversity without harming conversion
- attach rate в корзине
- GMV uplift
- margin-aware uplift

## Целевая архитектура для Servio

Рекомендуемая схема без ломки текущего проекта:

### Domain split

- `backend/shopfront/recommendations.py`
  Оставить как orchestration facade для storefront.
- `backend/shopfront/recommendation_service.py`
  Новый слой orchestration/use-cases.
- `backend/shopfront/recommendation_ranker.py`
  Новый scoring/ranking слой.
- `backend/shopfront/recommendation_selectors.py`
  Новый query-heavy слой для candidate retrieval.
- `backend/shopfront/recommendation_events.py`
  Новый модуль записи событий интереса.
- `backend/shopfront/tasks.py`
  Celery tasks для refresh популярных товаров и персональных подборок.
- `backend/shopfront/models.py` или новый пакет `backend/shopfront/models/`
  Модели materialized recommendations и event summaries.

### Данные

Нужно добавить 3 уровня хранения:

1. Raw events
- событие просмотра, клика, корзины, покупки, сохранения

2. Aggregates
- co-purchase counts
- product-to-product affinity
- user-to-brand/category affinity
- popularity by time window

3. Materialized recommendation sets
- готовые списки ids для рендера на home/PDP/cart/checkout/account

### Infra role

- PostgreSQL: source of truth и агрегаты малого/среднего объема
- Redis: короткоживущий cache горячих подборок
- Celery: пересчет агрегатов и materialized sets
- OpenSearch: optional later stage для trend segmentation, search-personalization и hybrid retrieval

## Как OpenSearch и hybrid search помогают рекомендациям

Да, помогают, и в `servio` это особенно полезно, потому что search stack уже существует и его можно использовать как recommendation candidate engine.

Важно: OpenSearch не должен заменять recommendation layer. Его роль другая:

- быстро расширять пул кандидатов
- находить substitute и similar товары за пределами простого same-category/same-brand
- помогать с zero-results и search-recovery рекомендациями
- давать richer recall для personalization и discovery

### Что уже есть в проекте

- low-level OpenSearch client в [`backend/shopfront/search.py`](../backend/shopfront/search.py)
- orchestration и `HybridSearchProvider` в [`backend/shopfront/search_service.py`](../backend/shopfront/search_service.py)
- индексируемые `search_terms`, `semantic_terms`, `semantic_text`, suggest-поля в [`backend/catalog/opensearch_index.py`](../backend/catalog/opensearch_index.py)

То есть база уже есть: поиск умеет lexical recall, query rewrite и текущий pragmatic hybrid merge.

### Где OpenSearch реально полезен для recommendations

#### 1. Similar и substitute recommendations на PDP

Для блока "Похожие товары" и "Альтернативы" OpenSearch может находить кандидатов не только по category/brand, но и по:

- `semantic_terms`
- `description`
- `material`
- `purpose`
- `flavor`
- tags

Это особенно полезно, когда пользователь ищет не точный SKU, а функциональный аналог.

#### 2. Search recovery и zero-results surfaces

Если поиск дал слабую выдачу или zero results, можно строить recovery-блоки:

- похожие товары по semantic/hybrid recall
- популярное в близкой категории
- substitute по похожему intent

Это хороший bridge между search и recommendations.

#### 3. Personalized discovery recall

Если у пользователя есть affinity к category/brand/tag, OpenSearch можно использовать для извлечения более широкого пула кандидатов по его профилю интересов, а потом уже ранжировать их recommendation ranker-ом.

То есть схема такая:

- user profile -> affinity terms
- OpenSearch/hybrid retrieval -> 100-300 кандидатов
- recommendation ranker -> top 8-12 для surface

#### 4. Trending discovery

OpenSearch полезен не только для текстового поиска, но и для быстрых candidate pools по фильтруемым признакам:

- in stock
- promo
- new
- category
- brand
- seller

Это ускоряет построение мерчандайзинговых и discovery-подборок.

### Где OpenSearch не должен быть главным

Не стоит пытаться строить через OpenSearch:

- co-purchase affinity
- reorder prediction
- user-specific repeat procurement
- basket expansion logic на основе реальных заказов

Это лучше считать из `Order`, `OrderItem`, `FavoriteProduct`, `SavedList`, subscriptions и event-агрегатов.

### Практическая архитектура связки search + recommendations

Рекомендуемая схема для `servio`:

1. Search/OpenSearch слой отвечает за recall.
2. Recommendation selectors объединяют search candidates с business candidates.
3. Recommendation ranker считает финальный score.
4. Materialized `RecommendationSet` хранит финальные ids для UI.

Пример candidate sources для PDP:

- co-purchase candidates из `OrderItem`
- same seller candidates из PostgreSQL
- same brand/category candidates из PostgreSQL
- semantic similar candidates из OpenSearch/hybrid

Потом ranker собирает их в одну финальную выдачу.

### Что добавить в план на практике

Нужен отдельный recommendation candidate source, использующий search stack:

- `opensearch_similar_products(product, limit=...)`
- `opensearch_substitute_products(product, limit=...)`
- `hybrid_affinity_candidates(user_profile, limit=...)`
- `search_recovery_candidates(query, limit=...)`

Эти функции лучше положить в `recommendation_selectors.py`, а не вызывать search provider напрямую из view.

### Когда это внедрять

- Phase A: не обязательно, можно начать без OpenSearch-driven recommendations
- Phase B: да, это сильный шаг для PDP substitutes, similar products и search recovery
- Phase C: развивать до настоящего lexical + vector hybrid retrieval, если появится embedding pipeline

### Важная оговорка

Текущий `hybrid` в проекте уже полезен, но это еще не полноценный vector semantic retrieval. Поэтому в плане лучше закладывать 2 стадии:

1. использовать текущий hybrid provider как source расширенного candidate recall
2. позже, если будет смысл, добавить embeddings и настоящий lexical + vector hybrid

Иначе легко переоценить текущую "семантику" и недооценить важность order-driven recommendation signals.

## Какие поля добавить в OpenSearch product document для recommendation use cases

Сейчас в [`backend/catalog/opensearch_index.py`](../backend/catalog/opensearch_index.py) уже индексируются хорошие search-поля:

- `search_terms`
- `semantic_terms`
- `semantic_text`
- `suggest`
- `brand`
- `category`
- `store_name`
- `price`
- `is_new`
- `is_promo`
- `in_stock`

Для recommendation use cases этого фундамента недостаточно. Нужны еще поля, которые помогут candidate recall и business-aware filtering.

### Поля, которые стоит добавить в первую очередь

#### Identity и связи

- `brand_id`
- `category_id`
- `seller_id`
- `series_id`
- `tag_ids`

Это нужно, чтобы recommendation selectors могли делать быстрые filters и blends без лишнего SQL.

#### Commercial and operational fit

- `stock_qty`
- `min_order_qty`
- `lead_time_days`
- `pack_qty`
- `unit`
- `publication_status`

Это особенно важно для `servio`, потому что B2B-рекомендации должны учитывать operability, а не только смысловую похожесть.

#### Merchandising signals

- `collections`
- `collection_ids`
- `has_documents`
- `has_certificate`
- `is_featured_collection_product`

Это поможет смешивать semantic recall с merchandising logic.

#### Recommendation support fields

- `price_bucket`
- `popularity_score_7d`
- `popularity_score_30d`
- `purchase_count_30d`
- `view_count_7d`
- `add_to_cart_count_7d`
- `conversion_score`

На первом этапе эти поля можно не использовать в search ranking напрямую, но они полезны для recommendation candidate filtering и blending.

#### B2B suitability fields

- `seller_rating` или seller trust proxy
- `seller_is_verified`
- `has_fast_delivery`
- `country_of_origin_keyword`
- `market_segment` если появится сегментация каталога

### Какие поля особенно важны для PDP substitutes

Если цель сделать хороший блок "Альтернативы", то минимум стоит добавить:

- `brand_id`
- `category_id`
- `seller_id`
- `stock_qty`
- `min_order_qty`
- `lead_time_days`
- `pack_qty`
- `price_bucket`
- `tag_ids`

Тогда substitute logic сможет находить не просто "текстово похожие" товары, а реально пригодные к закупке замены.

### Как использовать эти поля в recommendation layer

Схема должна быть такой:

1. OpenSearch возвращает расширенный candidate pool.
2. Recommendation selectors накладывают business filters:
- `in_stock`
- приемлемый `lead_time_days`
- подходящий `price_bucket`
- адекватный `min_order_qty`
3. Recommendation ranker считает итоговый score.

### Что не надо делать в первой итерации

Не нужно сразу перегружать индекс десятками derived fields. Для первой волны достаточно:

- identity fields
- operational fields
- 2-3 popularity fields
- 1-2 conversion fields

И только потом расширять схему.

## Что нужно реализовать по этапам

## Этап 1. Нормализовать recommendation events

### Что сделать

Собрать единый поток событий для recommendation-quality.

Нужно фиксировать:

- `product_view`
- `recommendation_impression`
- `recommendation_click`
- `add_to_cart`
- `remove_from_cart`
- `purchase`
- `favorite_add`
- `saved_list_add`

### Где менять

- [`backend/static/shopfront/analytics.js`](../backend/static/shopfront/analytics.js)
- [`backend/shopfront/views/product.py`](../backend/shopfront/views/product.py)
- [`backend/shopfront/views/checkout_cart.py`](../backend/shopfront/views/checkout_cart.py)
- [`backend/shopfront/views/checkout_flow.py`](../backend/shopfront/views/checkout_flow.py)
- новый модуль `backend/shopfront/recommendation_events.py`

### Что важно

- у каждого события должен быть `recommendation_source`
- нужен `request_id` или близкий correlation id
- нужен `user_id`, а для гостя `session_key`
- нужен `surface`: `home`, `pdp`, `cart`, `checkout`, `account`, `search_recovery`
- нужен `position` в блоке
- нужно тащить `seller_id`, `brand_id`, `category_id`, `price`

### Результат

Появится единая измеримость качества рекомендаций. Без этого нельзя честно понимать, что реально работает.

## Этап 2. Вынести логику из request-time в candidate/ranking pipeline

### Что сделать

Разделить текущую рекомендационную логику на:

- candidate generation
- ranking
- rendering

### Предлагаемая структура

- `recommendation_selectors.py`
  Собирает кандидатов по источникам.
- `recommendation_ranker.py`
  Складывает score.
- `recommendation_service.py`
  Выбирает стратегию под surface.

### Пример источников кандидатов

- same brand
- same category
- same seller
- co-purchase from `OrderItem`
- recently popular
- new and promo constrained by affinity
- from saved lists / favorites / subscriptions
- reorder from prior purchases

### Почему это нужно

Сейчас логика размазана между `recommendations.py`, `views/helpers.py`, `pages.py`, `checkout_*`. Это мешает эволюции и A/B.

## Этап 3. Добавить агрегаты популярности

### Что сделать

Сделать не один "популярный товар", а несколько видов popular lists:

- globally popular 24h
- globally popular 7d
- popular in category
- popular in brand
- popular for seller
- popular among repeat buyers
- popular with high conversion, а не просто с большим числом показов

### Новые сущности

Минимально:

- `RecommendationPopularitySnapshot`
- `RecommendationProductAffinity`

Если без нового app, можно начать в `shopfront/models.py`, но лучше готовить выделенный пакет или `shopfront/recommendation_models.py`.

### Источники сигнала

- `OrderItem` для purchased popularity
- `product_view` для viewed popularity
- `add_to_cart` для intent popularity
- weighting с decay по времени

### Формула на старте

```text
popularity_score =
  purchases_7d * 8
  + add_to_cart_7d * 3
  + clicks_7d * 2
  + views_7d * 1
  + repeat_purchase_30d * 10
```

### Где показывать

- home: "Популярное в Servio"
- category page: "Популярное в этой категории"
- seller/store page: "Часто заказывают у этого поставщика"
- zero-results: "Популярное рядом с вашим запросом"

## Этап 4. Построить полноценный "Вам может подойти" для пользователя

### Что сделать

Собрать user-affinity профиль.

### Использовать сигналы

- последние просмотры
- избранное
- saved lists
- заказы и повторные заказы
- brand/category subscriptions
- поисковые клики и конверсии

### Что считать

- affinity к brand
- affinity к category
- affinity к seller
- ценовой диапазон
- повторяемые закупочные паттерны

### Пример простого user score

```text
user_product_score =
  brand_affinity * 3
  + category_affinity * 4
  + seller_affinity * 2
  + popularity_score * 1
  + promo_boost * 1
  + in_stock_boost * 2
  - overshown_penalty
```

### Отдельно для B2B

Для `servio` важно не рекомендовать все подряд, а учитывать:

- закупочный профиль компании
- frequent reorder товаров
- рабочие ценовые диапазоны
- preferred sellers
- MOQ и lead time

Если эти поля будут доступны на уровне `LegalEntity` или истории заказов компании, это даст качество выше, чем "consumer-like recommendations".

## Этап 5. Усилить PDP как Amazon-style decision page

### Что уже есть

- similar products
- accessories
- frequently bought together
- seller cross-sell
- recently viewed

### Что добавить

- substitute recommendations
  Когда товар дорогой, нет в наличии, большой MOQ или длинный lead time.
- better-better-best ladder
  3 альтернативы: дешевле, оптимально, премиум.
- compare-ready recommendations
  Похожие товары с ключевыми различиями по pack size, material, MOQ, lead time.
- attachment recommendations
  Что докупить к товару как комплект.

### Практическая реализация

Сначала без ML:

- substitutes: same category + same brand/seller + price distance + stock availability
- better/best: сортировка по цене, promo, rating/reviews
- attachments: через tag/category adjacency и co-purchase

## Этап 6. Усилить корзину и checkout

### Цель

Поднять AOV, не ломая конверсию.

### Правила как у Amazon

- в корзине показывать наборы с высокой вероятностью докупки
- в checkout показывать только low-friction товары
- ограничить количество SKU в блоке
- не показывать то, что требует долгого выбора

### Для `servio`

В `cart` и `checkout` стоит ранжировать кандидатов по:

- тому же seller
- короткому lead time
- низкому MOQ
- высокой co-purchase affinity
- не слишком высокой цене относительно корзины

### Что убрать

Не стоит в checkout показывать:

- сложные substitute-подборки
- дорогие альтернативы
- товары без наличия

## Этап 7. Сделать reorder engine для B2B

Это один из самых ценных Amazon-подобных сценариев для вашего проекта.

### Что сделать

Добавить блоки:

- "Заказывают повторно"
- "Пора пополнить"
- "Повторить прошлую закупку"

### На чем строить

- прошлые `Order` и `OrderItem`
- частота покупки SKU
- средний интервал между закупками
- сезонность
- saved lists, созданные из заказов

### Где показывать

- account home
- orders history
- home для авторизованного пользователя
- cart empty state

### Почему это важно

Для B2B marketplace reorder часто дает больше GMV, чем generic personalization.

## Этап 8. Ввести materialized recommendation tables

### Что сделать

Чтобы не считать все на лету, хранить готовые наборы рекомендаций.

### Минимальная модель

`RecommendationSet`

- `kind`
- `scope_type`
- `scope_id`
- `source`
- `product_ids`
- `metadata`
- `generated_at`
- `expires_at`

Примеры:

- `kind=personalized_home`, `scope_type=user`, `scope_id=123`
- `kind=fbt`, `scope_type=product`, `scope_id=456`
- `kind=popular_category`, `scope_type=category`, `scope_id=77`

### Почему это важно

- меньше SQL в request path
- проще A/B
- легче прогревать кэш
- можно безопасно деградировать на старые снапшоты

## Этап 9. Пересчет через Celery

### Очереди задач

- hourly popularity refresh
- product affinity refresh
- user affinity refresh
- reorder prediction refresh
- warm cache for top surfaces

### Trigger strategy

- after purchase: enqueue affinity updates for all ordered product pairs
- after favorite/saved list add: enqueue lightweight user-affinity update
- scheduled beat: full popularity recompute

### Важно

Не переносить тяжелые вычисления в signals. Только `transaction.on_commit(...delay())`.

## Этап 10. Добавить A/B testing и score governance

### Что тестировать

- разные формулы ranking
- число карточек в блоке
- порядок блоков на home/PDP/cart
- promo boost vs no promo boost
- seller-diversity penalty vs no penalty

### Метрики успеха

- CTR by source
- add-to-cart rate by source
- purchase conversion by source
- revenue per impression
- average order value uplift
- repeat purchase uplift

### Практика

В PostHog заводить эксперименты по `recommendation_source` и variant label.

## Какие модели и таблицы я бы добавил в первую очередь

Минимальный полезный набор:

1. `RecommendationEvent`
- сырые события recommendation и product intent

2. `RecommendationProductAffinity`
- `source_product_id`
- `target_product_id`
- `affinity_type`
- `score`
- `orders_count`
- `updated_at`

3. `RecommendationPopularitySnapshot`
- `scope_type`
- `scope_id`
- `window`
- `product_id`
- `score`

4. `RecommendationSet`
- materialized ids под surface/scope

Если нужен минимальный старт без большого объема raw events, можно часть event ingestion сначала писать в PostHog, а в БД держать только агрегаты и materialized sets.

## Приоритет внедрения в Servio

Рекомендую идти в таком порядке.

### Фаза A. Быстрая польза за 1 спринт

- нормализовать recommendation event schema
- вынести ranking/candidate logic в сервисные модули
- сделать popular snapshots
- завести `RecommendationSet` для home/PDP/cart/checkout

### Фаза B. Основной коммерческий эффект

- user-affinity "Вам может подойти"
- category/brand/seller popularity
- reorder recommendations
- substitute recommendations на PDP
- OpenSearch/hybrid candidate retrieval для similar/substitute/search-recovery блоков

### Фаза C. Продвинутая оптимизация

- company-aware recommendations
- margin-aware ranking
- seasonality and replenishment prediction
- lexical + vector hybrid retrieval через OpenSearch

## Предлагаемое распределение по файлам

### Новые файлы

- `backend/shopfront/recommendation_service.py`
- `backend/shopfront/recommendation_ranker.py`
- `backend/shopfront/recommendation_selectors.py`
- `backend/shopfront/recommendation_events.py`
- `backend/shopfront/recommendation_tasks.py` или расширение [`backend/shopfront/tasks.py`](../backend/shopfront/tasks.py)
- `backend/tests/test_recommendation_service.py`
- `backend/tests/test_recommendation_ranker.py`
- `backend/tests/test_recommendation_tasks.py`

### Точки рефакторинга

- упростить [`backend/shopfront/recommendations.py`](../backend/shopfront/recommendations.py) до facade-слоя
- убрать прямые recommendation query fragments из [`backend/shopfront/views/helpers.py`](../backend/shopfront/views/helpers.py)
- убрать дублирующийся impression payload builder из `pages.py`, `helpers.py`, `checkout_support.py` в общий recommendation analytics helper

## Пример целевого API внутри backend

```python
recommendations_for_home(user=request.user, session=request.session)
recommendations_for_product(product=product, user=request.user, session=request.session)
recommendations_for_cart(user=request.user, cart_lines=ctx["items"])
recommendations_for_checkout(user=request.user, cart_lines=ctx["items"])
recommendations_for_reorder(user=request.user)
```

View не должен знать, как именно считается score.

## Риски и как их избежать

### Риск 1. Слишком рано уйти в ML

Не нужно начинать с embeddings или отдельного recsys-сервиса. Текущий проект уже может получить сильный uplift на:

- co-purchase
- affinity
- popularity
- reorder
- seller/category/brand-aware ranking

### Риск 2. Перегрузить request path

Все тяжелые расчеты только через Celery + cache + materialized sets.

### Риск 3. Сделать consumer recommendations вместо B2B

Нужно приоритизировать:

- reorder
- operational fit
- MOQ/lead time/stock
- seller trust
- company buying patterns

### Риск 4. Мерить только CTR

Главные бизнес-метрики для `servio`:

- GMV uplift
- AOV uplift
- repeat order rate
- reorder completion
- purchase conversion from recommendation

## Конкретный пошаговый план реализации

### Блок 1. Foundation и измеримость

1. Зафиксировать единый recommendation event contract.
2. Вынести builder-ы recommendation analytics payload в общий helper.
3. Добавить backend ingestion или server-side normalization для recommendation events.
4. Привязать все текущие recommendation surfaces к единому `recommendation_source`.
5. Завести dashboard по `impression -> click -> add_to_cart -> purchase`.

### Блок 2. Рефакторинг recommendation кода

6. Создать `backend/shopfront/recommendation_service.py`.
7. Создать `backend/shopfront/recommendation_ranker.py`.
8. Создать `backend/shopfront/recommendation_selectors.py`.
9. Перенести текущую логику из `recommendations.py`, `views/helpers.py`, `pages.py`, `checkout_*` в service layer.
10. Оставить view только роль вызова сервиса и передачи готового context в шаблон.

### Блок 3. Модели и хранение

11. Добавить `RecommendationSet`.
12. Добавить `RecommendationPopularitySnapshot`.
13. Добавить `RecommendationProductAffinity`.
14. Решить, нужен ли raw `RecommendationEvent` в PostgreSQL сразу или достаточно PostHog + агрегатов на первой итерации.
15. Добавить индексы и TTL/expiration стратегию для materialized recommendation data.

### Блок 4. Popularity и affinity pipeline

16. Реализовать hourly/daily Celery task для popularity refresh.
17. Реализовать product-to-product affinity refresh из `OrderItem`.
18. Реализовать user-affinity aggregation из views, favorites, subscriptions, saved lists, orders.
19. Сохранить результаты в materialized tables.
20. Добавить warm cache для top surfaces.

### Блок 5. Первая волна productized recommendations

21. Перевести `frequently_bought_together` на affinity/materialized candidates.
22. Перевести seller cross-sell на единый recommendation service.
23. Сделать блок "Популярное в Servio".
24. Сделать блок "Популярное в категории".
25. Сделать блок "Вам может подойти" на основе user-affinity.
26. Сделать блок "Заказывают повторно" и "Пора пополнить".

### Блок 6. OpenSearch для recommendations

27. Расширить [`backend/catalog/opensearch_index.py`](../backend/catalog/opensearch_index.py) recommendation-полями:
- `brand_id`
- `category_id`
- `seller_id`
- `series_id`
- `tag_ids`
- `stock_qty`
- `min_order_qty`
- `lead_time_days`
- `pack_qty`
- `publication_status`
- `price_bucket`
- `popularity_score_7d`
- `popularity_score_30d`
- `conversion_score`
28. Обновить mapping/index lifecycle под новые поля.
29. Пересобрать индекс и прогнать reindex.
30. Добавить в `recommendation_selectors.py` OpenSearch candidate sources:
- `opensearch_similar_products`
- `opensearch_substitute_products`
- `hybrid_affinity_candidates`
- `search_recovery_candidates`
31. Смешивать OpenSearch candidates с business candidates в ranker, а не рендерить их напрямую.

### Блок 7. Rollout по поверхностям

32. Обновить `home`.
33. Обновить `PDP`.
34. Обновить `cart`.
35. Обновить `checkout`.
36. Обновить `account/orders` для reorder surfaces.
37. Прогнать rollout по feature flags.

### Блок 8. Эксперименты и контроль качества

38. Добавить A/B flags и variant logging.
39. Замерять CTR, add-to-cart rate, purchase conversion, revenue per impression, AOV uplift.
40. Сравнить old heuristic vs new ranked recommendations.
41. Отдельно следить, не падает ли checkout conversion после добавления cross-sell logic.

## Что бы я сделал первым именно в этом репозитории

Если идти самым практичным путем, я бы начал с такого vertical slice:

1. Унифицировал recommendation analytics и event schema.
2. Вынес recommendation logic из view helper-ов в сервисный слой.
3. Добавил `RecommendationSet` + Celery refresh для:
- `popular_global_7d`
- `popular_category_7d`
- `fbt`
- `personalized_home`
4. Подключил новые materialized источники в home и PDP.
5. После стабилизации метрик перенес cart/checkout на тот же pipeline.

Такой порядок даст быстрый результат, почти не рискуя checkout и не требуя переписывать проект.

## Итог

У `servio` уже есть база для recommendation system, причем она заложена в правильных местах: `shopfront`, `orders`, `analytics`, `Celery`, `OpenSearch`.

Следующий шаг не в том, чтобы "добавить еще один блок рекомендаций", а в том, чтобы превратить текущие эвристики в управляемую recommendation platform:

- с единым event schema
- с candidate/ranking split
- с materialized sets
- с Celery refresh
- с B2B-first сценариями reorder и operational-fit recommendations

Именно это даст опыт, похожий на Amazon: рекомендации будут не декоративными, а реально влияющими на поиск, выбор, докупку и повторные закупки.
