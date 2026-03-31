# Frontend Plan: Recommendation Platform

Дата: 2026-03-28  
Роль: `frontend`

## Краткая оценка текущего состояния

Recommendation sections в Servio уже не пустые, но это ещё не единая recommendation platform на фронтенде. Сейчас есть полезные блоки для `home`, `pdp`, `cart`, `checkout` и `account`, но часть названий сильнее, чем данные за ними. Это нормально для переходного этапа, но нельзя выдавать эвристики и fallback-логику за честную персонализацию.

Честная оценка:

- уже хорошо: есть реальные surfaces, есть backend contract layer, есть аналитическая база для `recommendation_impression`, `recommendation_click`, `add_to_cart`, `purchase` и `recommendation_dismiss`
- временная заглушка: часть блоков пока строится на heuristics, materialized snapshots и fallback-подборках
- архитектурный долг: единый typed section contract, явные states, visibility-tracking и стабильная семантика labels
- вводит в заблуждение: любые блоки с названием вроде `Вы смотрели`, `Из ваших подписок`, `Похожие`, если под ними нет реального сигнала
- это ещё не персонализация: если `user_id` не влияет на выдачу, если нет реальной истории действий и если ranking не использует пользовательские сигналы

## Главные проблемы

| Категория | Проблема | Влияние на продукт |
|---|---|---|
| Продуктовые | Ложные labels для sections | Падает доверие к витрине |
| Продуктовые | Одинаковая подача для персональных, популярных и recovery-блоков | Пользователь не понимает, почему видит этот блок |
| Product/UX | Слишком много recommendation-блоков на одной странице | Шум, снижение CTR и рост когнитивной нагрузки |
| Data | Не везде есть честные recent views, watchlist и repeat-purchase сигналы | Нельзя называть блок персональным |
| Data | Слабая/частичная семантика `similar`, `substitute`, `accessory` | Секции выглядят похожими, но значат разное |
| Архитектурные | Нет единой slot-модели на уровне frontend | Сложно поддерживать единый UX и instrumentation |
| Архитектурные | Секции могут рендериться как обычный контент без явного lifecycle | Потеря visibility/impression accuracy |
| Аналитика | Нет стабильного различия между `rendered`, `visible`, `impressed` | Метрики не сравнимы и плохо интерпретируются |
| Performance | Personalized blocks легко раздувают SSR и cache variance | Риск для TTFB/CLS и SEO page shell |

## Целевая архитектура

Фронтенд должен работать как тонкий presentation layer над typed recommendation contracts. Названия, порядок и формат sections должны приходить из backend, а frontend обязан только честно отображать их и измерять.

### Базовые правила

- `Home`, `PDP`, `Cart`, `Checkout`, `Account` получают разные slot-типы
- первичный контент страницы не должен зависеть от recommendation blocks
- персонализированные блоки не должны менять `title`, `H1`, `canonical`, `breadcrumbs`
- для каждого блока нужен `surface`, `section_key`, `source`, `strategy`, `tracking_payload`
- если данных нет, блок не подменяется другим смыслом без смены label

### Технический принцип

Frontend не считает `similar`, `substitutes` и `accessories` сам. Он отображает уже рассчитанный backend contract и только управляет layout, state, tracking и fallback presentation.

## Какие section slots нужны

| Surface | Нужные slots | Честный label | Когда показывать |
|---|---|---|---|
| `home` | `recommended_for_you`, `recently_viewed`, `watchlist`, `popular`, `replenishment` | `Рекомендуем для вас`, `Вы смотрели`, `Из ваших подписок`, `Популярное`, `Пора пополнить` | Только если есть реальный сигнал или fallback с честным label |
| `pdp` | `similar_products`, `accessory_products`, `substitute_products`, `seller_cross_sell` | `Похожие товары`, `С этим товаром берут`, `Альтернативы`, `Другие товары этого продавца` | В зависимости от stock, affinity и content density |
| `cart` | `cross_sell`, `replenishment`, `substitutes_for_missing_items` | `Добавьте к заказу`, `Пора пополнить`, `Замены для недоступных позиций` | Только при понятной покупке-цели |
| `checkout` | `cross_sell` только в компактном виде | `Добавьте перед оплатой` | Не мешать финализации заказа |
| `account` | `reorder`, `replenishment`, `favorites_based`, `saved_search_recovery` | `Повторить заказ`, `Пора пополнить`, `Из избранного`, `Сохранённые поиски` | Только в кабинете и order detail |

## Как логировать события

Фронтенд должен различать `rendered`, `visible` и `impressed`.

| Event | Когда отправлять | Зачем |
|---|---|---|
| `section_rendered` | Секция смонтирована | Базовый факт показа UI |
| `section_visible` | Секция вошла в viewport и удержалась там | Честная видимость |
| `section_impression` | Секция реально считается увиденной | Основная denominator-метрика CTR |
| `card_impression` | Конкретная карточка попала в viewport | Аналитика выдачи и ранжирования |
| `card_click` | Пользователь открыл товар | CTR по item и section |
| `add_to_cart` | Клик по add-to-cart из секции | ATC attribution |
| `dismiss` | Пользователь скрыл блок | Негативный сигнал и UX friction |
| `purchase` | Заказ завершён и атрибутирован | CVR / GMV attribution |

Обязательные поля payload:

- `surface`
- `section_key`
- `section_title`
- `section_source`
- `strategy`
- `variant`
- `request_id`
- `position`
- `product_id`
- `visibility_ms`
- `viewport_state`

## Как не ломать SEO и производительность

- рекомендации не должны менять SEO-ядро страницы: `title`, `H1`, `canonical`, `breadcrumbs`, structured data
- первичный HTML должен оставаться полезным без рекомендаций
- персональные блоки лучше рендерить отдельным слоем, чтобы не раздувать cache variance всего page shell
- для below-the-fold блоков использовать skeleton с фиксированной высотой, чтобы не ловить CLS
- не использовать тяжёлые client-only рендеры для первых экранов
- если блок пустой или ошибочный, не подменять его случайным контентом ради заполнения места

## Как строить section contracts и states

Минимальный контракт секции должен содержать:

- `key`
- `title`
- `subtitle`
- `source`
- `strategy`
- `is_personalized`
- `tracking_payload`
- `products[]`
- `empty_reason`
- `fallback_source`
- `cta`

Минимальный contract для карточки товара:

- `id`
- `slug`
- `name`
- `image`
- `price`
- `old_price`
- `discount_pct`
- `rating`
- `review_count`
- `in_stock`
- `lead_time_days`
- `min_order_qty`
- `brand`
- `seller`
- `labels[]`
- `url`
- `add_to_cart_url`
- `reason_codes[]`

States:

- `loading`: skeleton той же плотности, что и реальная секция
- `empty`: честное объяснение, почему блока нет или почему он пустой
- `error`: тихий fallback или скрытие секции, если данных нет
- `success`: секция видна только если есть осмысленный контент

## Как различать типы блоков

| Тип блока | Как называть | Как подавать |
|---|---|---|
| Personalized | `Рекомендуем для вас` | Только если есть user signals и ranking |
| Popular | `Популярное` | Честная популярность без намёка на персонализацию |
| Accessories | `С этим товаром берут` | Компактно, с акцентом на add-to-cart |
| Substitutes | `Альтернативы` | Показывать stock, ETA и причину замены |
| Reorder | `Повторить заказ` / `Заказывают повторно` | Только на базе order history |
| Recovery | `Продолжить поиск` / `Похожие по запросу` | Только для search zero-result или narrow-result recovery |

Если сигнала нет, label должен меняться вместе с источником. Нельзя оставлять прежнее название и подсовывать другую семантику.

## Что нужно от API

Frontend нужен не “ещё один список товаров”, а typed recommendation envelope.

API должен отдавать:

- `surface`
- `variant`
- `request_id`
- `sections[]`
- `section.key`
- `section.title`
- `section.subtitle`
- `section.source`
- `section.strategy`
- `section.is_personalized`
- `section.fallback_source`
- `section.tracking_payload`
- `section.empty_reason`
- `section.products[]` с полями карточек

Также нужны:

- стабильный `request_id` для attribution
- `experiment_variant` для A/B и shadow/canary
- честный `source` (`django-inline`, `fastapi`, `fallback`)
- `empty_reason` и `fallback_source`, чтобы frontend не гадал, почему секция пропала

## Ошибки текущего UI

- одинаковые карточки и одинаковая плотность для разных intent-сценариев
- `recommendation`-блоки без явного source label
- отсутствие visibility-tracking, из-за чего impression rate и CTR искажены
- silent fallback на другой тип секции без смены подписи
- слишком агрессивные personalized blocks на ранних этапах страницы
- отсутствие честного empty state
- отсутствие разделения `popular` и `personalized` в визуальном языке
- попытка компенсировать пустую рекомендацию случайным контентом

## Итог

Фронтенд-цель не в том, чтобы “показать блоки”. Цель в том, чтобы пользователь понимал, что это за блок, почему он появился и как на него реагировать. Только после этого рекомендации можно честно измерять, сравнивать и улучшать.
