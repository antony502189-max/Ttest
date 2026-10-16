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

In **Mis anuncios**, the TOP action on an individual listing opens a choice
between homepage placement and TOP. The two page-level promotion cards are hidden.
Both services keep that listing selected. TOP asks for duration before showing
its total; homepage placement shows its price on the final confirmation dialog.
Neither opening the choice nor moving between steps creates a payment session.
TOP duration is selected with an end-date calendar and 10/14/21/30-day presets.
The displayed start date is fixed because service starts after payment (or extends
an existing TOP period). The supported duration remains 10–365 days; calendar
arithmetic uses date-only UTC values so daylight-saving changes do not alter the
number of paid days. Checkout still submits the duration, not a scheduled start.

The existing homepage photo slot can also be purchased from **Mis anuncios** for
**€60 for one calendar month**. It shows the selected published listing's photo
and a direct link, in the existing homepage layout. Checkout reserves the single
slot; concurrent purchases and administrator replacement of a purchased slot
are blocked. It starts on confirmed payment and ends at the same UTC time on the
next month's corresponding day (clamped to the last day for shorter months).
There is no recurring subscription. A new purchase is possible after expiry.

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
