# Catalog Redesign Stage 1 Architecture

Дата: 2026-03-27  
Роль: `architect`

## 1. Цель

Запустить первый этап полного редизайна Servio через 3 рабочие концепции страницы каталога:

- `A` — классика маркетплейса
- `B` — mobile-first
- `C` — быстрый выбор / супермаркет

Цель шага 1 не в том, чтобы сразу переделать весь продукт, а в том, чтобы:

- зафиксировать единую UX-логику будущего редизайна
- проверить 3 разные модели выбора товара
- реализовать их в рабочем виде на Next.js App Router
- выбрать базовый каталог-паттерн, который потом станет основой для home, PDP, cart, checkout и account surfaces

Ключевое ограничение: `frontend` не начинает реализацию до утверждённого UX.

## 2. Почему это важно

Текущий дизайн не принят не из-за недостатка “визуала”, а из-за слабой продуктовой логики:

- каталог должен ускорять поиск и выбор
- интерфейс должен быть утилитарным, а не декоративным
- mobile UX должен быть не адаптацией desktop, а полноценным сценарием выбора
- вся дальнейшая пересборка продукта должна опираться на одну дизайн-систему, а не на разрозненные экраны

Если начать с хаотичного редизайна “по страницам”, мы получим визуально разные паттерны и сломаем migration discipline. Каталог — правильная точка старта, потому что именно он задаёт:

- плотность интерфейса
- фильтрацию
- карточку товара в листинге
- поисковое поведение
- логику сравнения и добавления в корзину

## 3. Какие домены затрагиваются

На шаге 1 затрагиваются:

- `frontend/app/(public)/catalog`
- `frontend/app/(public)/search`
- `frontend/components/product-card.tsx`
- design-system слой storefront
- каталоговые filters/sort/search controls
- mobile navigation каталога
- route-level переключение между `/catalog-a`, `/catalog-b`, `/catalog-c`

Косвенно затрагиваются как будущие потребители дизайн-системы:

- `home`
- `PDP`
- `cart`
- `checkout`
- `account`
- `orders`
- `favorites`
- `addresses`
- `settings`

Не затрагиваются в шаге 1:

- backend API contracts
- checkout business logic
- seller surfaces
- admin
- bot

## 4. Пошаговый план

### Шаг 1. Архитектурная рамка

Зафиксировать продуктовые принципы и границы:

- ориентир на Яндекс Маркет + grocery UX
- функциональность > визуал
- цена, наличие и CTA важнее декоративных решений
- единая grid-система 4/8px
- единая логика filters, cards, sorting, availability, add-to-cart

### Шаг 2. UX-концепции

`uiux` готовит [docs/CATALOG_REDESIGN_CONCEPTS.md](./CATALOG_REDESIGN_CONCEPTS.md) с 3 концепциями:

- структура экрана
- сценарий пользователя
- filters behavior
- карточка товара
- mobile UX
- плюсы / минусы / trade-offs

Выход шага 2 — утверждённый UX-пакет, а не код.

### Шаг 3. Approval gate

Перед стартом `frontend` должны быть явно выбраны:

- базовая grid-логика
- единая card language
- общие catalog tokens
- правило переключения между концепциями
- границы того, что отличается между `A/B/C`

Если этого нет, `frontend` не стартует.

### Шаг 4. Frontend implementation

После approval:

- поднять `/catalog-a`
- поднять `/catalog-b`
- поднять `/catalog-c`
- добавить переключатель между концепциями
- сохранить один data layer и один backend API surface

Различия между концепциями допускаются только в:

- density
- user flow
- filters behavior
- product selection pattern

Различия не должны жить в разных API, разных карточках “по настроению” или хаотичных layout rules.

### Шаг 5. Validation

После реализации сравнить концепции по:

- скорости нахождения товара
- количеству кликов до add-to-cart
- понятности mobile сценария
- читаемости цены, скидки, рейтинга, наличия
- устойчивости filters/sort/search

### Шаг 6. Выбор базовой модели

По результатам сравнения выбрать:

- основной catalog pattern
- secondary ideas, которые стоит забрать из альтернатив
- то, что переносится в полный редизайн home/PDP/cart/account

## 5. Какие агенты нужны

### `architect`

- держит рамку
- контролирует границы
- не даёт смешать разные продуктовые модели

### `uiux`

- создаёт 3 UX-концепции
- фиксирует дизайн-систему и interaction rules
- не уходит в декоративный дизайн

### `frontend`

- стартует только после UX approval
- реализует `/catalog-a`, `/catalog-b`, `/catalog-c`
- обновляет Next.js / Node.js stack в рамках согласованного пакета

### `qa_metrics`

- сравнивает концепции по сценариям
- ставит smoke на `/catalog-a|b|c`
- проверяет mobile и critical catalog interactions

### `devops`

- нужен только на этапе stack upgrade / runtime validation
- не нужен до approval UX

### `backend`

- в шаге 1 не нужен, если текущих catalog/search contracts хватает
- подключается только при выявленном API gap

## 6. Риски

### 1. Псевдо-редизайн вместо продуктового UX

Риск: концепции будут отличаться только косметикой.  
Последствие: пользовательское поведение не проверяется, а выбор концепции бессмысленен.

### 2. Слишком ранний старт frontend

Риск: `frontend` начнёт собирать страницы до фиксации UX-логики.  
Последствие: лишняя перепись, конфликт с user requirement, слабая системность.

### 3. Перегрузка scope

Риск: в шаг 1 попытаются затянуть home/PDP/cart/account.  
Последствие: потеря темпа и размытая ответственность.

### 4. Ломка backend API ради каталога

Риск: catalog redesign начнёт тянуть за собой новые backend contracts без реальной необходимости.  
Последствие: нарушение migration discipline.

### 5. Stack upgrade в неправильный момент

Риск: обновление Node.js / Next.js сделать параллельно с неутверждённым UX.  
Последствие: трудно локализовать регрессии.

## 7. Как проверяем

На конце шага 1 должны быть:

1. [docs/CATALOG_REDESIGN_CONCEPTS.md](./CATALOG_REDESIGN_CONCEPTS.md) с 3 полными концепциями
2. `/catalog-a`, `/catalog-b`, `/catalog-c` в рабочем виде
3. переключатель между вариантами
4. один и тот же backend API contour под всеми тремя страницами
5. ручная проверка:
   - search
   - categories
   - filters
   - sorting
   - price/discount visibility
   - rating
   - stock state
   - add-to-cart
   - cart entry
   - mobile interaction
6. QA comparison matrix по 3 концепциям

Критерии успеха:

- быстрее находится товар
- меньше лишних кликов
- mobile path проще
- интерфейс не требует объяснения
- все отступы, grid и hierarchy системны

## 8. Что сознательно НЕ делаем в этом шаге

- не переделываем весь продукт сразу
- не трогаем checkout, seller, admin, bot
- не переносим бизнес-логику во frontend
- не переписываем backend contracts без необходимости
- не строим новый design system package отдельно от реального storefront
- не делаем “креативный” UI
- не делаем премиальную подачу вместо utilitarian commerce UX

## 9. Переход на актуальный стек

Технический подпакет должен идти вместе с frontend-реализацией, но после UX approval.

### Что фиксируем сейчас

Текущий storefront использует:

- `next ^15.2.4`
- `react ^19.0.0`

Для следующего шага целевой baseline:

- Node.js `24.x` LTS line
- Next.js `16.x` Active LTS line

Основание:

- Node.js official releases: `v24` помечен как `Active LTS`
- Next.js Support Policy: `16.x` помечен как `Active LTS`, `15.x` — уже `Maintenance LTS`

Источники:

- https://nodejs.org/en/about/releases/
- https://nextjs.org/support-policy

### Как обновлять безопасно

1. Зафиксировать UX.
2. На отдельном frontend пакете обновить:
   - `package.json`
   - lockfile
   - локальный runtime baseline
3. Прогнать:
   - `npm install`
   - `npm run typecheck`
   - `npm run build`
4. Проверить App Router routes `/catalog-a|b|c`.
5. Не менять backend API contracts во время stack upgrade.

### Что нельзя делать

- нельзя одновременно менять UX-модель, routing model и backend contracts
- нельзя смешивать stack upgrade с broad refactor всей кодовой базы

## 10. Короткий вывод

Шаг 1 должен идти так:

1. `uiux` фиксирует 3 каталожные концепции и единую дизайн-систему.
2. После approval `frontend` реализует `/catalog-a`, `/catalog-b`, `/catalog-c`.
3. Stack upgrade на Node.js `24.x` LTS и Next.js `16.x` Active LTS делается внутри этого frontend-пакета, но не раньше UX approval.
4. По итогу выбирается базовая модель для полного редизайна всего пользовательского продукта.
