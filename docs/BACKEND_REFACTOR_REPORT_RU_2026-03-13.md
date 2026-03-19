# Отчет по рефакторингу backend-структуры

## Что сделано

- Shopfront view-модули перенесены в `backend/shopfront/views/`
- Users HTML view-модули и общие helper-модули перенесены в `backend/users/views/`
- API слои вынесены в:
  - `backend/catalog/api/`
  - `backend/orders/api/`
  - `backend/commerce/api/`
  - `backend/users/api/`
- Core view-модуль перенесен в `backend/core/views/`
- `urls.py` обновлены на новую структуру
- Для старых import paths оставлены compatibility shims

## Новая структура

- `shopfront/views/`:
  - `catalog.py`
  - `checkout_cart.py`
  - `checkout_flow.py`
  - `checkout_payment.py`
  - `discovery.py`
  - `pages.py`
  - `product.py`
  - `helpers.py`
- `users/views/`:
  - `auth_html.py`
  - `account_html.py`
  - `seller_html.py`
  - `helpers.py`
- `catalog/api/views.py`
- `orders/api/views.py`
- `commerce/api/public.py`
- `commerce/api/admin.py`
- `users/api/views.py`
- `core/views/system.py`

## Совместимость

Старые flat paths не удалены резко. Для них оставлены thin compatibility modules, чтобы не ломать:

- старые импорты в коде
- тесты, которые monkeypatch-ят legacy module paths
- постепенный переход остального backend-кода на canonical imports

## Проверки

Выполнено:

- `python3 -m py_compile ...` по перенесенным модулям и маршрутам
- `docker compose --profile test run --rm backend-test /app/.venv/bin/pytest -o addopts='' tests/test_users_api.py tests/test_users_html_views.py tests/test_commerce_public.py tests/test_shopfront_views.py -q`

Результат:

- `121 passed`

## Итог

Backend приведен к более предсказуемой структуре:

- web/html views теперь сгруппированы в `views/`
- API теперь сгруппированы в `api/`
- старые import paths сохранены как совместимый слой, а не как основное место разработки
