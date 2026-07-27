# Second implementation audit

Audit baseline: first-audit `main` ending at `178da0207a1a764e5d22181db5b2f0d36c3fe327`.

This is an independent second-pass review focused on concurrency, security boundaries, data lifecycle, browser/backend contracts and failure modes. It does not use GitHub Actions. Runtime verification remains reproducible through `scripts/final-audit-local.sh`.

## New defects found and fixed

### Authentication and session security

- Refresh rotation, password reset and e-mail verification token consumption were vulnerable to concurrent reuse. PostgreSQL row locks now serialize consumption.
- Replaying a rotated refresh token now revokes the active session family instead of only returning `401` for the old token.
- Concurrent registration and Google-account linking now convert database uniqueness races into controlled `409` responses.
- Browser endpoints that issue or mutate refresh cookies validate the request Origin outside development/test.
- Frontend refresh rotation is serialized through one shared promise, preventing parallel API requests from rotating the same cookie simultaneously.
- Access-token decoding requires `exp`, `sub` and `type=access`; malformed UUID subjects return authentication failure instead of a database error.
- Malformed Argon2 hashes are treated as invalid credentials instead of propagating a server exception.

### Listing validation, search and privacy

- Listing write and patch DTOs strip whitespace, reject unsupported room/status values and prevent explicit `null` values from reaching non-null database columns.
- Exact coordinates can be cleared only as a complete pair.
- Search validates price/area/date ranges, deposits, room-count values and duplicate filters.
- Availability filtering now excludes listings whose availability window has already ended and treats an absent end date as open-ended.
- Public, owner and image endpoints use consistent visibility rules for status, expiry, soft deletion and blocked/deleted owners.
- The frontend no longer truncates the catalog at 100 results; it follows backend `total/offset` pagination until the complete result set is loaded.
- Owner-only `street`, `postcode` and optional exact coordinates survive API hydration and editing without entering public listing DTOs.
- Publish contact name, telephone, WhatsApp and contact-channel settings are synchronized with the user profile before listing creation/update.

### Media and storage lifecycle

- Image decoding checks dimensions before full decode, handles Pillow decompression-bomb warnings/errors and verifies the file before re-encoding.
- Private draft media uses `Cache-Control: private, no-store`; public media has bounded revalidation and ETag/304 handling.
- Listing images owned by blocked/deleted users are no longer accessible through an old direct media URL.
- A listing image cannot simultaneously be assigned as an avatar.
- Replacing listing images marks removed, unreferenced assets deleted and removes their storage objects after transaction commit.
- Deleting a listing removes its image links and cleans assets not referenced by another listing or avatar.

### Messaging, reports and account state

- Message-thread creation is atomic through `INSERT ... ON CONFLICT`, removing the concurrent duplicate-thread race.
- New messages require an active published listing and an owner who accepts contact-form messages.
- Reports can only target active public listings with active owners.
- Favorites, discarded listings and guest imports now use the same public visibility boundary as catalog search.
- Account deletion removes active sessions, reset/verification tokens, favorites, discarded state, saved searches, history and queued mail containing the original address before anonymization.
- Non-mock messages and reports are explicitly excluded from browser localStorage.
- Guest state is consumed once per distinct payload and removed from persisted guest scopes after successful import.

### Admin and production operation

- Admin user responses now contain the complete profile, preventing the frontend from replacing the current administrator with an empty partial profile.
- Admin statistics and lists ignore soft-deleted users/listings.
- Runtime validation rejects unknown environments/storage adapters, invalid limits, HTTP production frontend URLs, local production media storage, missing Redis/SMTP/S3 and production auto-publish.
- The in-memory rate-limit fallback is bounded and Redis failures use a short circuit-breaker cooldown.

## Regression coverage added

- refresh-token replay and session-family revocation;
- availability-window search;
- private/public media cache policy and ETag handling;
- avatar/listing-media conflict;
- listing-media cleanup after replacement and deletion;
- disabled contact-form messaging;
- account-state erasure;
- auth/listing DTO null and whitespace validation;
- production configuration safeguards;
- JWT access-token type validation;
- malformed password hashes;
- bounded in-memory rate limiting.

## Remaining code-level limitations

These are not silent failures, but they remain follow-up engineering work:

- `PublishPage` edit mode still displays empty street/postcode fields because its local `toDraft` mapper does not yet populate the owner-only values. The API layer preserves the stored values, so saving without editing does not erase them.
- The publish success screen still contains legacy copy suggesting immediate visibility/local storage even though production listings enter moderation.
- The publish contact e-mail field is not a separate backend field; the account e-mail remains authoritative.
- Account deletion is optimistically reflected in React state before the DELETE request resolves; a network failure may require session rehydration/reload.
- Catalog correctness now supports more than 100 records, but the browser downloads all matching backend pages. A very large production catalog should move UI pagination fully server-side.

## Verification status

The changes were audited statically and regression tests were added to the repository. No GitHub Actions workflow was created or triggered.

A complete runtime result must be obtained from a clean local checkout with Docker:

```bash
bash scripts/final-audit-local.sh
```

Until that command completes successfully, this report does not claim that Ruff, Mypy, pytest, frontend typecheck/build, Playwright, accessibility, visual parity, PostGIS and MinIO suites are all green.

External production credentials and infrastructure remain outside repository verification: domain/TLS, managed PostgreSQL/Redis, S3 lifecycle, SMTP/domain verification, Google OAuth/Maps restrictions, Sentry and backup restoration drills.
