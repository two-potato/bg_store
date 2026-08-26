# Recommendation Stage 1 Label Matrix

Дата: 2026-03-28  
Пакет: backlog `064`  
Роль: `uiux`

## Цель

Зафиксировать честные `labels`, `disclosure` и `empty-state` правила для recommendation sections Servio.

Правило Stage 1 простое:

- если сигнал есть, называем его точно
- если сигнала нет, не притворяемся
- если fallback произошёл, это должно быть видно

## 1. Матрица section types -> allowed labels -> forbidden labels

| Section type | Allowed labels | Forbidden labels |
| --- | --- | --- |
| `personalized_home` | `Рекомендуем для вас`, `Подобрано для вас` только если user-specific signals реально участвуют | `Рекомендуем для вас` без user contribution, `Персонально подобрано` при popularity fallback |
| `recently_viewed` | `Вы смотрели`, `Продолжить просмотр` только при real recent views | `Вы смотрели` без history, `Продолжить просмотр` без session/user history |
| `watchlist` / subscriptions | `По вашим подпискам`, `Из ваших подписок` только при реальных brand/category subscriptions | `Из ваших подписок` без subscriptions, `По вашим подпискам` при popularity-only fallback |
| `popular` | `Популярное`, `Популярное в Servio` | Любой label с намёком на персонализацию |
| `replenishment` | `Пора пополнить`, `Повторная закупка`, `Заказывают повторно` | `Пора пополнить` без repeat-purchase signal, `Заказывают повторно` без order history |
| `similar_products` | `Похожие товары`, `Похожие по категории` | `Похожие товары` только по popularity, `Персонально подобрано` |
| `accessory_products` | `С этим товаром берут`, `Добавьте к заказу` | `С этим товаром берут` без co-purchase/accessory signal, `Рекомендуем` без контекста |
| `substitute_products` | `Альтернативы`, `Замены` | `Альтернативы` без stock-aware substitute logic, `Часто покупают вместе` |
| `cart_cross_sell` | `Добавьте к заказу`, `Ещё к заказу` | `Рекомендуем для вас` в корзине без контекста, `Часто покупают вместе` без сигнала |
| `checkout_cross_sell` | `Добавьте перед оплатой`, `Последний шанс усилить заказ` только в very compact form | Любые агрессивные promo labels, любые labels, мешающие checkout |
| `reorder` | `Повторить заказ`, `Вернуться к закупке` | `Вы смотрели`, `Популярное` для reorder flow |
| `search_recovery` | `Возможно, вы искали`, `Похожие по запросу`, `Продолжить поиск` | `Рекомендуем для вас`, `Популярное`, `Часто покупают вместе` |

## 2. Disclosure rules

Disclosure нужен, если пользователь может неверно понять, почему блок показан.

### Когда нужен `subtitle`

- у `personalized` блоков
- у `replenishment` и `reorder`
- у `substitutes`
- у `search_recovery`
- у любого блока, который может деградировать в fallback

### Когда нужен `why-this` disclosure

- если в блоке есть user-specific ranking
- если label звучит персонально
- если секция использует subscriptions, history, saved intent или repeat purchase

### Когда нужен `fallback explanation`

- если `engine_source != source`
- если `fallback_source` заполнен
- если section стала generic/popular вместо персональной
- если пустой персональный блок был заменён на другой intent

### Формулировки disclosure

- `Основано на ваших просмотрах и заказах`
- `Популярные позиции без персонализации`
- `Подобрано как альтернатива по наличию и назначению`
- `Показано как запасной вариант, потому что персональная выдача пустая`

## 3. Empty-state rules

### Когда секцию скрываем

- нет данных
- нет честного label для fallback
- секция не несёт коммерческой пользы
- показывать блок означало бы врать о сигналах

### Когда показываем честное объяснение

- персональная секция пустая, но для trust нужно объяснить почему
- блок стал пустым из-за отсутствия eligible items
- section была снижена до fallback, и это важно для понимания

### Empty-state templates

- `Пока нет данных для этой подборки`
- `Нет товаров, подходящих под текущий контекст`
- `Пока не нашли честную замену`
- `Покажем блок, когда появятся сигналы`

### Чего делать нельзя

- подставлять случайные товары под старый label
- заменять персональную секцию на popular без смены названия
- показывать empty state с маркетинговым текстом вместо объяснения

## 4. Surface-by-surface правила

### `home`

- можно: `personalized`, `popular`, `replenishment`, `recently_viewed`, `watchlist`
- нельзя: все intents одновременно на первом экране
- порядок: `personalized` -> `popular` -> `replenishment` -> `recently_viewed` -> `watchlist`

### `pdp`

- можно: `similar`, `accessories`, `substitutes`, `seller_cross_sell`
- нельзя: `Вы смотрели` как основной PDP блок, если это не PDP history flow
- `substitutes` должны явно показывать, что это замена, а не просто похожий товар

### `cart`

- можно: `cross_sell`, `replenishment`, `substitutes_for_missing_items`
- нельзя: агрессивный персональный маркетинг
- блоки должны помогать завершить заказ, а не уводить пользователя из checkout path

### `checkout`

- можно: очень компактный `cross_sell`
- нельзя: большие recommendation-карточки, агрессивные promo labels, шумные секции
- главный приоритет здесь — завершение покупки

### `account`

- можно: `reorder`, `replenishment`, `favorites_based`, `saved_search_recovery`
- нельзя: подмена account intent общим marketplace discovery
- здесь рекомендации должны выглядеть как инструмент повторной закупки

## 5. Что прекратить использовать немедленно

Ниже паттерны, которые надо убрать из продукта, если нет доказанного сигнала:

- `Подобрано для вас` без user-specific contribution
- `Вы смотрели` без реальной recent history
- `Из ваших подписок` без реальных subscriptions
- `Часто покупают вместе` без co-purchase или accessory signal
- `С этим товаром берут` без accessory logic
- `Персонально подобрано` для popularity fallback
- `Возможно, вы искали` вне search recovery
- `Последний шанс усилить заказ` в noisy checkout context

## 6. Stage 1 truth rule

Если label нельзя честно объяснить за 1 фразу, label не проходит Stage 1.

Если секция не может быть объяснена без притворства, секцию надо скрыть.

Если fallback случился, он должен быть виден в copy и в payload.
