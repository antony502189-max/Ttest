# Homepage commercial advertising

Commercial campaigns are separate from property listings. The `commercial_advertisements` table owns campaign content, payment and moderation state, schedule, and the `homepage_bottom` placement. The internal house ad is frontend content and has no database row.

## Lifecycle

An authenticated advertiser uploads one JPEG, PNG, or WebP through `/api/v1/advertisements/uploads`. The existing bounded image decoder normalizes it to WebP and generates card and thumbnail variants. The upload is tagged `advertisement_image`; listing publication rejects that media kind. Campaign creation starts in `pending_payment`/`unpaid`. `POST /advertisements/{id}/checkout` returns a test checkout descriptor and does not change state. An explicit `POST /advertisements/{id}/fake-payment/complete` records `paid` and moves the campaign to `pending_review`. Only a backend allowlisted administrator may approve, reject, or deactivate. Approval sets an active window, defaulting to 30 days. Editing approved content clears approval and returns it to review. Cancellation removes it from public display immediately.

`AdvertisementPaymentService` is the provider boundary. Its current `FakeAdvertisementPaymentService` records only test state. No card data, payment SDK, gateway call, or real production price is present. A real provider should implement checkout creation and a verified asynchronous completion/webhook, then use the same payment transition and moderation lifecycle. Production launch of paid campaigns requires pricing, reconciliation, refunds, idempotent webhook handling, and legal copy to be decided separately.

## Public rendering

`GET /api/v1/advertisements/homepage` returns at most three safe public DTOs. The homepage shows the first, ordered by administrator priority, approval time, then ID. Eligibility requires active status, paid status, valid start/end window, active owner, and live image. Both desktop and mobile render the same content section near the bottom. The client treats an API failure as an empty result and shows the house ad. Images request the `card` variant lazily, with fixed aspect ratio and a neutral failure fallback. Public media access applies the same eligibility rules; owner/admin can inspect pending media through authenticated requests. Deactivation and expiry are revalidated on every media request.

## Security and operations

All write routes derive ownership from the bearer session. Administrator routes use the existing `require_admin` allowlist. The server validates text lengths and rejects markup, restricts destinations to HTTP(S) URLs or normalized phone, WhatsApp, and email values, and rejects dangerous schemes. External links use `rel="noopener noreferrer sponsored"`. Advertisement uploads use the existing MIME, decoded type, byte, pixel, quota, and variant limits. The media deletion and reconciliation paths count campaign references. The existing distributed rate limiter covers creation and uploads. Logs use event names without campaign IDs as metric labels.

Apply Alembic revision `0052_commercial_advertisements` before deploying the backend. It adds the advertisement image media enum value and an independent table/indexes; it does not change listing rows. The enum value remains after downgrade because removing PostgreSQL enum members would require a risky type rebuild. Monitor test payment and moderation logs during rollout. The public API can be deployed before the frontend; with no approved campaigns, the frontend shows only the house ad. Do not deploy this feature to production until the owner approves the test-payment UX and moderation operations.
