# Administration and moderation

The production administration console is available at `/admin` and intentionally opens on **Users** rather than a dashboard.

## Authentication and authorization

The normal Google authentication flow is reused. Production admin authorization is enforced by the backend on every `/api/v1/admin/*` route.

An account is an administrator only when:

1. it is authenticated;
2. it has a linked Google identity (`google_subject`);
3. its normalized email has an active row in `admin_access`;
4. it is not subject to an active full-account moderation restriction.

The initial migration seeded these administrators:

- `tf.shuler@gmail.com`
- `antony502189@gmail.com`

The forward repair migration `0039_admin_grant_repair` deterministically restores
their **allowlist grants** if either row was absent or inactive. It never creates,
unblocks, restores, or moderates a user account, so a blocked, deleted, restricted,
or password-only account is still not an administrator. A password-only designated
account receives a self-only `GOOGLE_IDENTITY_REQUIRED` response from
`GET /api/v1/admin/access`; the Profile page then offers the normal Google flow to
link the authoritative Google account with the same email. The allowlist is never
returned for another account or treated as an email-only authorization bypass.

Administrators can add or revoke other administrator emails under **Settings → Administrators**. All administrators have equal rights. Self-revocation is rejected, and the backend never allows removal of the last active administrator. Allowlist changes are serialized so two concurrent revocations cannot both observe the same stale administrator count.

The frontend role is not a security boundary. Production access and production navigation visibility are derived from the server-side admin authorization decision. Mock mode retains the legacy local `admin` role only so isolated browser tests do not require a real backend.

## User restrictions

`user_restrictions` records revocable moderation restrictions. Supported types:

- `full` — normal protected application actions are denied, but identity/login/refresh sessions are intentionally preserved so a restricted account can rehydrate its identity and render the moderation reason, expiry state and support path after a reload. This identity bootstrap is not functional application access: ordinary protected endpoints still enforce the full restriction through `current_user`, and publish/view policies remain denied;
- `publish` — the account may browse and manage its profile but cannot create/publish/renew listings;
- `view_listings` — the account may remain signed in and publish, but public listing search/list/detail/image, messaging, reporting and saved-listing collection flows are denied while the restriction is active.

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

The Listings console exposes **1 day**, **1 week**, **1 month**, **forever**, and a
custom future date. `ends_at = NULL` means a first-class permanent restriction;
the database check permits NULL or an end after the start, and the expiry worker
skips permanent rows. Administrators must explicitly remove a permanent
restriction. Restriction and unrestriction responses retain any existing TOP
promotion metadata so the moderation UI cannot lose the persisted promotion.

Listing moderation writes and automatic listing-expiry handling use the same `User → Listing → Restriction` row-lock ordering as account deletion, preventing cross-flow deadlocks and revalidating owner/listing state before mutation or restoration notices.

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

These narrowly scoped identity/moderation endpoints intentionally use the lower-level authenticated-user dependency so a fully restricted account can still render its reason and support path. Ordinary protected endpoints use the moderation-aware dependency and deny full restrictions by default. `/api/v1/admin/*` additionally enforces full-account access before the database-backed administrator allowlist.

The frontend moderation gate shows the reason, expiry state (`Sin fecha final` for permanent restrictions) and support address instead of exposing a raw `403` as the user experience.

## Account deletion

Admin deletion is a **soft delete**. It sets `users.deleted_at`; it does not physically remove the user row. Unlike a moderation restriction, account deletion revokes existing refresh sessions. Public listing queries exclude deleted owners, while administrative history and report relationships remain available.

Deleted-account detail in the admin console is historical/read-only: restriction, unrestriction, repeated deletion and note-write controls are not offered after `deleted_at` is set.

An active administrator cannot be restricted or deleted until their admin access is revoked.

## Reports, notes and audit trail

The console contains:

- **Users** — search/filter and user detail;
- **Reports** — moderation workflow and direct navigation to the related owner/listing;
- **Listings** — independent listing restrictions;
- **Activity** — read-only `audit_logs` history;
- **Settings** — administrator allowlist management.

Admin user/report/listing/audit clients drain every server page rather than silently truncating at 200 rows. Cursor pagination is used after the first full page so concurrent inserts/deletions cannot shift offset boundaries, while the server's offset ceiling remains fail-closed.

Reports can target either a listing or its advertiser/user while retaining the listing and owner as historical investigation context even after soft deletion. A new report can only be created against a currently public listing, and an authenticated requester must also pass the listing-view moderation policy.

`admin_notes` are internal and are never exposed through user-facing endpoints. Note creation locks and revalidates the target account so a concurrent soft delete cannot create a new write on a record that has already become historical.

Risky operations require explicit confirmation in the UI. Account deletion additionally requires typing `DELETE`.

## TOP listings and map markers

`listing_promotions` is the sole TOP source of truth. Only publicly eligible,
published listings may be promoted. A first promotion, re-promotion, and removal
each write an audit event and invalidate the catalog. Public search applies the
promoted tier before the ordinary tier, with newest `boosted_at` first inside TOP;
normal filters and pagination use that server-side ordering rather than a client
sort.

Desktop and mobile map markers use the returned `promoted` state. TOP markers are
red, have a higher collision/z-index priority, and update in place after a catalog
refresh. Geometry changes drive map fitting; a TOP-only refresh updates marker
styling without resetting a user's pan or zoom.

## External import operations

`/api/v1/admin/external-import/runs`, `/worker`, and `/run` remain protected
operational API endpoints. They are intentionally not exposed in the moderation
console because import execution is operated through the existing worker and
production monitoring process; no second scheduler or worker is created. See
`docs/production-operations.md` for the authenticated inspection workflow.

## Operational safety

Do not:

- make frontend-only admin checks the authorization boundary;
- use the legacy product `role` as the production administrator decision;
- revoke identity/refresh sessions merely to implement a full moderation restriction—the restricted session is intentionally needed for moderation UX;
- hard-delete user rows for ordinary moderation;
- overwrite a listing's normal status just to represent a temporary restriction;
- represent permanent restrictions with arbitrary far-future dates;
- expose moderation-hidden listing media, messaging, reports or saved-listing state through alternate resource paths;
- remove audit history from the admin UI;
- add a second scheduler solely for restriction expiry.
