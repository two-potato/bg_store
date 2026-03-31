# QA / Metrics Report — Next Buyer Wave

Дата: 2026-03-27
Контур: `cart / account / orders / buyer tools`
Объём проверки: `cart`, `account shell`, `orders list/detail/reorder`, `settings`, `preferences`, `addresses`, `legal`, `notifications`, `favorites`, `lists`, `saved-searches`, `analytics ingest`

## 1. Что проверено

- Инфраструктурный smoke:
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml ps --status running`
  - `backend`, `frontend`, `nginx` и зависимые сервисы подняты.
- Frontend quality smoke:
  - `cd frontend && npm run typecheck` — passed.
  - `cd frontend && npm run build` — passed.
- Backend contract smoke:
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -T backend python -m pytest tests/test_storefront_bridge_api.py -q --no-cov` — `17 passed`.
- Внешний unauth runtime через `nginx`:
  - `GET http://127.0.0.1:8080/cart` — `200`, buyer cart route реально идёт в Next.
  - `GET http://127.0.0.1:8080/account` — `200`, buyer account blocker реально идёт в Next.
  - HTML buyer blockers больше не содержат `http://localhost:8000/...`.
  - CTA из `/account`, `/account/favorites`, `/account/orders` ведут на same-origin `/legacy/account/login/?next=...` и реально открывают login page c `200`.
- Auth runtime через внешний путь:
  - `GET http://127.0.0.1:8080/account/login/?next=%2Faccount` — same-origin backend login page, без ухода на `localhost`.
  - direct auth flow под `smoke-user / smoke-pass-2026` проходит.
- Automated buyer smoke в репо:
  - добавлен [buyer_wave_smoke.mjs](/home/twopotato/dev/servio/scripts/buyer_wave_smoke.mjs) и команда `npm run smoke:buyer` в [package.json](/home/twopotato/dev/servio/package.json).
  - сценарий проверяет:
    - unauth `/cart`
    - unauth `/account`
    - unauth CTA reachability
    - auth `login -> account`
    - создание заказа через `smoke-user`
    - `/account/orders`
    - `/account/orders/{id}`
    - `reorder -> /cart`
  - фактический прогон на текущем runtime:
    - `Buyer smoke: unauth /cart passed`
    - `Buyer smoke: unauth /account passed`
    - `Buyer smoke: unauth CTA target reachable (/legacy/account/login/?next=%2Faccount)`
    - `Buyer smoke: auth /account passed`
    - `Buyer smoke: cart add passed`
    - `Buyer smoke: checkout created order ...`
    - `Buyer smoke: orders list passed`
    - `Buyer smoke: order detail + reorder passed`
    - `Buyer smoke: cart after reorder passed`
    - `Buyer wave smoke passed for http://127.0.0.1:8080`

## 2. Что не покрыто

- Buyer smoke пока не подключён как обязательный CI шаг.
- Не прогнаны browser mutations для:
  - `settings/preferences save`
  - `addresses create/default/delete`
  - `favorites/lists/saved-searches` create/delete/move flows
- Нет mobile browser pass, keyboard-only pass и screen-reader pass.
- Нет visual regression и Storybook quality pass по buyer wave.
- Не прогнаны негативные browser flows:
  - `401` после истечения session
  - `429` на analytics ingest
  - `5xx` на bridge endpoints

## 3. Главные риски

- Основной runtime blocker `024` снят:
  - unauth buyer CTA больше не ведут на `localhost`;
  - `/legacy/account/login/?next=...` теперь reachable и same-origin.
- Остаточный process risk:
  - buyer smoke уже существует и зелёный локально на реальном `Next + nginx` контуре,
  - но текущий CI workflow всё ещё поднимает только backend `runserver` на `127.0.0.1:8000` для browser smoke и не стартует полный `frontend + nginx` стек.
  - Поэтому `npm run smoke:buyer` ещё не закреплён как обязательный CI gate не из-за runtime blocker, а из-за текущей формы CI job.
- Completeness risk:
  - `claims/support/cancel/tracking` остаются частично в legacy detail и не закрывают full parity buyer wave.

## 4. Какие тесты / события / алерты добавить

### Тесты

- Следующий шаг по quality gates:
  - подключить `npm run smoke:buyer` в CI job, который поднимает реальный `frontend + backend + nginx`, а не backend-only `runserver`.
- Добавить browser flows:
  - `settings` save
  - `preferences` save
  - `addresses` create/default/delete
  - `favorites` toggle
  - `lists` create/delete/move-to-cart
  - `saved-searches` create/delete

### События

- Проверять фактическую отправку в `/api/storefront/analytics/ingest/` для:
  - `cart_viewed`
  - `cart_checkout_clicked`
  - `account_dashboard_viewed`
  - `orders_list_viewed`
  - `order_detail_viewed`
  - `order_reorder_clicked`
  - `favorite_toggled`
  - `saved_list_created`
  - `saved_list_moved_to_cart`
  - `saved_search_saved`
  - `address_created`

### Алерты

- `5xx` rate по `/api/storefront/*`
- `401` spike по `/api/storefront/account/*` и `/api/storefront/orders/*`
- `429` spike по `/api/storefront/analytics/ingest/`
- рост `reorder.result_type = none|partial`
- browser console errors на buyer routes

## 5. Блокеры релиза

- Runtime blockers по `024` не воспроизвелись.
- Оставшийся незакрытый технический шаг не про runtime, а про enforcement:
  - buyer smoke ещё не включён в CI на полном `Next + nginx` контуре.

## QA verdict

`Release-ready по минимальному buyer critical path runtime smoke`.

Что подтверждено:

- unauth buyer CTA больше не уводят на `localhost` и не падают в `404`;
- `npm run smoke:buyer` зелёный на реальном внешнем runtime;
- auth critical path `login -> account -> orders detail -> reorder -> cart` автоматизирован и проходит до конца.

Что остаётся сделать после релизного минимума:

- поднять этот smoke как обязательный CI gate на полном storefront-стеке;
- расширить покрытие buyer wave за пределы минимального critical path.

## Backlog 024 status

`Closed`.

Основание:

- localhost fallback убран и перепроверен;
- same-origin unauth CTA reachable;
- minimal automated buyer smoke в репо существует и проходит.
