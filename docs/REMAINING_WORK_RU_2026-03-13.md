# Статус remediation после полного прохода

Список из этого файла закрыт. Критических и обязательных пунктов из remediation-backlog больше не осталось.

## Что выполнено

- устранен `deploy/compose` drift
- исправлен local DX для `manage.py` и добавлен `make check-local`
- добавлены frontend build-check, browser smoke, visual regression и deploy/compose drift-check в CI
- устранен migration drift в `shopfront`
- сужены broad exceptions в search/logging/bot hot paths
- сужен fallback в fake-payment FSM
- product-card cart/favorite state вынесен из global context processors в request-scoped template tags
- checkout декомпозирован дальше:
  - submit orchestration вынесен в `checkout_submit_service.py`
  - page/submit flow вынесен в `checkout_flow_views.py`
  - cart views вынесены в `checkout_cart_views.py`
  - payment/guest-order views вынесены в `checkout_payment_views.py`
  - `checkout_views.py` стал compatibility/export module
- visual coverage расширен:
  - `home`
  - `catalog`
  - `product`
  - `cart`
  - `cart-filled`
  - `checkout`
  - `home-mobile`
  - `catalog-mobile`
  - `cart-mobile`
- frontend shell облегчен:
  - page-specific scripts подключаются через `page_type`
  - часть page-specific CSS вынесена из always-on shell в page-scoped loading
- security signaling усилен:
  - placeholder secrets в DEBUG явно warning’ятся
  - bot health показывает статус internal-token auth
- documentation ownership оформлен
- `README.md` приведен к роли entrypoint и ссылается на актуальные source-of-truth docs

## Что осталось только как optional follow-up

Это уже не обязательный remediation backlog, а обычные улучшения, если команда захочет идти дальше:

- расширять visual regression еще глубже на auth-bound и HTMX-specific mutation states
- дальше сокращать legacy CSS footprint и always-on shared assets
- поддерживать `README.md` и ownership docs в актуальном состоянии при следующих архитектурных изменениях

## Коротко

Обязательный remediation-план выполнен. Дальше остаются не блокеры, а нормальная эволюционная оптимизация frontend shell, visual coverage и документации.
