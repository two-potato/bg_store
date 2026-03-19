# Marketplace 2026 Execution Plan

## Purpose
This document is the execution source of truth for upgrading the current Django marketplace to a modern 2026-ready marketplace without rewriting the system from scratch.

The implementation principles are:
- preserve working business logic unless there is a clear production risk
- prefer incremental migrations over sweeping rewrites
- ship value in vertical slices, not isolated abstractions
- keep UX, backend, API, analytics, operations, and architecture aligned
- every wave must end in a deployable state

## Current Baseline
The project already has a strong foundation:
- Django marketplace structure with `catalog`, `orders`, `users`, `shopfront`, `commerce`
- category and brand catalog
- Elasticsearch-based search
- session cart and checkout
- seller/store foundation
- favorites, reviews, saved searches, recently viewed
- Celery, Redis, cache, Elasticsearch
- Sentry, PostHog, Clarity runtime integration
- seller grouping in cart
- idempotent order submission foundation

The main gaps that still block a 2026-grade marketplace are:
- no guest checkout
- no real promotions/coupons engine
- no full product variant and seller-offer domain
- no split order / split shipment model
- no delivery rate and ETA engine
- no production-grade payment provider integration and refunds
- no company/B2B account model
- no hybrid or semantic search
- limited seller operations tooling
- incomplete operational analytics and product-event taxonomy

## Working Rules
These rules govern all implementation work:

1. Do not break existing purchase flow while introducing new layers.
2. Prefer feature flags or additive paths when changing money flows.
3. Keep admin operable after each migration.
4. Add migrations in small batches with clear forward-only evolution.
5. Add tests alongside every critical commerce, cart, payment, and search change.
6. Validate every wave in dev before moving to the next wave.
7. If a later wave depends on an earlier data model, finish the data model first.
8. If a task introduces analytics, define events and properties before UI work is considered done.

## Delivery Format Per Task
Every task executed from this plan must follow the same structure:
- scope
- files to change
- migration impact
- API impact
- UX impact
- analytics impact
- test plan
- rollback risk

## Wave Structure

### Wave 1: Conversion, UX, Revenue Safety
Goal: remove the biggest conversion leaks and harden money-critical flows.
Status: completed.

#### 1. ~~Guest Checkout~~ `[done]`
Scope:
- allow order placement without forced account creation
- use guest identity based on email and phone
- keep optional account linking after order creation

Primary files:
- `backend/orders/models.py`
- `backend/orders/services.py`
- `backend/shopfront/views.py`
- `backend/templates/shopfront/checkout.html`
- `backend/templates/shopfront/partials/checkout_form_panel.html`
- `backend/static/shopfront/page.checkout.js`

Work items:
- add guest customer fields or normalize customer identity on `Order`
- update checkout validation for anonymous users
- keep idempotent order submission intact
- add post-purchase account invitation flow
- ensure order detail can be linked later to a real user

Acceptance criteria:
- anonymous user can complete checkout
- duplicate submit does not create duplicate orders
- existing authenticated checkout still works
- analytics include guest vs authenticated distinction

#### 2. ~~Checkout Diagnostics and Error Analytics~~ `[done]`
Scope:
- instrument full checkout funnel and failure reasons

Primary files:
- `backend/static/shopfront/analytics.js`
- `backend/static/shopfront/page.checkout.js`
- `backend/shopfront/views.py`

Events to add:
- `checkout_step_view`
- `checkout_error`
- `delivery_option_selected`
- `payment_started`
- `payment_failed`
- `coupon_applied`

Acceptance criteria:
- each checkout step is visible in PostHog
- validation failures are visible by field group and step
- payment start/fail states are measurable

#### 3. ~~Promotions and Coupon Engine~~ `[done]`
Scope:
- add first production-ready discount system

Primary files:
- new app or domain module under `backend/commerce` or `backend/promotions`
- `backend/orders/services.py`
- admin configuration
- checkout/cart templates

Models:
- `Coupon`
- `PromotionRule`
- `PromotionRedemption`

Capabilities:
- fixed and percent discount
- minimum subtotal
- active date windows
- seller/category/product scoping
- usage limit and per-user limit

Acceptance criteria:
- coupon apply/remove works from cart and checkout
- order stores discount source and final totals correctly
- invalid coupon reasons are visible in UI

#### 4. ~~Catalog Filters and Facets~~ `[done]`
Scope:
- turn catalog filtering into a strong marketplace discovery tool

Primary files:
- `backend/shopfront/search_service.py`
- `backend/shopfront/views.py`
- `backend/templates/shopfront/catalog.html`
- `backend/templates/shopfront/components/catalog_filters.html`
- `backend/catalog/models.py`

Capabilities:
- facet counts
- availability filter
- price range
- seller filter
- brand filter improvements
- delivery ETA filter
- filter persistence in querystring

Acceptance criteria:
- user can combine filters without losing state
- result counts are accurate
- search and category pages share the same filtering model

#### 5. ~~Product Detail Page Commercial Layer~~ `[done]`
Scope:
- strengthen decision-making on product pages

Primary files:
- `backend/catalog/models.py`
- `backend/templates/shopfront/product_detail.html`
- product admin

Capabilities:
- MOQ
- pack size
- VAT display
- lead time
- delivery promise
- availability states
- product documents and certificates
- richer trust block

Acceptance criteria:
- PDP communicates stock, lead time, seller trust, and commercial terms clearly
- documents and certifications are attachable from admin

#### 6. ~~Search Suggestions, Typos, and Recovery~~ `[done]`
Scope:
- improve search quality before semantic search

Primary files:
- `backend/shopfront/search_service.py`
- `backend/shopfront/views.py`
- `backend/shopfront/search.py`
- frontend live search templates

Capabilities:
- autocomplete
- typo tolerance
- synonym dictionary
- better zero-results recovery
- search click tracking

Acceptance criteria:
- top common misspellings still return useful results
- zero-results screens always show fallback actions
- search result click-through becomes measurable

## Wave 2: Growth, AOV, Retention
Goal: improve discovery, repeat purchase, and commercial merchandising.
Status: completed.

### 1. ~~Brand and Collection Experience~~ `[done]`
Scope:
- build SEO-capable landing structure for brands and curated collections

Primary files:
- `backend/catalog/models.py`
- `backend/shopfront/views.py`
- `backend/templates/shopfront/brand_detail.html`
- new collection templates

Models:
- `Collection`
- `CollectionItem`

Capabilities:
- brand hero and description
- collection landing pages
- curated merchandising blocks
- campaign-ready pages

Acceptance criteria:
- brands and collections are crawlable, filterable, and merchandisable

### 2. ~~Recommendations~~ `[done]`
Scope:
- add recommendation system foundations without ML overreach

Primary files:
- new selector/service module in `shopfront`
- home, PDP, cart, and checkout templates

Capabilities:
- recently viewed persistent storage
- similar products
- frequently bought together
- seller-aware cross-sell
- personalized homepage blocks for signed-in users

Acceptance criteria:
- recommendation blocks are visible in key surfaces
- analytics track impression and click-through

### 3. ~~Wishlist and Saved Lists~~ `[done]`
Scope:
- evolve favorites into repeat-purchase tooling

Primary files:
- `backend/shopfront/models.py`
- account templates
- cart integration

Models:
- `SavedList`
- `SavedListItem`

Capabilities:
- multiple named lists
- move list to cart
- list sharing
- reorder-oriented saved lists

Acceptance criteria:
- user can manage multiple product lists
- list-to-cart works without cart corruption

### 4. ~~Reviews, Q&A, and Trust Signals~~ `[done]`
Scope:
- add trust and user-generated content depth

Primary files:
- review models/templates/admin/API

Capabilities:
- verified purchase marker
- review photos
- helpful/unhelpful voting
- product Q&A
- seller rating summary

Acceptance criteria:
- reviews affect trust and are measurable
- moderation remains manageable through admin

## Wave 3: Marketplace Systemization
Goal: make the platform operationally ready for multi-seller complexity.
Status: completed.

### 1. ~~Seller Offer and Inventory Domain~~ `[done]`
Scope:
- separate product identity from seller-specific commercial offer

Primary files:
- `backend/catalog/models.py`
- cart and order services
- search indexing

Models:
- `SellerOffer`
- `SellerInventory`

Capabilities:
- seller-specific price
- seller-specific stock
- warehouse source
- lead time per seller
- offer status

Acceptance criteria:
- one product can have multiple seller offers
- cart and search can reason about offer-specific stock and pricing

### 2. ~~Split Order Model~~ `[done]`
Scope:
- allow one checkout to produce multiple seller fulfillment units

Primary files:
- `backend/orders/models.py`
- `backend/orders/services.py`
- account/admin templates and serializers

Models:
- `SellerOrder`
- `SellerOrderItem`

Capabilities:
- split by seller
- seller-specific statuses
- seller-level totals and comments
- split-safe analytics

Acceptance criteria:
- buyer sees one order
- operations can manage per-seller fulfillment
- split metadata is preserved for future payout/refund workflows

### 3. ~~Shipment Model and Delivery Operations~~ `[done]`
Scope:
- add fulfillment visibility and shipment structure

Primary files:
- orders/logistics modules
- order detail templates
- admin

Models:
- `Shipment`
- `ShipmentItem`

Capabilities:
- tracking number
- delivery method
- split shipment support
- fulfillment timestamps
- warehouse-to-order linkage

Acceptance criteria:
- each seller order can create one or more shipments
- buyer can see shipment progress clearly

### 4. ~~Admin Operations Layer~~ `[done]`
Scope:
- make admin usable for real marketplace operations

Primary files:
- `backend/orders/admin.py`
- seller/admin tools
- notifications

Capabilities:
- order queues
- SLA monitoring
- seller moderation
- stock alerting
- bulk import/export
- product document moderation

Acceptance criteria:
- operations team can manage high-volume workflows without raw DB access

### 5. ~~SEO and Content System~~ `[done]`
Scope:
- improve long-tail acquisition and structured discoverability

Primary files:
- category, brand, collection, landing templates
- sitemap and metadata layers

Capabilities:
- dynamic metadata
- schema improvements
- landing page templates
- content slots per taxonomy page

Acceptance criteria:
- taxonomy pages become SEO-addressable content surfaces

## Wave 4: Future-Ready Marketplace
Goal: create the architectural base for next-stage scale and intelligence.

### 1. ~~Hybrid and Semantic Search~~ `[done]`
Scope:
- move from lexical-only to hybrid retrieval

Primary files:
- `backend/shopfront/search_service.py`
- indexing jobs
- search configuration

Capabilities:
- query rewrite
- vector-ready index path
- hybrid retrieval
- reranking layer

Acceptance criteria:
- existing search remains stable
- semantic layer is additive and switchable

### 2. ~~B2B Company Accounts and Approval Workflows~~ `[done]`
Scope:
- support procurement teams and account hierarchy

Primary files:
- users, orders, account, pricing services

Models:
- `Company`
- `CompanyMembership`
- `ApprovalPolicy`

Capabilities:
- organization ownership
- staff roles
- approval chain
- company address book
- buyer-specific price agreements

Acceptance criteria:
- one company can have multiple buyers and approval roles
- B2B buyers can place and approve orders according to policy

### 3. Production Payment Layer
Scope:
- replace fake-acquiring-only path with true provider architecture

Primary files:
- `backend/orders/payment_providers.py`
- order services
- webhook endpoints

Capabilities:
- multiple providers
- webhook signature verification
- refunds
- payment reconciliation
- split payment readiness

Acceptance criteria:
- provider can be swapped without checkout rewrite
- payment state machine is reliable and observable

### 4. Loyalty, Personalization, and Pricing Intelligence
Scope:
- add margin-aware growth systems

Primary files:
- promotions, analytics, recommendation services

Capabilities:
- loyalty layer
- customer segmentation
- personalized offers
- margin-aware merchandising

Acceptance criteria:
- merchandising logic becomes data-driven, not purely manual

### 5. AI-Assisted Content and Catalog Enrichment
Scope:
- prepare content automation without surrendering moderation control

Primary files:
- catalog ingest and moderation tools
- admin support modules

Capabilities:
- title/spec enrichment assistance
- duplicate detection
- content normalization
- moderation queues

Acceptance criteria:
- AI enriches operations, not bypasses governance

## Cross-Cutting Workstreams

### Security
Must be handled continuously, not as a final pass.

Tasks:
- add CSP
- add rate limiting for auth, checkout, search, API
- harden file uploads
- review seller/admin permissions
- formalize fraud-related checkout guards
- keep analytics payload free of explicit PII

### Performance
Must advance alongside Waves 1 through 4.

Tasks:
- remove N+1 queries in catalog/cart/order paths
- introduce cache policy for catalog facets and search
- improve image handling for responsive delivery
- add background jobs for heavy indexing and enrichment
- define scaling assumptions for 10k+ concurrent users

### Observability
Must be measurable before major flows are called complete.

Tasks:
- extend PostHog event taxonomy
- send server-side purchase/order events where needed
- improve Sentry tagging and error grouping
- add Grafana-ready operational metrics
- track seller SLA and search quality

### Architecture
Must keep the codebase from collapsing under new domain complexity.

Tasks:
- extract services from `shopfront/views.py`
- define selectors/query modules for catalog, cart, checkout, seller data
- formalize payment and search provider boundaries
- keep templates componentized
- maintain additive migrations and backward-compatible service boundaries

## Execution Order
The order below is the canonical implementation sequence.

1. ~~Guest checkout~~
2. ~~Checkout analytics and error instrumentation~~
3. ~~Promotions and coupons~~
4. Catalog facets and filter model
5. PDP commercial fields and product documents
6. Search autocomplete, typos, synonyms, and click tracking
7. Brand pages and collection pages
8. Recommendation blocks and analytics
9. Saved lists and reorder flows
10. Reviews, Q&A, and trust upgrades
11. SellerOffer and SellerInventory domain
12. Split order model
13. Shipment model
14. Admin operations tooling
15. SEO and content landing system
16. Hybrid and semantic search foundation
17. ~~B2B company and approval workflows~~
18. Production payment providers and refunds
19. Loyalty and pricing intelligence
20. AI-assisted catalog enrichment

## Definition of Done
A task from this plan is not complete until all of the following are true:
- code is implemented
- migrations are applied and safe
- existing business logic still works
- relevant templates and APIs are aligned
- analytics for the feature are in place
- tests cover critical paths
- dev deployment is healthy
- known risks are documented

## Progress Tracking
Implementation progress should be tracked directly in this file by marking items with:
- `[todo]`
- `[in_progress]`
- `[done]`
- `[blocked]`

If priorities change, update this file instead of maintaining a separate private checklist.

## Commitment
Future implementation work should follow this document in order unless a production incident or explicit user reprioritization overrides it.
