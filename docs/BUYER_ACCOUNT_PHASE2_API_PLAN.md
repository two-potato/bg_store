# Buyer Account Phase 2 API Plan

Дата: 2026-03-27
Пакет: backlog `012`
Роль: `architect`

## 1. Контекст

После partial delivery уже есть:

- `buyer account bootstrap` для shell/dashboard из `shopfront/views/storefront_bridge.py`
- `orders list/detail/create` в `backend/orders/api`
- `favorite/compare/subscription toggle` в `shopfront/views/discovery.py`
- public catalog API, которого хватает для product enrichment

Не хватает page-level buyer account API для `favorites`, `lists`, `saved searches`, `account settings`, а также минимального event contract для wave `cart/account/orders`.

## 2. Что нужно первым

### Priority A. Закрыть account settings contract

Это блокирует перенос buyer account core и не требует включать `checkout` или `seller`.

Нужны:

- `GET /api/storefront/account/settings`
  - единый bootstrap для `addresses`, `legal_entities`, `notifications`, `preferences`
  - counts, links, current profile summary
- `GET /api/storefront/account/addresses`
- `POST /api/storefront/account/addresses`
- `PATCH /api/storefront/account/addresses/:id`
- `DELETE /api/storefront/account/addresses/:id`
- `GET /api/storefront/account/legal-entities`
  - memberships
  - company workspace summary
  - pending creation requests
- `POST /api/storefront/account/legal-entities/requests`
- `POST /api/storefront/account/legal-entities/requests/:id/cancel`
- `GET /api/storefront/account/notifications`
  - feed list
  - unread counters if есть в модели/сервисе
- `GET /api/storefront/account/preferences`
- `PATCH /api/storefront/account/preferences`

Почему первым:

- это buyer account core, а не optional discovery surface
- сейчас там legacy HTML/HTMX forms и redirects
- frontend иначе упрётся в form-post + message framework

### Priority B. Закрыть favorites/lists/saved searches как самостоятельные buyer surfaces

Нужны:

- `GET /api/storefront/favorites`
  - list
  - pagination or cursor
  - product cards с `is_favorite=true`
  - empty state metadata
- `POST /api/storefront/favorites/toggle`
  - можно оставить текущий toggle endpoint, если backend подтвердит стабильный contract

- `GET /api/storefront/lists`
  - list of saved lists
  - counts
  - preview items
- `POST /api/storefront/lists`
- `GET /api/storefront/lists/:id`
- `PATCH /api/storefront/lists/:id`
- `DELETE /api/storefront/lists/:id`
- `POST /api/storefront/lists/:id/items`
- `PATCH /api/storefront/lists/:id/items/:productId`
- `DELETE /api/storefront/lists/:id/items/:productId`
- `POST /api/storefront/lists/:id/move-to-cart`
- `POST /api/storefront/lists/create-from-favorites`
- `POST /api/storefront/lists/create-from-order/:orderId`

- `GET /api/storefront/saved-searches`
- `POST /api/storefront/saved-searches`
- `PATCH /api/storefront/saved-searches/:id`
- `DELETE /api/storefront/saved-searches/:id`

Почему вторым:

- это уже самостоятельные buyer tools
- часть точечных мутаций есть, но полноценных list/detail contracts нет
- без этого Next будет вынужден опираться на legacy HTML pages

### Priority C. Минимальный event contract для wave `cart/account/orders`

Нужны единые same-origin ingest contracts, без переноса продуктовой аналитики в frontend.

- `POST /analytics/cart-feedback/`
  - `cart_view`
  - `cart_item_add`
  - `cart_item_update`
  - `cart_item_remove`
  - `cart_clear`
  - `cart_checkout_cta_click`
- `POST /analytics/account-feedback/`
  - `account_dashboard_view`
  - `account_nav_click`
  - `account_addresses_create`
  - `account_addresses_update`
  - `account_legal_request_create`
  - `account_preferences_save`
  - `favorites_view`
  - `saved_lists_view`
  - `saved_searches_view`
- `POST /analytics/order-feedback/`
  - `orders_list_view`
  - `order_detail_view`
  - `order_reorder_click`
  - `order_tracking_view`

Минимальные поля события:

- `event`
- `ui_surface`
- `page_type`
- `request_id`
- `order_id` при наличии
- `list_id` при наличии
- `product_id` при наличии
- `source`
- `search_attribution` или `recommendation_source`, если событие связано с cart/list/order repeat flow

## 3. Что может остаться в legacy ещё на одну волну

Это не должно блокировать phase 2:

- `/account/comments/`
- shared saved lists
- advanced compare page, если toggle уже есть и page migration не критичен
- rich notification center actions beyond read-only feed
- сложные company workspace flows внутри `legal entities`, если они не нужны для базового buyer account UX
- order-adjacent документы/claims, если они не входят в partial delivery scope

## 4. Рекомендуемая последовательность

1. Stabilize `account settings` API.
2. Дать `favorites/lists/saved searches` page-level contracts.
3. Зафиксировать минимальный analytics ingest contract для new wave.
4. После этого запускать `frontend` на completion buyer account surfaces.
5. Потом отдельно закрывать `order detail extras`, если их не хватает после backlog `011`.

## 5. Архитектурные границы

Во frontend нельзя переносить:

- address validation rules и ownership checks
- legal entity membership logic
- notification/preferences business rules
- saved list merge/upsert rules
- reorder/cart transfer business logic
- analytics attribution assembly, если она зависит от backend session/search/recommendation state

## 6. Короткий вывод для следующего пакета

Если нужно выбрать только один следующий backend пакет, то это:

`account settings + lists/saved searches read-write API + minimal analytics ingest for cart/account/orders`

Этого достаточно, чтобы `frontend` и `uiux` добили buyer account wave без захода в `checkout` и без преждевременного расширения seller/account ops.
