# Homepage commercial advertising

Commercial campaigns are separate from property listings. The `commercial_advertisements` table owns campaign content, payment and moderation state, schedule, and the `homepage_bottom` placement. The internal house ad is frontend content and has no database row.

## Lifecycle

An authenticated advertiser uploads one JPEG, PNG, or WebP through `/api/v1/advertisements/uploads`. The existing bounded image decoder normalizes it to WebP and generates card and thumbnail variants. The upload is tagged `advertisement_image`; listing publication rejects that media kind. Campaign creation starts in `pending_payment`/`unpaid`. `POST /advertisements/{id}/checkout` returns a test checkout descriptor and does not change state. An explicit `POST /advertisements/{id}/fake-payment/complete` records `paid` and moves the campaign to `pending_review`. Only a backend allowlisted administrator may approve, reject, or deactivate. Approval sets an active window, defaulting to 30 days. Editing approved content clears approval and returns it to review. Expired campaigns require a new test checkout for renewal.

`AdvertisementPaymentService` is the provider boundary. Its current `FakeAdvertisementPaymentService` records only test state. No card data, payment SDK, gateway call, or real production price is present. A real provider should implement checkout creation and a verified asynchronous completion/webhook, then use the same payment transition and moderation lifecycle. Production launch of real paid campaigns requires pricing, reconciliation, refunds, idempotent webhook handling, and legal copy to be decided separately.

## Homepage placement and capacity

`GET /api/v1/advertisements/homepage` returns at most **12** eligible campaigns. Eligibility requires active status, paid status, valid start/end window, an active owner, and a live image. The backend serializes approval capacity decisions with a PostgreSQL transaction advisory lock, so concurrent admin approvals cannot exceed 12 simultaneous overlapping homepage campaigns.

The client renders the eligible set as one native carousel in the existing homepage design. It shows one campaign at a time, supports previous/next controls and direct position dots, and advances every eight seconds when the user is not hovering or focusing the carousel. Automatic movement is disabled for `prefers-reduced-motion`. The client also hard-caps the received set to 12 as a defensive boundary.

Desktop and mobile render the same commercial placement near the bottom of the homepage. Mobile keeps the banner as ordinary scroll content above the fixed bottom navigation. If no eligible campaign exists, or the public API fails, the site shows the localized house advertisement ("Your advertisement could be here") instead.

Images request the optimized `card` variant lazily with fixed dimensions and a neutral failure fallback. External destinations are disclosed as sponsored advertising and use safe link semantics.

## Contacts

Website destinations allow only public HTTP(S) URLs. Email uses a validated mailto destination. Phone and WhatsApp accept an explicit international prefix (`+...` or `00...`) or a normal nine-digit Spanish number beginning with 6, 7, 8, or 9; nine-digit Spanish numbers are normalized to `+34...`. Ambiguous local numbers are rejected instead of being silently interpreted as another country's calling code.

## Moderation and editing

An active campaign edited by its owner is removed from public display and returned to moderation. The old active schedule is cleared so a stale `ends_at` cannot make later reapproval impossible. In the current test-payment MVP a successful reapproval receives a fresh default test window. Before a real payment provider is enabled, the commercial entitlement policy for edited creatives must be finalized so paid duration cannot be extended unintentionally.

The administrator view lives inside the existing admin interface and can approve, reject, or deactivate campaigns. A thirteenth overlapping campaign receives HTTP 409 until one of the twelve slots becomes free.

## Media retention

Advertisement media participates in the existing ownership, orphan detection, account deletion, and storage-deletion flow. Terminal campaign rows are retained for 180 days for user/admin history. After that retention window, cancelled/rejected campaigns and long-expired active campaigns are removed in bounded maintenance batches; their media is released only when no remaining listing, avatar, or advertisement reference exists.

## Security and operations

All write routes derive ownership from the bearer session. Administrator actions use the existing `require_admin` allowlist. The server validates text lengths and rejects markup, restricts destinations to safe schemes, enforces ownership, and applies existing rate limits plus a per-account submission cap. Public DTOs contain only display-safe fields. Public media access applies the same campaign-eligibility rules; owner/admin can inspect pending media through authenticated requests.

Apply Alembic revision `0052_commercial_advertisements` before deploying the backend. It adds the advertisement image media enum value and an independent table/indexes; it does not change listing rows. The enum value remains after downgrade because removing PostgreSQL enum members would require a risky type rebuild.

The commercial-advertising PR intentionally does not alter property-map UI, bounded Spain catalog loading, map markers/cards, or search navigation behavior.
