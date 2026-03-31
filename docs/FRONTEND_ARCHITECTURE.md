# Frontend Architecture

## Stack

- Django templates
- HTMX for server-driven interactions
- Vanilla JS modules under `backend/static/shopfront/`
- Tailwind/DaisyUI plus legacy CSS layers

## Frontend Runtime Model

- Pages are rendered server-side first
- HTMX swaps partials for cart, checkout, account and discovery flows
- Analytics and monitoring scripts hydrate after page render
- Most business decisions stay on the server

## File Layout

- Templates: `backend/templates/**`
- Static JS/CSS: `backend/static/shopfront/**`
- Storefront view adapters: `backend/shopfront/views/**`

## Frontend Rules

- Prefer server-rendered HTML over client-side state duplication
- Keep JS focused on hydration, analytics, lightweight progressive enhancement
- When adding a POST from JS, include CSRF and use same-origin credentials
- Keep HTMX partials deterministic and idempotent
