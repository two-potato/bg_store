# Servio — Claude Code Project Memory

## Язык
- Всё общение, планы, отчёты, объяснения, комментарии к задачам и UI/UX-решения — только на русском языке.
- Английский допустим только для кода, API, имён файлов, библиотек и терминов, где это необходимо.

## Продуктовый контекст
- Проект: Servio
- Тип: marketplace
- Фронтенд: Next.js
- Стек менять нельзя без явного указания.
- API-контракты ломать нельзя.

## Текущая цель
- Переделка UI/UX фронтенда без смены технологического стека.
- Нужен современный marketplace UX/UI.
- Нужна сильная дизайн-система.
- Нужна высокая визуальная консистентность.
- Нужны best practices Next.js UI/UX.

## Архитектурные правила Next.js
- Использовать App Router.
- По умолчанию предпочитать Server Components.
- Client Components использовать только там, где реально нужны интерактивность, состояние, эффекты или browser APIs.
- Не раздувать client bundle без причины.
- Использовать next/image для изображений, где это оправдано.
- Использовать next/font для шрифтов.
- Учитывать SEO, layout stability и responsive behavior.

## UI/UX вектор
- Основа: Amazon structure + Farfetch cleanliness + Wayfair filtering + Faire clarity.
- Search-first UX.
- Чистая иерархия.
- Много воздуха.
- Сильный каталог.
- Сильная карточка товара.
- Рациональная PDP без текстовой свалки.
- Trust UX: отзывы, доставка, наличие, условия, прозрачность.
- Современные loading / empty / error states.
- Mobile-first логика.
- Clean commerce.
- Controlled density: интерфейс не пустой, но и не перегруженный.
- Progressive disclosure: сложность раскрывается по мере необходимости.

## Что запрещено
- Общаться не на русском.
- Менять стек без задачи.
- Ломать API-контракты.
- Делать дешёвый Temu-style UI.
- Делать перегруженный old-Amazon-style интерфейс.
- Плодить несистемные компоненты.
- Делать визуальный шум.
- Тащить новые библиотеки без сильного обоснования.
- Превращать всё в Client Components без причины.
- Игнорировать mobile UX.
- Жертвовать UX ради визуального эффекта.

## Референсы
- Amazon — https://www.amazon.com/
- Etsy — https://www.etsy.com/
- Airbnb — https://www.airbnb.com/
- Farfetch — https://www.farfetch.com/
- Wayfair — https://www.wayfair.com/
- TikTok Shop — https://seller.tiktok.com/
- Whatnot — https://www.whatnot.com/
- StockX — https://stockx.com/
- Faire — https://www.faire.com/

## Палитра Servio
- Primary 500: #2F6BFF
- Primary 600: #1F5AE6
- Primary 100: #E8F0FF
- Text 900: #1F2A44
- Text 700: #4A556D
- Text 500: #7E889B
- Page BG: #F5F7FB
- Card BG: #FFFFFF
- Subtle BG: #EEF2F7
- Border 200: #D9E0EA
- Border 300: #C8D0DC
- Neutral 200: #E7EBF2
- Neutral 300: #D5DCE7
- Neutral 500: #A9B4C5
- Success: #22A06B
- Warning: #F5A524
- Danger: #E5484D

## Радиусы
- XS: 8px
- SM: 10px
- MD: 12px
- LG: 16px
- XL: 20px
- Pill: 999px

## Приоритет страниц
### Priority 1
- Главная
- Каталог
- Поиск
- Карточка товара
- Корзина

### Priority 2
- Checkout
- Избранное
- Личный кабинет покупателя
- Страницы категорий
- Страницы брендов / продавцов

### Priority 3
- Seller pages
- Service pages
- Empty / error / loading states
- Modals / overlays / utilities
