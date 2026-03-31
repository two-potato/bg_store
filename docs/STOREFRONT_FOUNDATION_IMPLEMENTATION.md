# Storefront Foundation Implementation

## Цель

Поднять безопасный foundation-слой для поэтапного выноса storefront в `Next.js App Router` без изменения backend-доменов, `admin` и `bot`.

## Что внедрено

- Добавлен отдельный `frontend/` c `Next.js App Router`, `TypeScript` и production `standalone` build.
- Подняты первые public routes:
  - `/`
  - `/about/`
  - `/buyers/`
  - `/suppliers/`
  - `/delivery/`
  - `/payment/`
  - `/returns/`
  - `/contacts/`
  - `/faq/`
  - `/brands/`
  - `/collections/`
  - `/promotions/`
  - `/blog/`
- Добавлен health endpoint: `/api/health`.
- В `nginx` внедрён same-origin route switch:
  - backend остаётся default renderer
  - `Next.js` получает только allowlist public routes
  - `_next/*` и `__frontend/health` проксируются в новый frontend-контур
- В `docker-compose` добавлен сервис `frontend`.
- В CI добавлены `frontend` typecheck и build.

## Как включать

Переключатель:

- `STOREFRONT_NEXT_PUBLIC_ENABLED=0` — весь трафик остаётся на Django
- `STOREFRONT_NEXT_PUBLIC_ENABLED=1` — allowlist public routes начинает обслуживать `Next.js`

Upstream variables:

- `BACKEND_UPSTREAM`
- `FRONTEND_UPSTREAM`

## Rollback

Rollback делается без миграции данных:

1. вернуть `STOREFRONT_NEXT_PUBLIC_ENABLED=0`
2. перезапустить `nginx`

После этого весь storefront снова рендерится Django-контуром.

## Проверка

- `npm run typecheck` в `frontend/`
- `npm run build` в `frontend/`
- `docker compose -f docker-compose.yml -f docker-compose.dev.yml config`
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`
- `docker compose -f docker-compose.yml -f docker-compose.dev.yml build frontend nginx`

## Следующая волна

Следующий шаг после foundation:

1. перевести `home + static/marketing` на реальный backend-fed data contract
2. подготовить `catalog/search` storefront API
3. заложить browser auth/session bridge до переноса `cart/account`
