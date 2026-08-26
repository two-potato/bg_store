# UX Handoff: Cart, Buyer Orders, Buyer Account

Дата: 2026-03-27  
Роль: `uiux`  
Контур: migration wave `auth/cart/account` для нового `Next.js storefront`

## 1. Текущее состояние

### Legacy storefront
- `cart` уже реализован как рабочий purchase-flow: seller grouping, quantity stepper, clear cart, subtotal/discount/coupon/total, empty state, checkout CTA, reorder/cross-sell рекомендации.
- `buyer account` уже реализован как рабочее пространство закупщика, а не просто профиль: dashboard, orders, order detail, tracking, addresses, legal entities, notifications, preferences, comments.
- `orders` уже покрывают repeat purchase, timeline заказа, approval context, payment retry, invoice, cancel, reorder, claims, support, shipment tracking.

### Текущий Next storefront
- В `frontend/` есть только public storefront.
- Для `cart`, `buyer orders`, `buyer account` в новом storefront пока нет собственных экранов.
- В shell уже есть ссылки на `/cart/`, `/account/login/`, `/favorites/`, но UX-контур buyer-side ещё не перенесён.

### Вывод
- В этом пакете нельзя делать "красивый профиль" без рабочего purchase-ядра.
- Первый UX-приоритет: сохранить критичные buyer сценарии 1:1 по смыслу, но упростить навигацию, мобильное поведение и иерархию действий.

## 2. Route Map

### Cart
- `/cart` — основная корзина

### Buyer account core
- `/account` — buyer dashboard
- `/account/orders` — список заказов
- `/account/orders/[id]` — детали заказа
- `/account/orders/[id]/tracking` — tracking page
- `/account/addresses` — адреса доставки
- `/account/legal` — компании и B2B workspace
- `/account/notifications` — уведомления
- `/account/preferences` — коммуникационные настройки

### Связанные, но не ядро первой волны
- `/favorites`
- `/lists`
- `/saved-searches`
- `/compare`

### Не включать в этот пакет
- `/checkout/**`
- `/account/approvals/`
- `/account/comments/`
- `/account/seller/**`
- `/account/marketplace/**`

## 3. IA экранов

## 3.1 `/cart`

### Цель экрана
- быстро проверить состав корзины
- скорректировать количество
- понять итог и скидки
- перейти в checkout без лишних шагов

### IA
1. `Page header`
   - breadcrumb
   - `h1`
   - secondary action `Очистить корзину`, если есть товары
2. `Cart groups`
   - seller card
   - seller name
   - seller subtotal
   - list of line items
3. `Line item`
   - image
   - product name
   - price per unit
   - sku
   - quantity control
   - remove action
   - row total
4. `Order summary`
   - subtotal
   - profile discount
   - coupon discount
   - total
   - split-order info block при нескольких sellers
5. `Primary CTA block`
   - `Оформить заказ`
   - secondary `Продолжить покупки`
6. `Supportive blocks`
   - reorder recommendation block, если корзина пуста
   - cross-sell block, если корзина не пуста

## 3.2 `/account`

### Цель экрана
- показать ежедневный buyer workload
- сократить путь к заказам, approvals, повторным закупкам, адресам и компаниям

### IA
1. `Hero`
   - workspace title
   - short subtitle
   - CTA `Перейти в каталог`
   - CTA `Открыть заказы`
2. `Focus today`
   - approvals count
   - reorder entry
   - notifications count
   - companies/addresses entry
3. `Procurement queue`
   - unpaid orders
   - invoices
   - claims/support
   - company context
4. `Repeat purchase`
   - reorder recommendations
   - replenishment recommendations
5. `Operational metrics`
   - orders
   - profile discount
   - entities/addresses
   - favorites/saved searches
   - lists
6. `Secondary actions`
   - catalog
   - orders
   - companies
   - addresses
   - lists
   - favorites
   - compare
   - saved searches
7. `Profile block`
   - full name
   - phone
   - contact email
   - photo
   - telegram status

## 3.3 `/account/orders`

### Цель экрана
- дать buyer быструю ленту заказов и короткий путь к повторной закупке

### IA
1. `Compact hero`
   - page title
   - helper copy
2. `Orders list/table`
   - order id
   - created at
   - status
   - approval status
   - total
   - primary row CTA `Открыть`
3. `Top actions`
   - `Перейти в каталог`
   - `Черновики закупки`
4. `Reorder block`
   - products derived from order history

## 3.4 `/account/orders/[id]`

### Цель экрана
- быть единым рабочим экраном по заказу
- не заставлять buyer искать документы, оплату, tracking и support в разных местах

### IA
1. `Compact hero`
   - order id
   - summary subtitle
2. `Top metrics`
   - order status
   - approval status
   - total
3. `Procurement timeline`
   - created
   - approval
   - invoiced
   - paid
   - packed
   - shipped
   - delivered
   - claim state
4. `Repeat purchase block`
5. `Main content`
   - order items table
6. `Right rail / mobile stacked blocks`
   - order meta
   - payment and retry payment
   - legal entity / address
   - coupon / comment
   - approval decision block, если доступен
   - seller split summary
   - seller fulfillment summary
   - totals
   - action stack
   - invoice download
   - tracking
   - cancel
   - reorder
   - save as procurement list
   - approval history
   - claims block
   - support block

## 3.5 `/account/orders/[id]/tracking`

### Цель экрана
- отдельный быстрый экран отслеживания, особенно для mobile и прямых ссылок из уведомлений

### IA
1. compact hero
2. list of seller shipments
3. each shipment card:
   - seller name
   - shipment status
   - tracking number
   - delivery method
   - warehouse
   - updated at

## 3.6 `/account/addresses`

### IA
1. addresses list
2. add address form
3. geolocation assist
4. set default action
5. CTA to checkout as secondary action only

## 3.7 `/account/legal`

### IA
1. memberships list
2. company workspaces block
3. legal requests block
4. new request form
5. INN preview helper

## 3.8 `/account/notifications`

### IA
1. simple event feed
2. each event navigates to order/support-related destination

## 3.9 `/account/preferences`

### IA
1. grouped communication toggles
2. save CTA

## 4. Ключевые CTA

### Cart
- Primary: `Оформить заказ`
- Secondary: `Продолжить покупки`
- Tertiary: `Очистить корзину`
- Inline: `+`, `−`, `Удалить`

### Buyer dashboard
- Primary: `Открыть заказы`
- Secondary: `Перейти в каталог`
- Contextual: `Перейти к согласованию`, `Повторить закупку`, `Открыть компании`, `Открыть адреса`

### Orders list
- Primary: `Открыть заказ`
- Secondary: `Перейти в каталог`
- Secondary: `Черновики закупки`

### Order detail
- Primary: `Повторить заказ`
- Secondary: `Скачать invoice PDF`
- Secondary: `Tracking page`
- Secondary: `Сохранить как список закупок`
- Conditional: `Повторить оплату`
- Conditional: `Отменить заказ`
- Conditional: `Согласовать` / `Отклонить`
- Supportive: `Создать обращение`, `Отправить в поддержку`

### Addresses / legal / preferences
- Primary: `Сохранить`
- Secondary: `Открыть checkout` или `Перейти в каталог` только как контекстные ссылки

## 5. Состояния

## 5.1 Loading

### Обязательные правила
- На `cart` не использовать full-page spinner при изменении количества.
- Для line item quantity использовать row-level pending state.
- Для totals использовать optimistic refresh с защищённым disabled state у checkout CTA.
- На `orders list` использовать skeleton списка, а не пустую таблицу.
- На `order detail` сначала рендерить summary shell, затем timeline/items/side rail.
- На `addresses` и `legal` формы сохранять layout-стабильность при submit.

## 5.2 Empty

### Cart
- Empty headline: `Корзина пуста`
- Primary CTA: `Перейти в каталог`
- Below: reorder block из прошлых покупок

### Orders
- Empty headline: `У вас пока нет заказов`
- Primary CTA: `Перейти в каталог`
- Secondary CTA: `Открыть списки закупок`

### Notifications
- Plain empty feed without illustration overload

### Addresses / legal
- Empty should immediately explain why section matters for checkout/B2B

## 5.3 Error

### Cart
- quantity update error must stay inline on item level
- cart summary errors must stay above totals
- checkout CTA error must not clear current cart state

### Orders / account
- order detail fetch error must preserve back navigation to `/account/orders`
- mutation errors for cancel, reorder, support, claims, profile save should appear near the form/action source

## 5.4 Success

### Cart
- add/remove/update quantity should show compact toast or inline confirmation, not page jump

### Account
- profile, preferences, addresses, legal request, claims, support should each have visible success feedback

### Orders
- reorder success should explain where user landed:
  - cart updated
  - skipped unavailable items
  - added partial quantity if stock changed

## 6. Mobile-first поведение

### Cart
- summary block закреплять после списка товаров нельзя, если это мешает контенту; на mobile лучше stacked footer CTA after summary
- quantity control должен оставаться tappable одной рукой
- row layout должен переноситься в two-row structure:
  - row 1: image + title + price
  - row 2: qty controls + remove + row total

### Buyer account
- desktop sidebar не переносить 1:1
- на mobile account navigation должен стать:
  - top segmented switch для ключевых разделов
  - либо compact drawer
- dashboard cards должны быть одно-колоночными
- action overload в hero недопустим: максимум 2 CTA above the fold

### Orders
- order list на mobile не таблица, а cards
- order detail side rail на mobile должен становиться последовательным action stack после состава заказа
- timeline должен быть vertical и touch-readable

### Forms
- addresses/legal/preferences/profile: single-column, large touch targets, sticky save button не обязателен

## 7. Trust / policy / reorder / support blocks

### Trust and policy
- В `cart` сохранить seller grouping и explanatory block про multi-seller context.
- В `order detail` обязательно сохранить:
  - approval status
  - approval progress
  - approval policy summary
  - payment status
  - invoice access
  - delivery method
  - legal entity

### Reorder
- Reorder нужен в трёх местах:
  - empty cart
  - orders list
  - order detail
- Reorder не должен прятаться внизу страницы после support forms.
- Reorder CTA должен обещать предсказуемый результат, а не "магическое" восстановление заказа.

### Support
- `claims` и `support` на order detail сохраняем как buyer-safe actions.
- Их нельзя уводить в отдельный кабинет поддержки на этом этапе.
- Для mobile это должны быть простые раскрывающиеся блоки под action stack.

## 8. Что переносим 1:1

- seller grouping в cart
- quantity stepper
- clear cart action
- totals summary: subtotal, profile discount, coupon discount, total
- empty cart + CTA to catalog
- dashboard logic `focus today`
- procurement queue на buyer home
- orders list как отдельный entry point
- order timeline
- reorder blocks
- order actions: invoice, tracking, reorder, cancel, save as list
- claims/support формы в рамках order detail
- addresses section
- legal entities section
- notifications
- preferences

## 9. Что нужно улучшить относительно legacy

### Cart
- убрать ощущение "списка форм"; Next-версия должна выглядеть как единый cart workspace
- явнее отделить item controls от destructive action
- на mobile усилить иерархию total -> CTA

### Buyer dashboard
- legacy перегружен большим числом entry points
- в Next first screen должен показывать только buyer-critical actions
- profile editing лучше опустить ниже operational blocks

### Orders list
- вместо чистой таблицы нужен adaptive list/cards
- добавить быстрые фильтры во второй итерации, но не блокировать first ship

### Order detail
- legacy right rail перегружен
- в Next action group нужно разделить на:
  - payment/documents
  - delivery/tracking
  - reorder/list actions
  - issue resolution
- approval history, seller fulfillment и claims/support должны быть collapsible на mobile

### Addresses / legal
- формы должны выглядеть как продуктивные инструменты, а не как raw admin-like inputs
- helper copy должна объяснять, где данные будут использоваться

## 10. Что frontend должен реализовать первым шагом

### Обязательный first ship
1. `/cart`
2. `/account`
3. `/account/orders`
4. `/account/orders/[id]`

### Почему именно так
- Это минимальный рабочий buyer loop:
  - собрать корзину
  - увидеть history
  - открыть заказ
  - повторить закупку

### Что допустимо временно оставить ссылкой на legacy
- `/account/orders/[id]/tracking`
- `/account/addresses`
- `/account/legal`
- `/account/notifications`
- `/account/preferences`

### Frontend baseline for first ship
- единый `account layout`
- mobile navigation for account sections
- shared cards/tables/list item patterns
- reusable status badges
- reusable action stack
- skeletons for cart/orders/detail
- toast/inline feedback model for mutations

## 11. Что не переносить в этом пакете

- checkout step forms
- approval inbox как отдельный список
- comments / reviews cabinet
- favorites / lists / compare / saved searches как самостоятельные новые Next-экраны
- seller-specific order splits as отдельный buyer UX surface beyond summary
- deep finance/admin workflows

## 12. Требования к frontend handoff

### Компонентный состав
- `CartPage`
- `CartSellerGroup`
- `CartLineItem`
- `CartSummary`
- `AccountLayout`
- `AccountNav`
- `BuyerDashboard`
- `OrdersList`
- `OrderCardMobile`
- `OrderDetailSummary`
- `OrderTimeline`
- `OrderActionStack`
- `OrderClaimsBlock`
- `OrderSupportBlock`
- `AddressBookPage`
- `LegalEntitiesPage`

### UX требования
- keyboard-friendly quantity controls
- aria-live или эквивалент для cart mutations
- не использовать только цвет для статусов
- минимизировать full reload behavior
- всегда оставлять ясный путь назад к каталогу и списку заказов

## 13. Нужные API-ожидания от frontend к backend/architect

### Уже нужны для first ship
- `cart get`
- `cart add/update/remove/clear`
- `cart totals with discount/coupon state`
- `buyer account dashboard summary`
- `orders list`
- `order detail`
- `reorder action`

### Нужны до завершения всей wave
- `tracking detail`
- `addresses CRUD`
- `legal entities + requests`
- `notifications feed`
- `preferences update`
- `claims create/list`
- `support ticket create/list`
- явный response contract для partial reorder:
  - added
  - unavailable
  - qty adjusted

## 14. Аналитика

### Обязательные события
- `cart_viewed`
- `cart_qty_incremented`
- `cart_qty_decremented`
- `cart_item_removed`
- `cart_cleared`
- `cart_checkout_clicked`
- `account_dashboard_viewed`
- `orders_list_viewed`
- `order_detail_viewed`
- `order_tracking_viewed`
- `order_reorder_clicked`
- `order_cancel_submitted`
- `invoice_download_clicked`
- `claim_created`
- `support_ticket_created`
- `address_created`
- `legal_request_created`

### Что важно передать в payload
- order id
- product ids
- seller count
- total value
- approval state
- customer type
- source surface
- reorder result type

## 15. Риски

### UX риски
- перенести sidebar account 1:1 и сломать mobile
- оставить order detail перегруженным и нечитаемым
- спрятать reorder слишком низко
- сделать cart как форму из множества кнопок без ясной иерархии

### Accessibility риски
- quantity controls без корректных aria-label
- status-only color coding
- слишком плотные action stacks на mobile
- toast-only success without persistent confirmation

### Product risks
- без ясного reorder contract UX будет обещать больше, чем backend гарантирует
- без account summary API buyer dashboard превратится в пустую оболочку

## 16. Итог для frontend

Если выбирать только один критерий качества, то эта wave должна ощущаться как `рабочее место закупщика`, а не как набор разрозненных страниц.  
Первым ship нужен короткий и надёжный loop: `cart -> account dashboard -> orders list -> order detail -> reorder`.  
Все остальные buyer-инструменты можно временно оставить как связанный legacy-contour, пока frontend не соберёт устойчивое ядро.
