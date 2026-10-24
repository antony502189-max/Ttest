# Homepage advertising

The homepage shows a seven-position advertising grid (restored from the
historical layout in commit `66fca55f16ce`). Paid, published banners appear
in their normal API order and the remaining places display a neutral
megaphone placeholder labeled “Espacio publicitario” in the selected
language. On mobile, all seven positions form a vertical stack, matching
the previously approved reference instead of the later horizontal carousel.
On larger screens the places form a two-column grid.

The original call to action remains below the advertising slots, with the
heading “Tu anuncio podría estar aquí”, description, and full-width lime
“Publicar publicidad” button on mobile. When capacity is exhausted,
the existing availability/waitlist functionality replaces the purchase
call to action. Placeholders do not count as paid inventory; slot capacity
is still enforced by the backend and provider-confirmed reservations.

The homepage advertising header displays **€30.00 / month** (localized for
Spanish, Russian and English) next to the megaphone label, using the public
`GET /advertisements/availability` quote rather than a hardcoded frontend
price. This endpoint reads the same `PACKAGE_PRICE_CENTS` as Stripe Checkout,
and reports `monthlyPriceCents=3000`, `months=1`, `currency=EUR`.
If the public quote fails, the header omits the price instead of making one up.

The grid preserves its fonts, pale placeholder cards, sponsored links and
lime purchase button. **New homepage-bottom advertising banners cost €30 for
exactly one calendar month**, starting on administrator approval; users cannot
choose a shorter or longer duration. The backend still stores a 30-day order
compatibility field, but the actual purchased calendar month ends on the
corresponding day of the next month (clamped when needed). This is a
one-time purchase, not a recurring subscription.

The historical package identifier `homepage_1d` is retained to preserve
existing data and API compatibility; it does **not** offer one-day purchases.
Legacy `test_homepage_30d` entitlements retain their original paid terms.

## Administrator publication and rejection

Apply migration `0066_complimentary_ads` before deploying this behavior.
The moderation screen offers **Publicar banner sin coste**, opening the banner
editor in administrator mode. `POST /admin/advertisements` requires the normal
server-side administrator allowlist and full account access. It publishes a
banner immediately for one calendar month with API `paymentStatus=waived`, without
creating a payment order or Stripe session. Complimentary banners consume the
same seven-slot capacity and use the same image validation as paid banners.
Storage retains the legacy paid entitlement status plus nullable `payment_waived`
to preserve rollback compatibility without inventing payment orders or charges.
Ordinary advertisement creation still requires payment; client fields and URL
parameters cannot grant the exemption. Editing a live complimentary campaign
retains its expiry and sends it through moderation.

**Rechazar y eliminar** permanently deletes a pending-review banner row in the
same transaction that creates its owner's `advertisement_deleted` notification.
The notification includes the banner title and moderation note and is displayed
in Spanish, Russian or English. Unreferenced images are marked for the existing
storage deletion worker. The banner disappears from both campaign lists and
releases its slot. Confirmed payment records remain available for refunds in
the administrator payment review queue; rejection does not initiate a refund.
Repeated rejection or access to the removed banner returns 404.

Validation for this change: 17 advertising unit tests, 14 advertising API tests,
13 browser tests, TypeScript checking and the production build passed. API tests
used an isolated PostgreSQL database with the real advertising, payment and
authentication tables; unrelated geography columns were inert because PostGIS
was unavailable locally. The additive `0066` waiver-column migration was also applied and
verified separately on that database.

In **Mis anuncios**, the TOP action on each eligible owned listing offers two
independent paid products. The buyer selects a fixed period and sees the
price before explicitly confirming Stripe Checkout:

| Purchased period | Listing TOP | Single homepage featured listing |
| --- | ---: | ---: |
| **12 hours** | **€0.99** | **€4.95** |
| **24 hours** | **€1.70** | **€8.50** |
| **72 hours (3 days)** | **€4.50** | **€22.50** |

The homepage featured listing is the **single large main photo / booking
hero slot**, not one of the seven commercial advertising banners. Its tariff
is exactly five times the corresponding TOP tier. These are **one-time
purchases**, not subscriptions. No other time selections are accepted by the
new checkout API; the server computes the Stripe amount using a fixed
integer-cent tariff table and persists `duration_hours` on new orders.

TOP brings the selected property ahead of ordinary listings in search and
map results for exactly the purchased number of UTC hours. An additional
TOP purchase extends the existing unexpired TOP end time by the purchased
hours, without truncating the old paid period.

The single featured-listing slot becomes active only on verified payment,
shows the selected listing photo and direct link, and expires exactly
12, 24 or 72 hours from confirmed payment. Concurrent purchases and manual
administrator replacement of a paid slot remain blocked. Buy again only
after capacity becomes free.

**Historical protection:** `payment_orders.duration_hours` is nullable;
NULL denotes an existing order under the old days/calendar-month tariff.
Previous purchased durations, prices and fulfillment remain intact.
Migration `0064_hourly_promotion_orders` is additive and does not rewrite
earlier paid orders. The seven commercial advertising banners retain their
independent **€30 per calendar month** price and approval workflow.

Apply migration `0060_homepage_purchases` before deploying the new backend.
It adds the homepage order kind and nullable banner duration while preserving
old purchased campaign durations. Homepage payments use the same signed webhook,
verified Stripe GET recovery and background reconciliation as banner payments.

Advertisers upload JPEG, PNG or WebP and enter a title, description and website,
phone, WhatsApp or email destination. The existing image validation, ownership,
media delivery, moderation and campaign management paths remain in use.

## Payments and seven-slot capacity

`GET /payments/advertisements/{id}/quote` returns one month, €30 and current
capacity without reserving a place. The explicit payment click calls Stripe
Checkout; the browser sends `{ "days": 30 }` for legacy API compatibility.
Other values of `days` are rejected by the API (HTTP 422), and the price
is always calculated by the backend. Existing open sessions must be cancelled
before creating another order. A shared PostgreSQL transaction advisory lock
serializes checkout, moderation, editing, cancellation and webhook state
changes. Homepage featured-listing endpoints are
`/payments/homepage/quote` and `/payments/listings/{id}/homepage/checkout`,
`/status`, and `/checkout/cancel`.

Active unexpired campaigns, paid review submissions, and pending Stripe orders
reserve capacity. Pending orders count once per campaign. New purchases are
rejected with HTTP 409 before a provider session is created when all seven places
are occupied. Existing open sessions can be reused for their reserved campaign.

Banner Checkout accepts immediate card payments using the current
`allowed_payment_method_types` filter and expires after about 31 minutes.
Expiry webhooks release reservations; the outbox worker also checks old pending
orders against Stripe. A local timer never frees a potentially paid reservation.
Completed sessions are recovered through authenticated Stripe GET by the worker
and the owner's `/payments/advertisements/{id}/status` endpoint when a webhook is
lost. `/payments/advertisements/{id}/checkout/cancel` expires an open session before
releasing capacity. If payment wins the cancellation race, it is fulfilled and
capacity remains reserved. Subscribe Stripe to
`checkout.session.completed`, `checkout.session.async_payment_succeeded` and
`checkout.session.expired`. [Stripe Checkout parameters](https://docs.stripe.com/api/checkout/sessions/create).

Only signed paid webhooks or verified Stripe GET responses move campaigns into review. Editing a paid active
creative preserves its original end time, so repeated edits cannot restart the
paid period. Rejected and deactivated campaigns release space. Refunds retain the
existing manual Stripe process.

## Vacancy notifications

`GET /advertisements/availability` reports free capacity and the public VAPID key.
Authenticated users subscribe through `POST /advertisements/waitlist` and cancel
through `DELETE /advertisements/waitlist`. One waiting subscription per account is
stored durably. The worker checks for a vacancy after expiry, rejection or
cancellation and records one in-site notification per subscription. Notification
links open the advertising form. A notification does not reserve a place.

If enabled and permitted by the user, browser push is sent through the registered
`advertising-sw.js` service worker. Transient provider failures retry after five
minutes; invalid subscriptions (404/410) fall back to the in-site notification.
The endpoint only accepts known browser push providers, validates key sizes and
checks the browser's actual P-256 public point. Saved subscription state survives
page reload and can be cancelled. A changed subscription invalidates an old worker
claim so it cannot mark the new subscription as delivered.
Without browser permission, browser support, or server VAPID configuration, the
UI explicitly confirms the in-site notification channel.
[Browser subscription requirements](https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe).

## Deployment

1. Install backend dependencies using `backend/constraints.txt` and apply
   `alembic upgrade head`, including `0058_advertising_waitlist` and
   `0059_payment_fulfillment`.
2. Generate a key pair once in a private, ignored environment file:
   `python -m app.commands.web_push_keys --output webpush.local.env`.
3. Put `WEB_PUSH_PUBLIC_KEY`, `WEB_PUSH_PRIVATE_KEY` and `WEB_PUSH_SUBJECT` in the
   API and worker environment. Production Compose forwards all three settings.
   Never place the private key in frontend settings or source control. On Windows,
   keep the generated file in a directory whose ACL is restricted to the operator.
4. Serve the frontend over HTTPS, including `advertising-sw.js`, and run the
   existing outbox worker. Keep a stable VAPID pair across redeployments.
5. Keep existing Stripe keys/webhook configured; this change never switches Stripe
   between test and live modes.

If more than seven old campaigns/reservations already exist, new purchases stay
closed until capacity drops below seven. The public display is capped at seven;
resolve any pre-existing oversold paid campaigns operationally before release.

## Exceptional paid orders

`payment_orders.fulfillment_status` records `fulfilled` independently of `paid`.
A paid order that cannot be safely assigned is retained as `review_required`, with
the reason recorded and a notification to the buyer. Its campaign blocks another
purchase; the checkout and My campaigns show the payment issue. The administrator
advertising page shows the reconciliation queue from
`GET /payments/admin/review-required`. Refunds continue to be handled in Stripe;
do not collect another payment while the earlier one is unresolved.

The stored creative fingerprint prevents late events from approving different
content. A late paid expired order cannot displace seven currently reserved places.
Migration preserves historical paid TOP fulfillment to prevent duplicate grants;
historical paid advertising orders without a paid campaign are queued for review.

## Premium commercial advertising package (2026-10-24)

The homepage now has **one additional premium commercial banner position** above
the seven ordinary banner slots. Its visual card uses the site lime palette
with a single €60 price and a dark-green CTA; there is no benefits/pictogram row.
The seven ordinary positions remain independently available, each with its own
€30/month label, and existing paid creatives and their destinations are not
reordered or re-priced.

The customer journey is **placement preview → choose Premium €60 or Standard €30
→ create an advertisement → confirm preview → quote → explicitly start Stripe
Checkout → verified payment → pending moderation → approved display**.
Selecting a plan in the URL does not create a payment or reserve inventory.

New ad package `homepage_premium_1m` (stored as `placement=homepage_premium`)
is priced at **€60 per calendar month**, with a capacity of **one**. Existing
package `homepage_1d` remains **€30 per calendar month** with **seven**
ordinary places. Both prices and capacity are server-owned. The public
`GET /advertisements/availability` endpoint now includes `premiumAvailable`
and `premiumMonthlyPriceCents`, while preserving existing fields. Public
`GET /advertisements/premium` returns at most one eligible live premium
campaign. Existing `GET /advertisements/homepage` remains the seven ordinary
positions only.

Stripe orders still use `kind=advertisement`, duration_months=1 and the
existing signed webhook, cancellation, reconciliation, financial audit and
moderation flow. `/payments/advertisements/{id}/quote` and checkout calculate
the amount from the **saved immutable package**, not any client-supplied price.
The shared PostgreSQL advisory lock protects both independent pools;
paid review cases and pending Stripe sessions reserve their own pool.
Expired-order recovery, restored financial state, and moderation reject
overbooking in the selected placement. Once paid, a campaign cannot switch
tiers while entitlement remains active. There is no migration: existing
`commercial_advertisements.package_id` and `.placement` VARCHAR columns
already support the new identifiers.

If availability cannot be verified, the interface withholds the price and
disables buying rather than guessing. An occupied premium slot cannot be
purchased even if one or more ordinary €30 positions remain available.
Approval begins the purchased calendar month; creating a draft or opening
Stripe does not activate advertising.
