# Listing lifecycle closure audit

Audited base: `ce7b623534da1b2cca644a31775178c299ef75fd` (merge of PR #156). The backend/domain values below are authoritative; Spanish labels are presentation only.

## Lifecycle and source of truth

| Domain state | Owner label | Entry | Allowed next owner action | Allowed admin transition | Publicly eligible |
|---|---|---|---|---|---|
| `draft` | Borrador | legacy/server fixture only | submit to `pending` | `pending` | no |
| `pending` | Pendiente | production create, resubmit, renew | hide or close | publish, hide, reject | no |
| `published` | Publicado | admin approval; local auto-publish only outside production | hide, close, renew | hide or close | yes, subject to the overlays below |
| `hidden` | Oculto | owner/admin hide | resubmit, close, renew | pending | no |
| `closed` | Finalizado | owner close, expiry, deletion/account deletion overlay | renew/republish endpoint | pending | no |
| `rejected` | Rechazado | admin rejection | edit and resubmit/renew | pending | no |

Effective public eligibility additionally requires: no listing tombstone, unexpired `expires_at`, an active/unblocked/non-deleted owner, and no active listing or owner moderation restriction. External imports use the same `published`/`closed` visibility boundary.

Deletion and expiry are overlays, not extra enum values:

- restricted hard delete stores `status=closed`, `closed_reason=deleted`, and `deleted_at`; it removes favorite/discard relations and listing media relations and schedules orphan storage cleanup;
- account deletion stores `status=closed`, `closed_reason=account_deleted`, and `deleted_at` on all owned listings and anonymizes the account;
- expiry is immediately excluded by public queries and the lifecycle worker deterministically persists `status=closed`, `closed_reason=expired` with history and notifications.

## Cross-consumer consistency matrix

`Y` means visible/actionable as that consumer; `N` means it must not be exposed. “API” distinguishes public from authenticated owner/admin contracts. Every row remains representable in the database.

| Status | Owner My Listings | Public search | Mobile search | Map/markers | Direct public detail | Favorites/discarded | Admin list | Moderation | API | Database |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| `draft` | Y: edit/submit | N | N | N | N/404 | N | Y | Y: send pending | owner Y; public N | Y |
| `pending` | Y: edit/hide/close | N | N | N | N/404 | N | Y | Y: approve/hide/reject | owner/admin Y; public N | Y |
| `published` | Y: edit/hide/close/renew | Y | Y | Y | Y | Y | Y | Y: hide/close/restrict | public/owner/admin Y | Y |
| `hidden` | Y: edit/resubmit/close/renew | N | N | N | N/404 | N (saved row may remain, but is not returned) | Y | Y: restore pending | owner/admin Y; public N | Y |
| `closed` | Y: edit/renew | N | N | N | N/404 | N | Y | Y: restore pending | owner/admin Y; public N | Y |
| `rejected` | Y: edit/resubmit/renew | N | N | N | N/404 | N | Y | Y: restore pending | owner/admin Y; public N | Y |
| tombstoned | N | N | N | N | N/404 | N/relations removed | N | N | N/404 | Y: retained audit tombstone |

A `published` row with an expired timestamp, deleted/blocked owner, or active moderation restriction follows the public `N` cells while remaining visible to its owner and administrators. Unknown API status values fail closed to the non-public frontend state `Pendiente`.

## Mutation refresh contract

| Mutation | Authoritative mutation | Same-session refresh |
|---|---|---|
| create | `POST /listings`, then image sync | private owner cache updates immediately; public cache is fetched separately; search/map/favorites never receive pending optimistic rows |
| edit | owner `PATCH /listings/{id}` | owner and public catalogs refetch; `catalog:updated` refreshes search and open detail |
| hide / close | owner patch | same refresh; public list/map/favorites/detail lose the row |
| show / resubmit | owner patch to `pending` (or publish intent mapped by backend) | owner cache shows the returned real status; public consumers refetch and remain empty until approval |
| renew / republish | `POST /listings/{id}/renew` | owner and public catalogs refetch; production returns to `pending` |
| moderate / approve / reject / restrict / unrestrict / promote | admin routes | admin row updates and emits `catalog:refresh`; public, owner, search, map, favorites, and open detail refetch |
| restricted hard delete | `DELETE /listings/{id}` | owner/public caches remove the row and refetch |
| account delete | `DELETE /users/me` | backend invalidates catalog; current session clears public/owner/account collections and media references |
| automatic expiry | lifecycle worker plus effective query timestamp | worker touches catalog; polling/focus refreshes public and owner consumers |
| detail view count | public detail GET, once per viewer/day | returned detail snapshot is merged into public and owner caches so My Listings does not keep the prior count |

`allListings` is exclusively the public catalog. `ownedListings` exclusively hydrates `/listings/mine`. This separation is the invariant that prevents pending/hidden/rejected/closed owner rows from leaking into mobile search, map markers, public filter counts, favorites, or direct detail fallback.

Public hydration and forced refresh use a bounded version/list/version handshake. A concurrent mutation cannot pair an old listing snapshot with a new catalog version and suppress the next poll; an unstable final attempt deliberately retains the pre-fetch version so the normal poll retries.

## Owner, admin, and delete capabilities

- Owners can edit fields/media, hide, close, resubmit, renew/republish, and view every non-deleted owned state. Server-side ownership is checked for edit, status, renew, image replacement, and restricted hard delete.
- Admin moderation is authorized by active Google-backed `admin_access`, not the client role. Status changes must use the moderation endpoint and its transition table; the general owner patch route cannot bypass it.
- Administrators can inspect, approve, reject, hide, close, restore to review, restrict/unrestrict, and promote/unpromote. There is intentionally no admin hard-delete route or admin UI delete action.
- Ordinary owner deletion is intentionally unsupported. Hard delete remains restricted to the two verified operational identities, and those identities must additionally own the listing or hold active server-side admin access.

## Publication, drafts, localization, and validation

- Publication is one idempotent listing transaction followed by independently retryable media synchronization. A durable UUID key prevents duplicate rows and rejects changed-payload replay. A partial image failure retains the draft and existing listing ID.
- Production creates `pending`; success copy says the listing was sent to moderation. It is never added to the public catalog optimistically.
- Drafts are intentionally browser-local. Versioned v2/v3 migration keeps canonical select values stable across ES/RU/EN and language changes; there is no server draft API.
- Canonical values for rental mode, room type, bathroom, toilet, shower, kitchen, bed type, tenant restrictions, occupant types, and status are validated before database mutation. Translated labels are not submitted as values.
- Expired create/edit payloads fail validation. Admin approval of an already expired row fails with `LISTING_EXPIRED` and requires renewal.
- Migration `0040_listing_capacity_contract` aligns both historical database checks with the existing API/UI range of 1–10. No production migration was applied by this task.

## Media behavior

Uploads belong to a server-loaded user. Listing image replacement locks the listing and all old/new assets, requires active `listing_image` assets owned by the requester (or an active admin), replaces ordering atomically, and schedules only unreferenced assets for deletion. Avatar/listing dual attachment is rejected. Public media URLs independently enforce listing/owner/restriction/expiry visibility and use revalidation-required caching. Account deletion detaches owned assets and schedules storage deletion.

## Search, map, detail, favorites, reports, and notifications

- Desktop and API search use `visible_query`; mobile search and both map implementations consume only the refreshed public `allListings` result. Map coordinates are the privacy-jittered `location`; exact coordinates are owner-only.
- Direct API detail, canonical HTML, sitemap, public media, favorites/discarded collections, and report creation independently enforce the same effective visibility predicates. Canonical listing HTML is no longer publicly cacheable across lifecycle mutations.
- Favorite rows may remain while a listing is temporarily unavailable, but collection reads filter them out. Hide/close/reject/expiry/restriction creates an unavailable notification; hard/account deletion removes relevant collection relations.
- Listing status, restriction, expiry, saved-search-match, and favorite-unavailable notifications retain a nullable listing reference. Notifications for owner-only states route to My Listings rather than a public 404 detail.
- Reports can only be created for an effectively public listing and retain historical listing/owner context for admin review after soft deletion.

## Repository-wide subsystem classification

| Discovered subsystem | Classification | Evidence / decision |
|---|---|---|
| create/publication and idempotency | VERIFIED AND WORKING | API/service transaction plus publication hardening API/browser regressions |
| publication quotas and rate limits | VERIFIED AND WORKING | active-state counting, row locking, idempotent replay exemption, and concurrent creation regressions |
| local and legacy publication drafts | VERIFIED AND WORKING | v2/v3 canonical-value migration and ES/RU/EN language regressions |
| server-side draft persistence | INTENTIONAL LIMITATION | no draft endpoint; browser-local draft is the documented product contract |
| listing edit and contact profile synchronization | BUG FOUND AND FIXED | owner cache/public consumers now refetch; server ownership and effective-patch validation retained |
| owner management/My Listings | BUG FOUND AND FIXED | private `/mine` state is separate and survives reload; real pending/rejected labels are shown |
| owner hide/show/close/renew/republish | BUG FOUND AND FIXED | show now resubmits; backend transition policy rejects lifecycle bypasses; success copy uses returned status |
| desktop public search | VERIFIED AND WORKING | canonical backend query, paging, filter and frontend server-search regressions |
| mobile public search | BUG FOUND AND FIXED | pending optimistic/owned rows can no longer enter `allListings` |
| map, markers, list/map sync, approximate coordinates | BUG FOUND AND FIXED | map uses the isolated public catalog; API bbox regression uses the same listing ID |
| public and canonical listing detail | BUG FOUND AND FIXED | open detail listens for catalog refresh; canonical HTML requires revalidation |
| favorites and discarded listing references | VERIFIED AND WORKING | add/read/import enforce effective visibility; unavailable state is filtered and notified |
| search history and saved searches tied to newly published listings | VERIFIED AND WORKING | history stores filters rather than listing snapshots; canonical search DTO matching and publication/approval notification tests |
| phone/WhatsApp/external contact links | VERIFIED AND WORKING | visible contacts come from owner/public policy; external provenance/contact fields are server-owned |
| contact form and listing chats/messages | INTENTIONAL LIMITATION | legacy tables remain for compatibility, but API/UI messaging is deliberately unreachable |
| listing notifications and outbox | VERIFIED AND WORKING | transactional status/expiry/restriction/favorite/saved-search notifications and idempotency tests |
| reports/complaints | VERIFIED AND WORKING | only effectively public targets accepted; historical admin context retained |
| moderation restrictions and expiry | VERIFIED AND WORKING | effective query predicates, catalog invalidation, notices, email/outbox, and expiry worker tests |
| admin listing management and promotions | BUG FOUND AND FIXED | owner patch can no longer bypass admin transitions; admin mutations trigger consumer refresh |
| admin deletion | INTENTIONAL LIMITATION | unsupported by existing API/UI; no new destructive capability was invented |
| restricted hard delete | BUG FOUND AND FIXED | verified allowlist remains, with added owner-or-active-admin authorization |
| account deletion and owned listings | VERIFIED AND WORKING | listings tombstoned, public catalog invalidated, collections/media/account data cleaned |
| listing media lifecycle | VERIFIED AND WORKING | ownership, foreign reference, concurrency, orphan cleanup, cache, and storage queue regressions |
| expiration and renewal | BUG FOUND AND FIXED | expired writes/approval rejected; effective query and worker close; renew returns actual moderation state |
| analytics/view counter | BUG FOUND AND FIXED | detail response snapshot now updates public and private in-session consumers |
| API serializers/deserializers | BUG FOUND AND FIXED | unknown status fails closed; owner DTO alone exposes private location/address |
| validation schemas | BUG FOUND AND FIXED | future-expiry invariant added; canonical enums and privileged-field rejection retained |
| database model, enum, constraints and indexes | BUG FOUND AND FIXED | capacity 1–10 migration added; status/owner/location/price/date checks inspected |
| lifecycle/catalog background job | VERIFIED AND WORKING | bounded skip-locked expiry transition, history, notifications, and catalog invalidation |
| external listing importer/source lifecycle | VERIFIED AND WORKING | imported rows use published/closed, source removal is conservative, and dedicated deterministic suites cover it |
| SEO sitemap/robots/canonical pages | BUG FOUND AND FIXED | same visibility query; mutable detail is no longer shared-cacheable |
| test fixtures/model behavior | BUG FOUND AND FIXED | tests no longer hide pending/rejected labels or expect direct show to bypass moderation |
| browser demo/mock provider | BUG FOUND AND FIXED | raw owner/admin state is retained privately while public search/map receive only published, unexpired rows with unblocked owners |

No discovered listing subsystem is left unclassified.

## Known intentional limitations and NOT PROVEN

- **INTENTIONAL LIMITATION:** server-side drafts, ordinary owner hard delete, admin hard delete, and in-product listing messaging/contact forms are not supported.
- **VERIFIED LOCALLY:** a clean Alembic upgrade reached `0040_listing_capacity_contract (head)`, and the end-to-end lifecycle closure regression passed against the local PostgreSQL/PostGIS test database. This does not assert that production has run the migration.
- **NOT PROVEN:** real S3 object deletion, email delivery, live external-source crawling, Google Maps production rendering, CDN behavior, and production data were not exercised. Evidence would require their credentials/services or an authorized staging/production read-only run. Source contracts and deterministic local tests cover their boundaries only.
- Production was not deployed or mutated.
