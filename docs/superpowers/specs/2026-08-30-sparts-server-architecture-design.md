# Sparts Server Architecture Design

Date: 2026-08-30
Status: Proposed for review
Base repository: `two-potato/servio`, branch `dev`

## 1. Goal

Evolve Servio into the Sparts backend without a full rewrite. Sparts is a replacement-parts commerce system with verified digital inventory, compatibility data and make-to-order production. The architecture must optimize the business path:

`search -> product/part page -> compatibility -> cart -> payment -> production -> QC -> shipment`

The first production target is tens to hundreds of strong SKUs, while keeping an explicit path to many thousands of SKUs, multiple manufacturing methods, contractors and an eventual print farm.

The default production-start SLA is 6 hours after confirmed payment unless a SKU explicitly overrides it. This is a start-of-production SLA, not an order-completion SLA.

## 2. Decision summary

Sparts will use a **domain-oriented modular monolith** on Django, PostgreSQL as the only business source of truth, Redis for ephemeral infrastructure concerns, Celery for asynchronous work, a search engine as a rebuildable projection, and S3-compatible object storage for digital assets.

Core domain boundaries are implemented as explicit Django modules with service-level APIs. Cross-domain side effects that must survive process failure use a transactional outbox. Business transitions are explicit service calls; Django signals are not used to orchestrate the paid-order-to-production lifecycle.

Microservices, Kafka and Kubernetes are intentionally excluded from the MVP. Module boundaries must nevertheless be strong enough that Production or Discovery can be extracted later without rewriting consumers.

## 3. Findings from Servio

### 3.1 Infrastructure worth keeping

Servio already has the right baseline stack:

- Django 5.2, DRF and ASGI.
- PostgreSQL.
- Redis.
- Celery worker and Celery beat.
- Elasticsearch.
- Gunicorn/Uvicorn and Nginx.
- Sentry and Prometheus instrumentation.
- Docker Compose for development and deployment.
- A separate Telegram bot process.
- pytest, Ruff and mypy development tooling.

The existing deployment composition already separates web, worker, scheduler, bot, PostgreSQL, Redis, Elasticsearch and Nginx. This is a useful starting topology and should be evolved rather than replaced.

### 3.2 Application structure worth keeping

Servio already demonstrates several useful patterns:

- `shopfront` has dedicated cart and checkout services instead of putting all behavior into templates/views.
- `shopfront` has catalog selectors and live-search services.
- `orders` contains a service layer and Celery tasks.
- `catalog` has a dedicated Elasticsearch index module and offer service.
- tests exist for catalog, commerce, orders, shopfront, health/metrics and N+1 behavior.

These patterns should become the norm in Sparts: explicit write services, explicit read selectors/projections and focused task modules.

### 3.3 Domain structure that must change

The current `catalog.Product` is an ordinary commerce product aggregate. It combines SKU identity, manufacturer SKU, dimensions, material, price, stock quantity, lead time, generic attributes, seller and unrelated product properties. Extending it with CAD, licensing, compatibility and production fields would create a high-coupling god model.

The current order model also includes marketplace-oriented structures such as seller splitting, seller orders and marketplace shipments. These solve a different business problem than Sparts production routing. They should not become the backbone of Sparts manufacturing.

The current order signal automatically plans seller splits and schedules notifications whenever an order is saved or changes status. This pattern is acceptable for non-critical notifications, but it is not acceptable for the paid-order-to-production guarantee because the orchestration is implicit and direct `.delay()` scheduling does not provide durable atomicity with the order transaction.

## 4. Target bounded contexts

The MVP target is eight primary modules plus `core`. This is deliberately smaller than the long-term domain map.

### 4.1 `catalog`

Owns commercial identity and discoverability of a sellable replacement part.

Responsibilities:

- Sparts SKU and public naming.
- Brand/category relationships used by catalog navigation.
- OEM/reference numbers and aliases.
- Customer-facing description and structured product facts.
- SEO metadata and canonical public slugs.
- Sellability/publication state.

The existing `Product` is not immediately deleted. It becomes a migration source/compatibility surface while a new normalized Part model is introduced. New Sparts-only concepts must not be added to the legacy Product JSON field.

Core entities:

- `Part`
- `PartReference`
- `PartImage`
- `Category`
- brand/manufacturer presentation metadata

### 4.2 `compatibility`

Owns the compatibility graph as normalized relational data.

Core entities:

- `EquipmentBrand`
- `EquipmentFamily`
- `EquipmentModel`
- `EquipmentVariant`
- `EquipmentAssembly`
- `PartCompatibility`
- `CompatibilityEvidence`

`PartCompatibility` records a compatibility assertion against a specific sellable/revision context and has an explicit status:

- `CLAIMED`
- `INFERRED`
- `VERIFIED`
- `CUSTOMER_VERIFIED`
- `REJECTED`

Compatibility is never stored as an unstructured list in `JSONField`.

Evidence records may refer to installation testing, manufacturer documentation, customer-confirmed installation, measured dimensions or another explicit source. This supports future confidence scoring without changing the relationship model.

### 4.3 `digital_inventory`

Owns digital manufacturing assets, provenance and immutable revisions.

Core entities:

- `DigitalAssetSource`
- `DigitalAsset`
- `PartRevision`
- `RevisionAsset`
- `LicenseRecord`
- `VerificationRecord`

Rules:

- CAD/STEP is preferred as the master geometry source where available.
- STL/3MF are production derivatives, not authoritative history.
- Every production-capable revision records source, author/provider, license and commercial-use status.
- Files are immutable objects in S3-compatible storage and identified by SHA-256.
- A geometry change creates a new `PartRevision`; an already-sold revision is never silently overwritten.
- `OrderItem` snapshots the revision used to fulfill that order.

### 4.4 `commerce`

Owns cart/checkout pricing inputs, commercial offer and order capture. Existing reusable Servio checkout logic is retained where it does not depend on marketplace semantics.

Core responsibilities:

- cart calculation;
- price/offer resolution;
- discounts if retained as a product requirement;
- checkout validation;
- order creation and immutable commercial snapshots.

A sellable offer must separate customer price from manufacturing reality. Availability is modeled as a strategy, not merely an integer stock count.

Availability modes:

- `MAKE_TO_ORDER`
- `BATCH`
- `STOCKED`

The public product model does not change when a successful SKU moves between those modes.

### 4.5 `orders`

Owns customer order state and payment-level commercial facts, not machine/job workflow.

The target customer-order lifecycle is intentionally simpler than production lifecycle. Production status is derived from production jobs and surfaced to customers without forcing all manufacturing detail into `Order.status`.

Required order snapshots include:

- SKU/part identity;
- selected `PartRevision`;
- description/name at purchase time;
- quantity;
- unit price, tax and line total;
- manufacturing SLA applied to the line;
- customer delivery data required for fulfillment.

Marketplace seller-splitting entities are legacy candidates. They may remain during migration but must not be extended for manufacturing.

### 4.6 `production`

Owns physical manufacturing orchestration.

Core entities:

- `ManufacturingMethod`
- `Material`
- `ManufacturingSpec`
- `Producer`
- `Machine` or provider capability record
- `ProductionJob`
- `ProductionAttempt`
- `QCInspection`
- `ProductionCost`

Production workflow:

`PAID -> QUEUED -> ASSIGNED -> PRINTING -> POST_PROCESSING -> QC -> READY -> SHIPPED`

The persistence model should not assume that `PRINTING` is the only manufacturing method. The human-facing state may keep this wording initially, while underlying manufacturing method supports FDM, SLA, SLS/MJF, CNC, casting, batch production and external providers.

`ProductionJob` belongs to an order line or fulfillable quantity. `ProductionAttempt` records actual attempts so failure/reprint history is not destroyed.

A failed attempt does not duplicate the commercial order or create another customer charge.

### 4.7 `fulfillment`

Owns shipment preparation and transport-company integration after a line has passed QC or is otherwise fulfillable.

Core entities:

- `Fulfillment`
- `Shipment`
- `ShipmentItem`
- tracking/provider references

Shipping is carrier-driven. Sparts does not model its own courier operation for the MVP.

The existing marketplace `Shipment -> SellerOrder` relation should not be reused as the long-term Sparts relation; target shipment items point to fulfillable order/production outputs.

### 4.8 `integrations`

Owns adapters for external systems:

- acquiring/payment provider;
- transport company APIs;
- Telegram operator notifications;
- email;
- manufacturing contractor/provider APIs.

Domain modules depend on internal interfaces, not provider-specific HTTP calls.

Examples of internal ports:

- `PaymentGateway`
- `ShippingProvider`
- `ManufacturingProvider`
- `OperatorNotifier`

Provider webhook processing must persist provider event IDs and enforce idempotency.

### 4.9 `core`

Contains shared technical primitives only:

- timestamp base model;
- money/value helpers that truly cross domains;
- transactional outbox infrastructure;
- idempotency primitives;
- health/observability support.

`core` must not become a dumping ground for business logic.

## 5. Module interaction rules

1. Views/API handlers validate transport concerns and call services.
2. Services own write-side business transactions.
3. Selectors/query services own complex read-side ORM behavior.
4. Celery tasks are thin orchestration/adaptor boundaries around idempotent services.
5. Cross-domain writes are not performed from templates, serializers or signals.
6. A module may import another module's documented service/selector interface; it should not manipulate another module's models opportunistically.
7. Critical state changes use database constraints as the final invariant whenever practical.

Suggested per-module shape:

```text
module/
  models.py or models/
  services.py or services/
  selectors.py or selectors/
  tasks.py
  events.py
  admin.py
  api/
  tests/
```

Do not split a small module into folders merely for symmetry. Split when file size/responsibility justifies it.

## 6. Transaction and event architecture

### 6.1 Transactional outbox

Paid-order-to-production is a reliability boundary.

Within one PostgreSQL transaction:

1. lock/read the payment/order state;
2. idempotently mark payment/order paid;
3. create the durable outbox event `ProductionRequested` with an idempotency key;
4. commit.

An outbox dispatcher publishes/processes pending rows after commit. Processing may use Celery, but the durable intent is the PostgreSQL outbox row, not the broker message.

Minimum outbox fields:

- stable event ID (UUID);
- event type;
- aggregate type and ID;
- payload/version;
- idempotency key;
- created timestamp;
- published/processed timestamp;
- retry count;
- last error.

A unique constraint on the business idempotency key prevents duplicate production intent from duplicate payment webhooks.

### 6.2 Idempotent consumers

At-least-once delivery is assumed.

`ProductionRequested` handling must use a unique business key such as order-item/revision/fulfillment unit and create no more than one initial `ProductionJob`. Retried tasks may observe the existing job and return successfully.

External provider creation calls need their own outbound idempotency/reference key and reconciliation path.

### 6.3 Signals policy

Django signals may remain for non-critical decoupled concerns when failure does not invalidate a business transaction, but new critical flows must not depend on them.

The existing order `post_save` notification/seller-split signal should be gradually replaced by explicit order application services. Notifications may remain asynchronous listeners after durable business events exist.

## 7. Production SLA design

Every paid order line has an applied production-start deadline:

`production_due_at = paid_at + production_start_sla`

Default SLA: 6 hours.

The SKU/revision/manufacturing offer may override it.

Persist timestamps necessary to calculate compliance:

- `paid_at`
- `queued_at`
- `assigned_at`
- `production_started_at`
- `qc_completed_at`
- `ready_at`
- `shipped_at`

An SLA watcher runs periodically and finds paid/queued jobs whose `production_due_at` is approaching or breached. It creates an operator alert through the notification adapter. Repeated scheduler runs must not create alert storms; escalation records use unique severity/window keys.

Primary metric:

`production_start_latency = production_started_at - paid_at`

Required aggregates:

- P50/P95 production-start latency;
- percentage started within SLA;
- breached-job count;
- breach count by producer/manufacturing method/SKU.

## 8. Search and discovery

PostgreSQL is authoritative. Elasticsearch/OpenSearch remains a rebuildable read model.

A Sparts search document includes at least:

- Sparts SKU;
- title;
- OEM/reference numbers and aliases;
- equipment brand/model/variant;
- assembly/node;
- category;
- compatibility status/confidence facts;
- material and important dimensions;
- availability mode;
- lead/SLA facts appropriate for customers;
- current offer price;
- verification state.

Index updates are driven by durable events/outbox or a deterministic reindex command. No business fact exists only in the search engine.

The initial engine can remain Elasticsearch because Servio already has it. Engine replacement is not an MVP objective.

## 9. SEO and GEO rendering

The storefront remains server-rendered Django HTML first. Public part, OEM/reference, equipment and compatibility pages must be crawlable without client-side rendering.

Use semantic HTML and structured schema.org facts. Structured data should be produced from normalized domain facts, not separately maintained SEO strings wherever possible.

Programmatic landing pages are generated only when they have useful structured content and a clear entity/query purpose. Do not generate thin pages for every combinatorial relationship.

DRF remains available for Telegram, operator tools, integrations and future clients. The existence of an API does not require the storefront to become an SPA.

## 10. Digital asset storage

Move production assets away from local application filesystem semantics to S3-compatible object storage.

Object keys should be revision-oriented, for example:

```text
digital-assets/parts/<part-id>/revisions/<revision-id>/master/<sha256>.step
digital-assets/parts/<part-id>/revisions/<revision-id>/production/<sha256>.3mf
digital-assets/parts/<part-id>/revisions/<revision-id>/preview/<sha256>.webp
```

Database rows store object key, SHA-256, size, MIME/type, role, source/license references and creation metadata.

Application code never assumes that an object can be mutated in place.

## 11. Deployment topology

### MVP

Keep the current container-oriented topology:

- Nginx/reverse proxy;
- Django ASGI web process;
- Celery worker;
- Celery beat/outbox dispatcher;
- Telegram bot;
- PostgreSQL;
- Redis;
- Elasticsearch;
- S3-compatible object storage (external managed service or dedicated service).

Use separate Celery queues for workload isolation when needed:

- `critical`
- `payments`
- `production`
- `search`
- `notifications`
- `imports`

Redis may remain the Celery broker for MVP. RabbitMQ is an evolution option when production/event delivery volume or operational guarantees justify it. The application must not depend on Redis-specific business semantics.

### Scaling stage

Scale Django web and Celery workers independently. Introduce managed/separate PostgreSQL, Redis and search services before introducing Kubernetes.

Kubernetes is deferred until multiple independently scaled application pools/environments and operational staffing justify its cost.

## 12. Observability

Keep Sentry and Prometheus. Add OpenTelemetry-compatible trace/context instrumentation incrementally where cross-process debugging becomes valuable.

Technical metrics alone are insufficient. Required business metrics include:

- `payments_confirmed_total`
- `production_jobs_created_total`
- `payment_to_production_start_seconds`
- `production_sla_breaches_total`
- `production_attempt_failure_rate`
- `qc_failure_rate`
- `reprint_rate`
- `compatibility_return_rate`
- `search_zero_results_rate`
- search-to-product CTR
- product-to-cart conversion
- paid-order conversion
- margin by SKU

Every request/task log related to an order/production flow should carry stable correlation identifiers where available: order ID, order item ID, production job ID and external provider reference.

## 13. Servio -> Sparts migration map

| Servio component | Decision | Sparts direction |
| --- | --- | --- |
| Django/DRF/ASGI | Keep | Platform foundation |
| PostgreSQL | Keep | Sole business source of truth |
| Redis | Keep | Cache/session/locks/broker initially; no unique business data |
| Celery + beat | Keep | Explicit queues, idempotent tasks, SLA watcher, outbox dispatcher |
| Elasticsearch | Keep initially | Rebuildable discovery projection |
| Nginx/Docker | Keep | MVP deployment |
| Sentry/Prometheus | Keep | Extend with business metrics |
| Telegram bot service | Keep | UI/integration only; business writes through backend API/services |
| `shopfront` services/selectors | Reuse/adapt | Preserve SSR and service/query separation |
| `catalog.Product` | Transitional | Do not add Sparts domain complexity; migrate to Part/reference/revision model |
| `catalog.es_index` | Adapt | Index Sparts search projection, not raw Product |
| `orders.Order` | Adapt | Keep customer-order aggregate, simplify marketplace assumptions |
| `OrderSellerSplit` | Retire from Sparts core | Marketplace legacy, not production routing |
| `SellerOrder`/`SellerOrderItem` | Retire from Sparts core | Replace with `ProductionJob`/fulfillment concepts |
| marketplace Shipment relation | Replace | Fulfillment attached to manufactured/fulfillable order items |
| `orders.services` pattern | Keep/improve | Explicit application services with transactions |
| `orders.signals` orchestration | Reduce | Replace critical flows with explicit services + outbox |
| fake acquiring provider | Keep only for tests/dev | Add real payment adapter and idempotent webhook processing |
| local media for production CAD | Replace | S3-compatible immutable object storage |
| generic Product `attributes` | Limit | Presentation-only flexible attributes; compatibility/revision/rights stay relational |

## 14. Migration sequence

The migration must keep Servio runnable after every phase.

### Phase 0 — architecture guardrails

- Add this design/ADR foundation.
- Add module dependency conventions and testing expectations.
- Establish the transactional-outbox primitive and idempotency test patterns before critical production integration.

### Phase 1 — digital catalog foundation

- Introduce `Part`, `PartReference` and compatibility equipment entities without deleting `Product`.
- Introduce `PartRevision` and digital asset provenance/license entities.
- Build migration/admin tooling to link selected existing Products to Parts.
- Render the first Sparts part pages from the new normalized facts while preserving existing Servio pages during transition.

Exit criterion: a real SKU can express OEM references, equipment compatibility, commercial-use rights and an immutable manufacturing revision.

### Phase 2 — Sparts checkout snapshot

- Adapt cart/checkout so an order item snapshots Part + selected PartRevision + applied production SLA.
- Keep existing Servio order APIs working where possible.
- Remove dependency on `stock_qty > 0` as the universal sellability rule; use availability mode.

Exit criterion: a customer can pay for a make-to-order digital SKU without pretending physical stock exists.

### Phase 3 — production workflow

- Add manufacturing spec/provider/job/attempt/QC/cost entities.
- Implement explicit `confirm_payment` application service with transactional outbox.
- Consume `ProductionRequested` idempotently.
- Implement production state transitions and timestamps.
- Add 6-hour SLA watcher and operator escalation.

Exit criterion: confirmed payment reliably creates exactly one production intent/job and SLA compliance is measurable.

### Phase 4 — fulfillment integration

- Add carrier adapter and Sparts fulfillment shipment model.
- Trigger fulfillment eligibility from passed QC/ready outputs.
- Preserve tracking and customer-visible shipment state.

Exit criterion: a production-complete order can be handed to a transport company without marketplace seller-order structures.

### Phase 5 — search/SEO projection

- Replace Product-centric search document with Part/reference/compatibility projection.
- Add deterministic full reindex.
- Add useful OEM/equipment/part landing routes and schema.org output.

Exit criterion: OEM code and equipment-model queries resolve normalized Sparts inventory and pages remain SSR/crawlable.

### Phase 6 — retire legacy marketplace coupling

- Stop creating seller splits/seller orders for Sparts orders.
- Remove dead marketplace-specific pathways only after data migration and behavior parity tests pass.
- Split large modules/files only where the Sparts code now changes them frequently.

## 15. Testing strategy

All migration phases use TDD for business invariants.

Required layers:

1. Model/constraint tests for uniqueness, revision immutability and compatibility relationships.
2. Service tests for explicit transactions and state transitions.
3. Idempotency tests that call payment webhook/outbox consumer/task multiple times.
4. Failure-window tests for payment commit vs worker dispatch.
5. Production SLA tests using frozen/controlled time.
6. Search projection tests plus full-reindex recovery test.
7. SSR route tests checking canonical/structured facts.
8. Existing Servio regression suite remains green throughout migration.
9. N+1/query-count tests are added for compatibility-heavy catalog pages because the relationship graph can create accidental query explosions.

Critical invariant examples:

- duplicate payment callback does not create a second payment or production job;
- a paid order cannot reference a mutable/unknown production revision;
- a rejected/non-commercial digital asset cannot become production-ready;
- one failed production attempt can be followed by another without losing cost/failure history;
- QC failure cannot mark the item ready;
- deleting/rebuilding search does not destroy business data;
- SLA breach calculation is based on persisted timestamps, not Celery task runtime.

## 16. Data and safety constraints

- Safety-critical parts require an explicit risk/engineering review status before ordinary publication.
- Sparts parts are identified as compatible parts, not OEM originals.
- Trademark/logo use is not inferred from compatibility data.
- Digital asset availability is not equivalent to commercial-use rights.
- Better-than-OEM geometry requires its own revision and verification record.
- Compatibility corrections must be auditable because compatibility errors are a primary return-risk metric.

## 17. Evolution boundaries

The first likely extraction candidate is `production` when Sparts operates multiple internal/external manufacturing providers with independent scaling/availability requirements.

The second likely extraction candidate is Discovery/Search when text, OEM, OCR/photo search, semantic retrieval and compatibility inference become a separately scaled workload.

Extraction is not scheduled by date or SKU count. It happens only when operational/team/runtime isolation benefits exceed distributed-system cost.

To preserve this option now:

- cross-domain writes go through services/events;
- provider integrations are adapters;
- search is a projection;
- production does not mutate catalog internals directly;
- business IDs are stable and suitable for external references.

## 18. Rejected alternatives

### Full rewrite

Rejected because Servio already contains useful commerce, checkout, SSR, Celery, search, bot, tests and deployment infrastructure. A rewrite would delay the first validated Sparts sales loop without creating proportional business value.

### Microservices from day one

Rejected because the MVP does not have team or scaling boundaries that justify distributed transactions, API versioning, service discovery and additional deployment surfaces.

### Compatibility in JSON

Rejected because compatibility is a core commercial asset requiring querying, verification, SEO landing relationships and error auditing.

### Graph database for compatibility

Rejected for MVP. PostgreSQL relations and indexes are sufficient for the initial graph and keep transactions, operations and joins in one authoritative store. A graph-specific read model may be introduced later if measured query workloads require it.

### SPA-first storefront

Rejected because server-rendered pages are simpler, cheaper and better aligned with Sparts SEO/GEO requirements. JavaScript islands/HTMX-style interactions can enhance the UI without moving domain rendering to a separate frontend application.

### Kubernetes for MVP

Rejected because Docker/container deployment with independently scalable processes is enough for the initial operational profile. Kubernetes would add operational cost before it creates leverage.

## 19. Architectural invariants

The following are hard rules for subsequent implementation plans:

1. PostgreSQL is the authoritative business store.
2. Compatibility is normalized relational data, not a Product JSON list.
3. Every manufactured sold line references an immutable PartRevision.
4. Digital asset source, license and commercial-use status are known before production-ready state.
5. Payment confirmation and production intent are atomically durable through a transactional outbox.
6. Background consumers and provider callbacks are idempotent.
7. The default production-start SLA is 6 hours unless explicitly overridden.
8. Search is a rebuildable projection.
9. Critical business orchestration is explicit service/event logic, not Django signals.
10. Storefront remains SSR-first.
11. Production domain is manufacturing-method agnostic.
12. External integrations are adapters behind internal interfaces.
13. Migration is incremental; Servio stays runnable after each phase.
14. No new marketplace abstraction is added unless it directly serves Sparts replacement-part commerce or production.
15. Architecture decisions are judged primarily by findability, compatibility accuracy, conversion, digital SKU quality, production SLA, margin, quality/returns and scale.

## 20. Review decision

If this design is approved, the next artifact is not a single giant implementation plan. The migration is large enough to require phase-specific implementation plans. The first implementation plan should cover **Phase 0 + Phase 1: architecture guardrails and digital catalog foundation** only. It must preserve existing Servio behavior and introduce the first end-to-end normalized Sparts SKU without prematurely implementing production orchestration.