# Recommendation Stage 1 Frontend Integration

Дата: 2026-03-28  
Пакет: backlog `066`  
Роль: `frontend`

## 1. Storefront integration rules

Frontend на Stage 1 работает как честный presentation layer над backend contract, а не как генератор собственной семантики.

### Базовые правила

- `section.key`, `section.title`, `section.source`, `section.strategy` приходят из contract payload и не придумываются на фронте.
- `frontend` не должен переименовывать секцию так, чтобы скрыть смену source или fallback.
- `personalized` label разрешён только если backend truth-model и contract baseline подтверждают user-specific contribution.
- `popular`, `recovery`, `materialized`, `bootstrap` должны оставаться различимыми в UI и payload.
- первичный page content не должен зависеть от recommendation blocks.
- recommendation blocks не меняют `H1`, `title`, `canonical`, `breadcrumbs`, structured data.
- если `fallback_source` или `empty_reason` присутствуют, frontend обязан показать это честно или скрыть секцию.

### Surface behavior

- `home`: можно показывать `recommended_for_you`, `popular`, `replenishment`, `recently_viewed`, `watchlist`.
- `pdp`: можно показывать `similar_products`, `accessory_products`, `substitute_products`, `seller_cross_sell`.
- `cart`: можно показывать `cross_sell`, `replenishment`, `substitutes_for_missing_items`.
- `checkout`: только узкий `cross_sell`, если он не мешает завершению заказа.
- `account`: `reorder`, `replenishment`, `favorites_based`, `saved_search_recovery`.

## 2. Required payload fields

### Envelope-level fields

- `recommendation_id`
- `surface`
- `variant`
- `source`
- `service_source`
- `engine_source`
- `fallback_source`
- `empty_reason`
- `latency_ms`

### Section-level fields

- `key`
- `title`
- `source`
- `strategy`
- `tracking_payload`
- `impression_id`
- `fallback_source`
- `empty_reason`
- `products[]`

### Product-level fields

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

### Usage rules

- `recommendation_id` нужен для склейки exposure -> click -> add_to_cart -> purchase.
- `impression_id` нужен для секционной атрибуции и parity checks.
- `engine_source` и `service_source` нужны для честной диагностики `django-inline` vs `fastapi`.
- `fallback_source` и `empty_reason` нужны, чтобы frontend не угадывал причину изменения секции.
- `latency_ms` нужен для platform observability и UX/performance gates.

## 3. Instrumentation plan

### Event model

Frontend должен различать `rendered`, `visible`, `impression`, `click`, `add_to_cart`, `dismiss`.

### When to send

- `rendered`: секция смонтирована на странице.
- `visible`: секция вошла в viewport и удержалась там.
- `impression`: секция реально засчитана как увиденная.
- `click`: пользователь открыл товар из секции.
- `add_to_cart`: пользователь добавил товар из секции.
- `dismiss`: пользователь скрыл или убрал секцию.

### Minimum payload

- `request_id`
- `recommendation_id`
- `impression_id`
- `surface`
- `section_key`
- `section_title`
- `section_source`
- `strategy`
- `variant`
- `position`
- `product_id`
- `visibility_ms`
- `viewport_state`
- `engine_source`
- `service_source`
- `fallback_source`
- `empty_reason`

### Rules

- `rendered` не равен `impression`.
- `visible` не равен `impression`.
- `impression` нельзя отправлять без корректного `section_key`.
- `click` и `add_to_cart` должны наследовать `recommendation_id` и `impression_id`.
- `dismiss` должен сохранять `surface` и `section_key`, иначе negative feedback теряется.

## 4. Blockers and risks

### Blockers

- Нет честного `truth-model` -> нельзя корректно выбирать labels.
- Нет `contract baseline` -> нельзя гарантировать нужные поля в payload.
- Нет `fallback_source` и `empty_reason` -> нельзя честно показать деградацию.
- Нет секционной instrumentation -> CTR и impression rate будут врать.

### Risks by surface

- `home`: риск перегрузить первый экран и смешать personal с popular.
- `pdp`: риск показать `similar` как ложную персонализацию.
- `cart`: риск увести пользователя от checkout.
- `checkout`: риск добавить шум и снизить conversion.
- `account`: риск превратить кабинет в витрину вместо инструмента повторной закупки.

## 5. Is Stage 1 baseline enough for Stage 2?

Коротко: для честного старта Stage 2, да, baseline уже достаточен как source-of-truth, но только для controlled execution.

Что это значит:

- можно начинать Stage 2 planning, integration design и surface-by-surface rollout prep;
- нельзя считать Stage 2 уже достигнутым;
- нельзя включать Stage 2 rollout без QA/devops gates и без подтверждения, что frontend реально соблюдает contract and truth rules.

## 6. Итог

Stage 1 baseline уже достаточен, чтобы frontend начал работать по единой контрактной модели и не врал про персонализацию.

Недостаточно только одного: забыть про `empty/fallback/truth` и начать рендерить красивые блоки без измеримости. Именно этого Stage 1 и не допускает.
