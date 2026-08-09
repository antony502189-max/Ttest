# Administration and moderation

The production administration console is available at `/admin` and intentionally opens on **Users** rather than a dashboard.

## Authentication and authorization

The normal Google authentication flow is reused. Production admin authorization is enforced by the backend on every `/api/v1/admin/*` route.

An account is an administrator only when:

1. it is authenticated;
2. it has a linked Google identity (`google_subject`);
3. its normalized email has an active row in `admin_access`.

The migration seeds the initial administrators:

- `tf.shuler@gmail.com`
- `antony502189@gmail.com`

Administrators can add or revoke other administrator emails under **Settings → Administrators**. All administrators have equal rights. Self-revocation is rejected, and the backend never allows removal of the last active administrator. Allowlist changes are serialized so two concurrent revocations cannot both observe the same stale administrator count.

The frontend role is not a security boundary. Production access is always decided server-side. Mock mode retains the legacy local `admin` role only so isolated browser tests do not require a real backend.

## User restrictions

`user_restrictions` records revocable moderation restrictions. Supported types:

- `full` — normal protected application actions are denied; new password/Google login and refresh-token issuance are denied, and active refresh sessions are revoked when the restriction is applied;
- `publish` — the account may browse and manage its profile but cannot create/publish/renew listings;
- `view_listings` — the account may remain signed in and publish, but public listing search/list/detail/image flows are denied while the restriction is active.

The admin UI exposes the required duration presets: **1 day**, **1 week**, **1 month**, **forever**, plus an optional custom end date.

Every restriction has a required free-text reason. A dated restriction is active while:

- `revoked_at IS NULL`;
- `starts_at <= now()`;
- `ends_at > now()`.

A permanent restriction stores `ends_at = NULL` and remains active until an administrator explicitly revokes it. No fake far-future date is used.

Because authorization evaluates this active window directly, dated restrictions restore access automatically without a separate unban job. The frontend refreshes moderation state on navigation, window focus and periodically so changes made while a session is already open are reflected promptly.

All public listings owned by a user with any active moderation restriction are excluded by the canonical public SQL visibility query. Their original listing statuses are never overwritten, so an expired/revoked restriction restores only listings that would otherwise be publicly visible. Public listing-image authorization applies the same rule, preventing a previously copied media URL from bypassing moderation visibility.

Manual early unrestriction records `revoked_at`/`revoked_by` and preserves the history row.

## Listing restrictions

`listing_restrictions` applies the same dated/revocable model to one listing. An active listing restriction removes the listing and its public listing images from public visibility without modifying its ordinary listing status.

Listing moderation writes are serialized per listing to prevent overlapping active restrictions during concurrent admin actions.

## Automatic expiry notifications

The existing mail worker processes expired **dated** moderation records. Permanent restrictions are intentionally excluded because `ends_at` is `NULL`. Each expired dated restriction has `expiry_notified_at` so the expiry email and in-app notice are queued at most once.

If an older restriction expires after a newer restriction has already become active, it is marked handled but no misleading “access restored” message is sent.

No additional cron, worker, or infrastructure service is required.

## User communication

Restriction, manual unrestriction and automatic-expiry events use the existing mail outbox and also create `moderation_notices` for the account UI.

The moderation support address is:

`tf.shuler@gmail.com`

A current user can inspect their active restriction at:

`GET /api/v1/users/me/restriction`

and moderation notices at:

`GET /api/v1/users/me/moderation-notices`

These narrowly scoped identity/moderation endpoints intentionally use the lower-level authenticated-user dependency so a fully restricted account can still render its reason and support path. Ordinary protected endpoints use the moderation-aware dependency and deny full restrictions by default.

The frontend moderation gate shows the reason, expiry state (`Sin fecha final` for permanent restrictions) and support address instead of exposing a raw `403` as the user experience.

## Account deletion

Admin deletion is a **soft delete**. It sets `users.deleted_at`; it does not physically remove the user row. Existing refresh sessions are revoked. Public listing queries exclude deleted owners, while administrative history and report relationships remain available.

An active administrator cannot be restricted or deleted until their admin access is revoked.

## Reports, notes and audit trail

The console contains:

- **Users** — search/filter and user detail;
- **Reports** — moderation workflow and direct navigation to the related owner/listing;
- **Listings** — independent listing restrictions;
- **Activity** — read-only `audit_logs` history;
- **Settings** — administrator allowlist management.

Admin user/report/listing/audit clients drain every server page rather than silently truncating at 200 rows. User status filters and listing-deletion predicates are applied in SQL before pagination.

Reports can target either a listing or its advertiser/user while retaining the listing as investigation context. A new report can only be created against a currently public listing; moderation-hidden resources return the same `404` as other unavailable public listings.

`admin_notes` are internal and are never exposed through user-facing endpoints.

Risky operations require explicit confirmation in the UI. Account deletion additionally requires typing `DELETE`.

## Operational safety

Do not:

- make frontend-only admin checks the authorization boundary;
- hard-delete user rows for ordinary moderation;
- overwrite a listing's normal status just to represent a temporary restriction;
- represent permanent restrictions with arbitrary far-future dates;
- expose moderation-hidden listing media through direct asset URLs;
- remove audit history from the admin UI;
- add a second scheduler solely for restriction expiry.
