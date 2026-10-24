# PR #372 backend payment-integrity audit

Audit date: 2026-10-24. Reviewed head: `a89e4e0a874de87fc4b3edfc6bca272bed506879`.
Base: `d890f2bb0ff82f22c1d8fda366e1c4c2db037e22` (`main`).
PR: https://github.com/antony502189-max/Ttest/pull/372

## Verified defects and corrections

1. **Replacement Checkout races.** Stripe GETs intentionally commit before
   external IO. Two requests could then independently replace the same expired
   order. A campaign could also switch to premium during that gap while the
   original request retained the standard price. Advertisement replacement now
   reacquires the shared transaction lock and repeats ownership, campaign state,
   package, price, reservation and capacity checks using refreshed ORM objects.
   PostgreSQL barrier tests reproduced both failures before the correction.
2. **Recovery oversold inventory.** A delayed payment that could not fulfill was
   saved as paid/review-required. Operator retry checked capacity only when the
   previous status was expired/failed, so the next retry could grant the occupied
   premium slot. Every assignment now checks capacity, including paid retries;
   unsafe confirmed payments remain in the review queue with their receipts.
3. **Package and placement validation.** Unknown packages silently received the
   standard price; placement was absent from the existing creative fingerprint.
   Unsupported purchases now fail closed, and checkout, fulfillment, approval
   and financial restoration verify the package/placement relationship. Premium
   fulfillment additionally requires its fingerprint and EUR 6000-cent monthly
   order. Existing fingerprint serialization remains unchanged for pending orders.
4. **Invalid fulfillment eligibility.** Payment fulfillment could assign a
   blocked/deleted owner's campaign or a deleted/invalid image. Fulfillment now
   checks active owner and owned advertisement-image eligibility transactionally.
   A confirmed payment that fails validation remains paid/review-required.
5. **Paid periods and legacy edits.** A moderator could shift the start and end
   of an edited campaign, effectively moving its already purchased period. Saved
   paid dates are now immutable on reapproval. The existing edit schema also
   prevented legacy `test_homepage_30d` campaigns from receiving creative edits;
   their standard-form edits now preserve the actual legacy package and dates.
6. **Financial restoration.** Successful restoration could leave fulfillment
   marked review-required. Conversely, a capacity rejection rolled back the
   authoritative dispute result. Restoration now records successful fulfillment,
   or retains a paused service and review note while committing the financial
   result. Eligibility and the appropriate inventory pool are checked first.
7. **Stripe retry contract.** Checkout used an undocumented
   `allowed_payment_method_types` field, and regenerated `expires_at` on each
   retry despite reusing the idempotency key. Creation now uses the documented
   card-only parameter under a pinned API version and a stable expiry one hour
   after the persisted order creation time. Provider failures retain reservations.
8. **Premium development-payment duration.** Without a Stripe order, premium
   moderation fell back to the legacy one-day duration. Premium now uses the
   calendar-month helper in both approval paths. Legacy standard day orders
   retain their stored amounts and day entitlements.

## Verification scope

The complete backend PR diff and supporting order/session, signature, financial
inbox, moderation, media/owner eligibility, inventory and migration code were
reviewed. Regression coverage includes real concurrent PostgreSQL requests for
premium/standard inventory, duplicate and replacement Checkouts, tier changes
during provider IO, signed duplicate/out-of-order webhooks, delayed recovery,
cancellation, local reservation age, invalid fulfillment, authorization, price
tampering, paid edits, renewal, administrator gifts/approval, disputes/refunds,
calendar boundaries and legacy entitlements. Stripe HTTP and financial snapshots
are stubbed; database transactions and advisory locks are real.

The existing shared PostgreSQL advisory transaction lock serializes scarce
inventory mutations. Premium and standard occupancy queries use separate
placements and capacities (1 and 7). Current string columns and indexes support
both identifiers; no migration or historical amount rewrite is needed.

## Local verification

Run from `backend/`, with an isolated PostgreSQL 16/PostGIS 3.4 container and
`APP_ENV=test`, a test database URL, test JWT secret and empty Redis URL:

```text
python -m alembic upgrade head
pytest -q -rs -m 'not integration'
pytest -q tests/integration/test_payment_audit.py tests/integration/test_banner_payment_lifecycle.py tests/integration/test_homepage_purchase.py tests/integration/test_monthly_top_purchase.py tests/integration/test_commercial_advertisements.py tests/integration/test_schema_parity.py
python -m ruff check app tests
python -m mypy app
git diff --check
```

Results: migrations applied successfully; unit suite **835 passed, 15 skipped,
0 failed**; the six PostgreSQL integration files **66 passed, 0 failed**; Ruff
passed across `app tests`; mypy passed for **114 source files**; whitespace
validation passed. Skipped unit cases are opt-in public-source checks or require
native release/media tools unavailable in this Windows environment.

## Limits and operational notes

- No live Stripe charge or account-specific API configuration was tested. The
  HTTP contract is checked with transport tests against the documented API:
  https://docs.stripe.com/api/checkout/sessions/create and
  https://docs.stripe.com/api/idempotent_requests .
- The one-hour expiry is provider-controlled; no local timer releases inventory.
  Unknown creation results retain their reservation. Pre-fix unknown creations
  can require the existing administrator session-reconciliation flow because
  their old request parameters differ. An uncached first creation attempted
  after Stripe's minimum expiry window can likewise require reconciliation.
- Optional live external-source tests and environment-dependent native-tool
  tests are outside this payment audit. The remaining application-wide
  integration/S3 suite and frontend/browser tests were not run locally.
- No frontend files, production deployments, merges or new PRs are part of this
  change. Push is the final execution step and triggers configured PR workflows;
  CI completion is intentionally not monitored.
