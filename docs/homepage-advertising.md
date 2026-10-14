# Homepage advertising

The homepage has seven advertising cards at the bottom, using the existing fonts,
white cards, magenta links and lime purchase buttons. Each new `homepage_1d`
campaign costs **€1 per day**, with a selectable duration of **10–365 days**. Duration starts at administrator approval.
Existing `test_homepage_30d` purchases retain their paid duration and price.
The paid number of days is recorded on the order and campaign; approval uses that duration.

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

`GET /payments/advertisements/{id}/quote?days=21` returns the owner’s price and availability
without reserving a place. The explicit payment click calls the existing Stripe
Checkout endpoint. A shared PostgreSQL transaction advisory lock serializes
checkout, moderation, editing, cancellation and webhook state changes.

The banner Checkout body is `{ "days": 21 }`; totals are computed on the server.
Changing an existing open payment's duration requires cancelling that payment
first. Homepage endpoints are `/payments/homepage/quote` and
`/payments/listings/{id}/homepage/checkout`, `/status`, and `/checkout/cancel`.

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
