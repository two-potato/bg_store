# Slug and URL Audit

## Короткий вывод

Текущая URL-схема в `Servio` уже частично опирается на slug как на публичный идентификатор, но выглядит не как единая продуктовая система, а как набор исторически сложившихся маршрутов.

Главная проблема сейчас не в том, что slug-ы не работают. Они работают.

Главная проблема в другом:

- URL taxonomy не унифицирована
- часть маршрутов выглядит product-friendly, часть нет
- категории, товары, продавцы и поиск не сведены к одной понятной схеме
- nested category URL сейчас отсутствует
- vendor surface раздвоена между `stores/` и `sellers/`

Если ориентироваться на желаемый формат:

- `/brands/`
- `/brands/costa-nova`
- `/categories/`
- `/categories/tableware`
- `/categories/tableware/plates`
- `/products/`
- `/products/costa-nova-pearl-dinner-plate`
- `/vendors/`
- `/vendors/roomers`
- `/search`

то текущую схему стоит считать переходной и требующей нормализации.

## Что есть сейчас

Текущие storefront-маршруты:

- `/brands/`
- `/brands/<brand_slug>/`
- `/catalog/categories/<category_slug>/`
- `/catalog/`
- `/search/live/`
- `/product/<slug>/`
- `/stores/<store_slug>/`
- `/sellers/<seller_slug>/`

Это видно в [backend/shopfront/urls.py](/home/twopotato/dev/servio/backend/shopfront/urls.py#L95).

### Что в этом хорошо

- `brands` уже выглядят нормально
- `product/<slug>` и vendor-поверхности уже slug-based
- есть legacy redirects по `id` и `username`

### Что в этом плохо

- `catalog/categories/...` не выглядит как first-class SEO/public route
- `product/` в единственном числе выбивается из общей ресурсной модели
- `stores/` и `sellers/` создают путаницу в vendor identity
- `/search/live/` есть, но нет явной канонической search-page URL в виде `/search`
- категории не поддерживают nested path вроде `/categories/tableware/plates`

## Желаемая каноническая схема

Я бы закрепил такую публичную схему как canonical:

- `/brands/`
- `/brands/<brand-slug>/`
- `/categories/`
- `/categories/<category-path>/`
- `/products/`
- `/products/<product-slug>/`
- `/vendors/`
- `/vendors/<vendor-slug>/`
- `/search`

Где:

- `category-path` это полный nested path, например `tableware/plates`
- `product-slug` это плоский уникальный slug товара
- `vendor-slug` это единый публичный slug продавца

## Оценка по каждому блоку

### 1. Brands

Текущее состояние:

- уже близко к целевому
- `brands/<slug>` выглядит правильно

Вывод:

- этот блок менять минимально
- можно оставить как есть

### 2. Categories

Текущее состояние:

- сейчас категория открывается как `/catalog/categories/<slug>/`
- slug у `Category` плоский и глобально уникальный

Проблема:

- URL не соответствует ожиданию пользователя
- нет иерархии в URL
- из адреса не видно родительскую категорию
- путь не совпадает с навигационной структурой каталога

Желаемое состояние:

- `/categories/tableware`
- `/categories/tableware/plates`

Мой вывод:

- для категорий нужен не просто `slug`, а `path slug`
- лучше хранить:
  - обычный `slug` сегмента
  - и вычисляемый `full_path` или `path_slug`

Пример:

- category: `tableware`
- child: `plates`
- canonical URL child: `/categories/tableware/plates`

Это лучше и для SEO, и для UX, и для дебага.

### 3. Products

Текущее состояние:

- сейчас `/product/<slug>/`

Проблема:

- единственное число выбивается из общей REST-like витринной схемы
- URL выглядит менее “каталожно” и менее консистентно, чем `/products/...`

Желаемое состояние:

- `/products/costa-nova-pearl-dinner-plate`

Вывод:

- товары нужно переводить на `/products/<slug>/`
- старый `/product/<slug>/` оставить как permanent redirect

### 4. Vendors

Текущее состояние:

- есть `/stores/<store_slug>/`
- есть `/sellers/<seller_slug>/`

Проблема:

- пользователь не должен разбираться, что у вас “seller profile” и “seller store” это разные сущности
- публичная vendor identity должна быть одна
- две сущности можно оставить в доменной модели, но не обязательно тащить это в public URL taxonomy

Желаемое состояние:

- `/vendors/`
- `/vendors/roomers`

Вывод:

- нужен единый canonical vendor route
- внутренне можно решать, что это:
  - `SellerStore`
  - `UserProfile`
  - агрегированная vendor page

Но наружу должен быть один понятный публичный ресурс: `vendor`

### 5. Search

Текущее состояние:

- поисковая выдача фактически живет в `/catalog/?q=...`
- live-search живет отдельно в `/search/live/`

Проблема:

- нет явной канонической search page
- поиск смешан с каталогом
- это мешает аналитике, SEO-сигналам, IA и читаемости продукта

Желаемое состояние:

- `/search?q=plates`
- `/search/live/` можно оставить как внутренний endpoint

Вывод:

- storefront search page лучше вынести в `/search`
- каталог оставить для browse/filter mode
- поиск и browse должны быть близки, но не обязаны быть одним и тем же URL

## Что не нравится в slug-слое прямо сейчас

### 1. Нет единого URL contract

Сейчас маршруты отражают историю разработки, а не продуманную информационную архитектуру.

### 2. Нет nested category slug model

Для категорий плоский `slug` уже маловат как публичная модель.

### 3. Нет единого vendor slug contract

Публичный продавец раздвоен между `store` и `seller`.

### 4. Нет явной canonical/redirect стратегии для всех типов сущностей

Частично редиректы есть, но общей slug history модели нет.

## Что я рекомендую сделать

## Этап 1. Зафиксировать canonical URL map

Прямо на уровне продукта и роутинга закрепить:

- `brands`
- `categories`
- `products`
- `vendors`
- `search`

И больше не добавлять новые public surface-пути вне этой схемы.

## Этап 2. Разделить browse и search

Сделать:

- `/categories/...` для навигации по дереву
- `/search?q=...` для поисковой выдачи

А `/catalog/` постепенно перевести в internal compatibility layer или redirect strategy, если это допустимо продуктово.

## Этап 3. Ввести nested category path

Для `Category` добавить отдельный canonical path:

- `slug`: сегмент, например `plates`
- `full_slug_path`: `tableware/plates`

И искать категорию не просто по `slug`, а по полному пути.

## Этап 4. Унифицировать vendors

Выбрать один публичный объект:

- либо `SellerStore`
- либо специальный `Vendor` projection

И вести весь public traffic туда:

- `/vendors/<slug>/`

Старые маршруты:

- `/stores/...`
- `/sellers/...`

оставить как 301 redirect.

## Этап 5. Ввести slug history

Для public entity типов:

- brand
- category
- product
- vendor

нужна история старых slug/path с 301 redirect на текущий canonical URL.

Это особенно важно, если импорт/refresh может регенерировать slug.

## Как бы я оценил целевую схему

Схема, на которую ты ориентируешь:

- `/brands/`
- `/brands/costa-nova`
- `/categories/tableware/plates`
- `/products/costa-nova-pearl-dinner-plate`
- `/vendors/roomers`
- `/search`

выглядит правильной.

Почему она хорошая:

- единообразная
- читаемая
- SEO-friendly
- соответствует mental model marketplace
- легко документируется
- хорошо масштабируется

## Финальная рекомендация

Я бы принял такие решения:

1. `brands` оставить почти как есть.
2. `categories` перевести с `/catalog/categories/<slug>/` на `/categories/<path>/`.
3. `product` перевести с `/product/<slug>/` на `/products/<slug>/`.
4. `stores` и `sellers` схлопнуть в единый public `vendors`.
5. Канонической страницей поиска сделать `/search`, а `/search/live/` оставить внутренним HTMX/live endpoint.

## Итоговая оценка

Текущая slug/URL система:

`5.5/10`

Целевая схема из твоего примера:

`8.5/10`

Разница как раз в том, что целевая схема ощущается как продуманная продуктовая навигация, а текущая все еще выглядит как эволюционный набор маршрутов.
