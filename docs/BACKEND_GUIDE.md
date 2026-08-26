# Backend Guide

## Layering

Use this order of responsibility when adding backend code:

1. Models for persistence and constraints
2. Selectors/query helpers for read-heavy ORM assembly
3. Services for orchestration and business rules
4. Views/API serializers as transport adapters
5. Tasks for async or scheduled work

## Placement Rules

- New seller/account HTML logic: `backend/users/views/`
- New storefront UI logic: `backend/shopfront/views/`
- New search logic: `backend/shopfront/searching/`
- New recommendation logic: `backend/shopfront/recommendation/`
- New public search/recommendation contract API: `backend/shopfront/api/`
- Shared order business rules: `backend/orders/services.py` or dedicated order service modules

## View Rules

- Parse request, call service, render response
- Avoid large multi-branch ORM orchestration directly inside views
- Keep redirects, HTMX partials, and JSON responses in the transport layer

## Service Rules

- Prefer typed inputs and outputs
- Keep public service functions small and testable
- Do not hide DB-heavy loops inside view helpers

## Performance Rules

- Default to `select_related` / `prefetch_related` on user-facing pages
- Add query-budget tests for list/detail pages
- Prefer cached selectors for expensive read-mostly filters and menus

## Security Rules

- No `csrf_exempt` on browser-driven endpoints without compensating control
- Validate uploads server-side
- Use internal token checks only for service-to-service endpoints
- Fail fast in production when secrets are placeholders

## Testing Rules

- Unit test services
- Integration test HTML views and API endpoints
- Add query count assertions for catalog/order/account pages
- Keep browser smoke for critical storefront flows
