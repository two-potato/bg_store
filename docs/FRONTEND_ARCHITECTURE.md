# Frontend Architecture

## Purpose

This document is the current source of truth for the Servio storefront frontend runtime.

Use it instead of older audit notes when you need to understand:

- how assets are loaded
- where to place CSS and JS changes
- how HTMX and server-rendered UI fit together

## Runtime Model

Servio storefront is a server-rendered frontend built on:

- Django templates
- HTMX
- Vanilla JS
- Tailwind CSS and DaisyUI

The frontend is not SPA-driven. The server remains authoritative for routing, rendered HTML, and business state.

## Main Entry Point

Primary shell:

- `backend/templates/shopfront/base.html`

This template defines:

- global SEO and metadata slots
- analytics and monitoring bootstrapping
- HTMX defaults on `<body>`
- CSS and JS asset order
- shared layout includes such as navbar, footer, mobile nav, toasts, and indicators

Treat asset order in `base.html` as a runtime contract.

## CSS Structure

Current runtime CSS is layered as:

1. built Tailwind bundle:
   - `backend/static/css/app.css`
2. vendor styles:
   - animate.css
   - hover.css
3. legacy split styles:
   - `backend/static/shopfront/css/legacy/*.css`
4. canonical plain CSS layers:
   - `tokens.css`
   - `base.css`
   - `layout.css`
5. component styles:
   - `backend/static/shopfront/css/components/*.css`

Guideline:

- prefer `tokens/base/layout/components` for new work
- touch `legacy/*.css` only for containment or migration work
- do not reintroduce monolithic stylesheet patterns

## JS Structure

Shared UI scripts:

- `backend/static/shopfront/ui.*.js`

Page scripts:

- `backend/static/shopfront/page.checkout.js`
- `backend/static/shopfront/page.product.js`
- `backend/static/shopfront/page.addresses.js`
- `backend/static/shopfront/page.legal.js`

Other runtime scripts:

- analytics
- error monitoring
- auth and consent helpers
- Telegram WebApp helpers

Guideline:

- place reusable behavior in `ui.*.js`
- place page-specific lifecycle code in `page.*.js`
- make all DOM initialization safe after HTMX swaps
- keep page scripts page-scoped in `base.html` instead of loading them globally
- keep page-specific CSS page-scoped in `base.html` where the asset is not part of the shared shell contract

## HTMX Contract

Global HTMX defaults are applied in `base.html` on `<body>`:

- `hx-boost="true"`
- `hx-target="main"`
- `hx-select="main"`
- `hx-swap="outerHTML"`
- `hx-indicator="#htmx-indicator"`

Implication:

- links and forms inherit boosted behavior unless explicitly disabled
- fragment endpoints must be compatible with main-content replacement
- page JS must survive partial rerenders

## Key Template Surfaces

Shared storefront components:

- `backend/templates/shopfront/components/navbar.html`
- `backend/templates/shopfront/components/mobile_nav.html`
- `backend/templates/shopfront/components/product_card.html`
- `backend/templates/shopfront/components/cart_control.html`

These are high-impact shared surfaces and should be changed conservatively.

## Build Workflow

Frontend build command:

```bash
npm run tw:build
```

Watch mode:

```bash
npm run tw:watch
```

When editing Tailwind-driven styles or `assets/tw.css`, rebuild the bundle.

## Current Constraints

- legacy and new CSS layers still coexist
- global shell is lighter than before, but still carries legacy CSS and shared UI JS that can be reduced further over time
- visual regression now covers home, catalog, product, cart, filled-cart, checkout, home-mobile, catalog-mobile, and cart-mobile states
- mutation coverage is currently anchored on deterministic cart-state transitions rather than auth-bound interactive states

## Document Status

This file is the current frontend architecture guide.

Related files:

- `docs/frontend_audit_2026-03-07.md`: historical audit and debt notes
- `docs/FULL_AUDIT_2026-03-12.md`: cross-functional audit and remediation tracking
