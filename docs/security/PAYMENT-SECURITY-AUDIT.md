# Payment security audit

Production at baseline: **Stripe unconfigured**, live flag false, no payment
orders. Both runtime and env-file checks report absent keys, without revealing
values. A functioning local sandbox is not evidence of enabled production
payments. Other environments, Stripe account/webhook subscriptions and dashboard
settings remain unverified. Do not activate live or production test purchases.

## Price and authority

Server-calculated EUR integer cents: TOP day package 100 cents/day, 10–365 days;
the monthly TOP UI submits 30 days (3000 cents), rather than a separate fixed
backend-only monthly tariff; homepage one calendar month at 6000 cents; advertising
30-day/one-month package 3000 cents. The browser submits terms/identifiers, not
authoritative amounts. All checkout target lookups require ownership and listing
eligibility. Fixed return paths use the existing HashRouter. Browser redirects
do not grant service. Hosted Stripe Checkout keeps PAN/CVV outside this server;
PCI scope and SAQ eligibility still need processor/acquirer confirmation.

Production test-key purchases previously could grant real entitlements without
real funds once configured. New `STRIPE_TEST_PAYMENTS_ENABLED=false` blocks new
Checkout by default in production. Explicit sandbox acceptance is required to
opt in; it is not isolation. Development tests remain usable. Existing signed
payment events, reconciliation and refunds continue to process so the gate
cannot strand previously accepted payments. Live checkout also checks the live
flag at creation, in addition to startup validation.

## Session, webhook and finances

Order UUID/reservation is committed before provider I/O. Retried creation uses
that UUID as Stripe idempotency key, with unknown attempts beyond 23 hours
requiring review. Provider I/O releases transaction locks, then fresh locked
state is loaded. Shared advertising capacity locking serializes reservations;
expired reservations require provider confirmation before reuse.

Webhook validates the raw-body SHA-256 HMAC and a five-minute timestamp window
before reading the signed event; signatures can rotate with multiple v1 values.
Malformed non-ASCII signatures now return 400. Checkout fulfillment binds order,
session, integer amount, EUR currency, configured test/live environment and
PaymentIntent. Completion without paid status cannot grant service. A paid
order is not downgraded by later failed/expired events. Duplicate fulfillment
does not extend service twice. Financial events use a unique event-ID inbox;
fresh provider charge/refund/dispute snapshots and locked updates handle
duplicates and delayed delivery. Checkout deduplication uses order/session
state rather than a separate Checkout event-ID ledger.

| Dimension | Implemented states / transitions |
|---|---|
| Order | creating → pending → paid / expired / failed; verified late payment may become paid, with capacity/eligibility review |
| Fulfillment | pending → fulfilled / review_required; refunded/dispute-lost → revoked; audited restore preserves recorded intervals |
| Financial | normal → refund_pending / partial_refund / refunded / disputed; provider failure → refund_failed; dispute outcome → normal or dispute_lost |
| Advertising | pending_payment → paid pending_review → active or rejected; unsettled paid inventory remains reserved |

Admin resolution requires current admin permission, a reason and audit identity.
A refund request is not completion; only succeeded provider receipts count.
Per-attempt idempotency and receipt recovery prevent blindly creating another
refund after uncertain commits. Partial refund is a manual-review state.
Deletion guards protect pending/unresolved payments and active entitlements;
historical TOP intervals remain individually attributable. Same-host compromise
or a database superuser can still alter these facts (SEC-001).

Reviewed: payment endpoints, Checkout transport, creation/reconciliation,
fulfillment, financial snapshots/inbox, deletion guards, models, migrations
0057–0063, advertising capacity/alerts, frontend payment paths and PR #332
documentation. Unit and real PostgreSQL tests cover synthetic signatures,
amount/environment mismatch, duplicates, expiry, payment failures, last-slot
races, refund/dispute and deletion/restoration scenarios. Browser tests use
mock provider/API responses; no real Stripe financial calls were made.

Residual cases: long-running distributed crash/fault injection, adversarial
interleavings beyond existing concurrency tests, actual Stripe API compatibility,
webhook delivery/retry configuration and live charge/refund/dispute behavior
remain unverified. Requesting owner-approved sandbox testing is the next gate;
successful synthetic tests alone do not establish live-payment readiness.
