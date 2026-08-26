# API Reference

## Endpoints

- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/docs/`
- Redoc: `/api/redoc/`
- Search contract API: `/api/search/*`
- Recommendations contract API: `/api/recommendations/*`

FastAPI service docs (platform services):

- Search service OpenAPI: `http://localhost:18110/openapi.json`
- Search service Swagger: `http://localhost:18110/docs`
- Recommendation service OpenAPI: `http://localhost:18111/openapi.json`
- Recommendation service Swagger: `http://localhost:18111/docs`

Local dev URLs:

- `http://localhost:8080/api/schema/`
- `http://localhost:8080/api/docs/`
- `http://localhost:8080/api/redoc/`

## Authentication

Most API methods require Bearer JWT authentication.

Header:

```http
Authorization: Bearer <access_token>
```

Telegram WebApp login:

- `POST /api/users/auth/tg-webapp/`
- Accepts `initData`
- Returns `{ "access": "<jwt>" }`

Internal order moderation endpoints use extra headers:

```http
X-Internal-Token: <internal service token>
X-Admin-Telegram-Id: <telegram admin id>
```

## Common Responses

- `200 OK` Successful read/update action.
- `201 Created` Resource created successfully.
- `204 No Content` Resource deleted successfully.
- `400 Bad Request` Validation error, malformed request, or missing required query/body fields.
- `401 Unauthorized` Missing or invalid authentication.
- `403 Forbidden` Authenticated user has no access to the target legal entity or internal action.
- `404 Not Found` Requested resource does not exist or is not visible to the caller.

Typical error body:

```json
{ "detail": "Authentication credentials were not provided." }
```

Validation-style error body:

```json
{
  "items": ["This field is required."],
  "non_field_errors": ["Некоторые товары не найдены."]
}
```

## Users

- `GET /api/users/me/`
  Returns current user profile summary.

- `POST /api/users/auth/tg-webapp/`
  Exchanges Telegram WebApp `initData` for JWT access token.

## Commerce

- `POST /api/commerce/check-inn/`
  Checks whether a legal entity with the given INN already exists locally.

- `POST /api/commerce/membership-requests/`
  Creates a membership request for an existing legal entity.

- `GET /api/commerce/delivery-addresses/`
- `POST /api/commerce/delivery-addresses/`
- `GET /api/commerce/delivery-addresses/{id}/`
- `PUT /api/commerce/delivery-addresses/{id}/`
- `PATCH /api/commerce/delivery-addresses/{id}/`
- `DELETE /api/commerce/delivery-addresses/{id}/`
  CRUD for delivery addresses available to the current user.

- `GET /api/commerce/lookup/party/?inn=...`
  Company lookup via DaData.

- `GET /api/commerce/lookup/bank/?bik=...`
  Bank lookup via DaData.

- `GET /api/commerce/lookup/revgeo/?lat=...&lon=...`
  Reverse geocode helper for address autofill.

## Commerce Admin

- `POST /api/commerce/admin/membership-requests/{id}/approve/`
- `POST /api/commerce/admin/membership-requests/{id}/reject/`
- `POST /api/commerce/admin/entity-creation-requests/{id}/approve/`
- `POST /api/commerce/admin/entity-creation-requests/{id}/reject/`

These methods are staff-only and intended for backoffice moderation.

## Catalog

- `GET /api/catalog/brands/`
- `GET /api/catalog/brands/{id}/`
- `GET /api/catalog/series/`
- `GET /api/catalog/series/{id}/`
- `GET /api/catalog/categories/`
- `GET /api/catalog/categories/{id}/`
- `GET /api/catalog/products/`
- `GET /api/catalog/products/{id}/`

Product filters:

- `brand`
- `series`
- `category`
- `is_new`
- `is_promo`

Example:

```http
GET /api/catalog/products/?category=12&is_promo=true
```

## Search (Contract Layer)

- `GET /api/search/query/?q=...&limit=...&country_limit=...`
  Unified storefront search contract with:
  - ranked product cards
  - suggestions and corrections
  - basic facets (`brands`, `categories`, `availability`, `price`)
  - provider metadata (`provider`, `effective_query`, `rewritten_query`, `rewrite_kind`)
  - source metadata (`django-inline`, `fastapi`, `django-inline-fallback`)

- `GET /api/search/suggestions/?q=...&limit=...&country_limit=...`
  Suggestions/corrections contract for live search UI.

Service mode (env):

- `SEARCH_SERVICE_MODE=django-inline|fastapi`
- `SEARCH_SERVICE_URL=http://search-api:8010`
- `SEARCH_SERVICE_TIMEOUT_SECONDS=0.8`

Important:

- `django-inline` is default and keeps existing domain search logic in Django.
- `fastapi` mode calls external `search-api` and falls back to Django on transport/payload errors.

## Recommendations (Contract Layer)

- `GET /api/recommendations/home/?limit=...`
- `GET /api/recommendations/products/{product_id}/?limit=...`
- `GET /api/recommendations/products/{product_id}/sections/{section}/`
- `POST /api/recommendations/cart/`
- `POST /api/recommendations/checkout/`
- `GET /api/recommendations/reorder/?limit=...` (auth required)
- `GET /api/recommendations/search-recovery/?q=...&limit=...`

All endpoints return a unified sections envelope:

- `recommendation_id`
- `surface`
- `variant`
- `latency_ms`
- `fallback_source`
- `empty_reason`
- `sections[]` with `key/title/products/source/strategy/tracking_payload/impression_id/fallback_source/empty_reason`
- `source` (`django-inline`, `fastapi`, `django-inline-fallback`)
- optional markers:
  - `service_source` (например, `search-api` / `recommendation-api`)
  - `engine_source` (фактический backend engine source, обычно `django-inline`)

Stage 1 contract freeze:

- `recommendation_id` — идентификатор конкретного recommendation decision/envelope
- `impression_id` — идентификатор секции/экспозиции для event linkage
- `engine_source` — кто фактически собрал payload (`django-inline` и т.п.)
- `service_source` — какой service обслужил запрос (`recommendation-api` и т.п.)
- `fallback_source` — причина/тип fallback, если он был применён
- `empty_reason` — почему payload/section пустые
- `latency_ms` — server-side latency формирования контракта

Service mode (env):

- `RECOMMENDATION_SERVICE_MODE=django-inline|fastapi`
- `RECOMMENDATION_SERVICE_URL=http://recommendation-api:8011`
- `RECOMMENDATION_SERVICE_TIMEOUT_SECONDS=0.8`

Important:

- Default mode keeps recommendation orchestration in Django (`shopfront/recommendation/service.py`).
- FastAPI mode is additive and falls back to Django if remote service is unavailable.

## Internal Service Contracts (Service-to-Service)

These endpoints are service-only and require `X-Internal-Token`:

- `GET /api/internal/search/query/`
- `GET /api/internal/search/suggestions/`
- `GET /api/internal/recommendations/home/`
- `GET /api/internal/recommendations/products/{product_id}/`
- `GET /api/internal/recommendations/products/{product_id}/sections/{section}/`
- `POST /api/internal/recommendations/cart/`
- `POST /api/internal/recommendations/checkout/`
- `GET /api/internal/recommendations/reorder/`
- `GET /api/internal/recommendations/search-recovery/`

Notes:

- Internal endpoints force `django-inline` mode to avoid recursion when public API runs in `fastapi` mode.
- Internal endpoints are excluded from public OpenAPI (`/api/schema/`).

## Orders

- `GET /api/orders/`
  Lists company orders visible to the current user.

- `GET /api/orders/{id}/`
  Returns order details including items, seller splits and seller orders.

- `POST /api/orders/`
  Creates a new order.

Order enums:

- `status`: `new`, `confirmed`, `paid`, `delivering`, `delivered`, `canceled`, `changed`
- `split_status`: `single`, `planned`, `ready`, `split`
- `approval_status`: `not_required`, `pending`, `approved`, `rejected`
- `source_channel`: `web`, `twa`, `api`

Example request:

```json
{
  "legal_entity_id": 7,
  "delivery_address_id": 14,
  "customer_comment": "Нужна утренняя доставка",
  "coupon_code": "WELCOME10",
  "items": [
    { "product_id": 101, "qty": 2 },
    { "product_id": 205, "qty": 1 }
  ]
}
```

Internal moderation:

- `POST /api/orders/{id}/approve/`
- `POST /api/orders/{id}/reject/`

Required headers:

```http
X-Internal-Token: <internal service token>
X-Admin-Telegram-Id: <telegram admin telegram id>
```

Possible responses:

- `200` `{ "ok": true }`
- `403` invalid internal token or no admin rights for the order's legal entity
- `404` order not found

## Notes

- Schema and UI docs are generated from DRF + drf-spectacular annotations in code.
- If you add a new API endpoint, document it with `extend_schema` or `extend_schema_view`.
- For public-facing changes, re-check `/api/schema/`, `/api/docs/` and `/api/redoc/`.
- Search/recommendations contract endpoints are source of truth for Next storefront migration.
