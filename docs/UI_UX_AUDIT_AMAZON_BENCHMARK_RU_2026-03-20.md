# UI/UX Audit: Актуальный Остаток После Второго Прохода

Дата: 2026-03-20

Статус: файл сокращен до реального незакрытого backlog. Все пункты, уже закрытые в коде, удалены.

## P0

### 1. Shared cart и collaborative procurement draft

Что осталось:
- общий cart/draft на компанию, а не только персональная корзина
- комментарии и mention-логика на line item
- handoff между инициатором, согласующим и закупщиком
- история изменений по draft
- lock-state и понятный ownership, чтобы несколько пользователей не перетирали правки друг друга

Почему это важно:
- это прямой аналог Amazon Business-паттерна, который снижает трение между поиском, согласованием и оплатой
- сейчас flow всё ещё слишком персональный для B2B-закупки

### 2. Guided buying до checkout, а не только внутри checkout

Что осталось:
- policy-safe guidance прямо в выдаче и на карточке товара
- preferred seller / preferred brand логика до входа в PDP
- сигнал cheaper approved alternative и faster approved alternative до клика в товар
- мягкое объяснение, почему SKU рекомендован или ограничен политикой компании

Почему это важно:
- Amazon Business выигрывает не только checkout-правилами, а ранним guidance в discovery
- сейчас guidance появляется поздно, когда пользователь уже почти принял решение

### 3. Bulk pricing и quote request flow

Что осталось:
- price breaks по объему на PDP и в cart
- CTA `Request quote` для корпоративной закупки
- запрос специальных условий из list/cart/PDP
- сценарий `compare -> select volume -> request terms`
- прозрачное состояние quote: отправлен, в работе, обновлен, принят, отклонен

Почему это важно:
- для B2B это один из самых заметных разрывов относительно Amazon Business
- текущий flow сильнее заточен под instant checkout, чем под negotiated procurement

## P1

### 4. Reorder и replenishment automation

Что осталось:
- cycle reminders по часто покупаемым SKU
- reorder suggestions по компании, команде и подразделению
- повторная закупка из order detail, invoice, favorites и saved lists как first-class CTA
- быстрый сценарий `repeat last compliant basket`

Почему это важно:
- сейчас repeat purchase уже стал лучше, но не дотягивает до полноценного replenishment loop

### 5. Seller quality scorecard 2.0

Что осталось:
- score за заполненность характеристик и совместимость атрибутов
- score за низкую конверсию PDP -> cart
- score за слабый media/document coverage по категории
- рекомендации продавцу не только что сломано, но и какой uplift это даст

Почему это важно:
- текущая seller quality queue уже полезна, но еще не стала полноценной системой роста качества ассортимента

### 6. Task-based bundles и guided baskets

Что осталось:
- наборы под сценарий работы: `open office`, `coffee point`, `new warehouse shift`, `meeting room refill`
- bundle-entry из search/category/PDP
- редактируемый basket-template с заменами approved substitutes

Почему это важно:
- это усиливает B2B use case, где пользователь часто покупает не отдельный товар, а рабочий набор под задачу

## P2

### 7. Recommendations в более операционных моментах

Что осталось:
- рекомендации сразу после add-to-cart
- рекомендации перед approval / перед отправкой на согласование
- явные add-on и substitute suggestions в order detail и reorder flow
- связка между рекомендациями и company policy, чтобы советы были не просто релевантными, а допустимыми

Почему это важно:
- рекомендации уже стали лучше на discovery/PDP, но пока не встроены в procurement loop целиком

## Вывод

Основной UI/UX слой storefront, PDP, compare, live search, checkout, buyer cockpit и seller cockpit уже доведен до заметно более amazon-like состояния. Оставшийся backlog теперь в основном про совместную B2B-закупку, раннее policy guidance, negotiated procurement и глубинную автоматизацию повторных закупок.
