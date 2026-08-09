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

Administrators can add or revoke other administrator emails under **Settings → Administrators**. All administrators have equal rights. Self-revocation is rejected, and the backend never allows removal of the last active administrator.

The frontend role is not a security boundary. Production access is always decided server-side. Mock mode retains the legacy local `admin` role only so isolated browser tests do not require a real backend.

## User restrictions

`user_restrictions` records dated moderation restrictions without terminating the user's existing authentication sessions.

Supported types:

- `full` — normal protected application actions are denied;
- `publish` — creating/publishing/renewing listings is denied;
- `view_listings` — opening listing details is denied.

Each restriction has a required free-text reason and end date. A restriction is active only while:

- `revoked_at IS NULL`;
- `starts_at <= now()`;
- `ends_at > now()`.

Because authorization uses this date window, expiration restores access automatically without a separate unban job.

All public listings owned by a user with any active moderation restriction are excluded by the canonical public SQL visibility query. Their original listing statuses are never overwritten, so an expired/revoked restriction restores only listings that would otherwise be publicly visible.

Manual early unrestriction records `revoked_at`/`revoked_by` and preserves the history row.

## Listing restrictions

`listing_restrictions` applies the same dated/revocable model to one listing. An active listing restriction removes the listing from the canonical public visibility query without modifying its ordinary listing status.

## Automatic expiry notifications

The existing mail worker processes expired moderation records. Each expired restriction has `expiry_notified_at` so the expiry email and in-app notice are queued at most once.

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

The frontend moderation gate shows the reason, expiry date and support address instead of exposing a raw `403` as the user experience.

## Account deletion

Admin deletion is a **soft delete**. It sets `users.deleted_at`; it does not physically remove the user row. Existing public listing queries already exclude deleted owners, while administrative history and report relationships remain available.

An active administrator cannot be restricted or deleted until their admin access is revoked.

## Reports, notes and audit trail

The console contains:

- **Users** — search/filter and user detail;
- **Reports** — moderation workflow and direct navigation to the related owner/listing;
- **Listings** — independent listing restrictions;
- **Activity** — read-only `audit_logs` history;
- **Settings** — administrator allowlist management.

`admin_notes` are internal and are never exposed through user-facing endpoints.

Risky operations require explicit confirmation in the UI. Account deletion additionally requires typing `DELETE`.

## Operational safety

Do not:

- make frontend-only admin checks the authorization boundary;
- hard-delete user rows for ordinary moderation;
- overwrite a listing's normal status just to represent a temporary ban;
- revoke sessions when applying the requested moderation restrictions;
- remove audit history from the admin UI;
- add a second scheduler solely for restriction expiry.
