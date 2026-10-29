# Registered saved intent and rematch dry run (disabled)

Migration 0074 adds a top-level matcher (`manual.v1` for existing rows) and a
separate `ai.v1` table containing a strict immutable criteria snapshot and its own content
hash. There is no result/session foreign key or conversational expiry dependency.
AI snapshots have no legacy mode/query/filters/polygon or alerts column. Older
binaries cannot address them through manual-search SQL. New-table constraints
enforce the AI schema; explicit account self-deletion clears snapshots and command
receipts under the shared collection lock. The owner FK also covers physical
account deletion. Existing
manual constraints and rental-mode nullability stay unchanged. Historical
migrations and the expand-only compatibility checker stay immutable.

Legacy notification SQL and per-row conversion reject non-manual matchers before
filter interpretation. Legacy write/patch/import reject reserved AI metadata;
hybrids in persisted filters are skipped. Manual lists and updates do not route
AI rows back into legacy filters. Registered deletion checks ownership for both
tables. The existing shared saved-search collection lock and combined count also
cover explicit AI saves; no separate background quota policy is selected.
An older binary sees only manual rows and applies its historical manual limit;
the current binary counts both tables. Delivery remains disabled during rollback.

The injected `RegisteredAISearches.save` accepts an owned committed result
reference, never caller criteria/hash or a mutable session. It checks registered
identity, ownership, vocabulary and schema and stores an independent snapshot.
Every save requires an explicit caller-retained UUID `idempotency_key`. The
owned receipt binds the normalized name and original result reference. A retry
returns the current saved object with the same ID before checking the creation
cap or the original session expiry; it never recreates or consumes another slot.
Changing payload under the same key is rejected. A new key intentionally creates
a separate copy. Deletion nulls the receipt target so a delayed retry returns
`SAVED_AI_DELETED` instead of resurrecting a deleted snapshot. Receipts retain only
the binding hash and target ID, not criteria or raw names. Self-delete removes
both snapshots and receipts in its transaction.
Snapshot DTOs include `matcher` and normalized `name`. Reads and writes validate
criteria against both the session and current fact-pipeline vocabularies;
configuration mismatch or later drift returns `SAVED_AI_STATE_INVALID`.
Enable/disable commands use a revision CAS. Reads validate the stored hash and
current schema/vocabulary and reject missing/blocked/deleted/restricted users.

`dry_run` and `dry_run_event` use the exact shared `verified_intent_predicate`
with public visibility and canonical card-value guards in a read-only repeatable
read transaction. Every call re-reads saved state, current sources/proofs and
moderation. An event's historical hash/revision is never delivery authority.
Duplicate/out-of-order events can inspect current state without acknowledgement.
Missing proof returns `not_verified_or_ineligible`, never consumes an event.
Decisions are observations of that database snapshot, not authorizations for any
later delivery; every response has `delivery_enabled=false`.

There is no public save capability/endpoint/UI, event worker, claim/ack lifecycle,
durable delivery decision, mail/push/notification creation, provider or crawler.
An activated worker still requires fencing/retry and idempotent versioned
decisions plus approved background quotas and retention/delivery policy. These
are deliberately not represented as a working alert feature.

Validation: local real isolated-PG migration/snapshot/ownership/CAS/limit/legacy
tests, unit regressions, Ruff and mypy. Dedicated CI runs the complete migration
chain and all fifteen hard-criterion card/map/dry-run parity cases on PostGIS,
along with current-source/proof/moderation/event/delete/disable checks. Exact
counts and links are recorded in the dependent draft PR after CI completes.

Collection recovery is available without activating AI inference or delivery:
authenticated `GET /saved-searches/ai?after=<uuid>&limit=100` returns owned metadata
(`id`, `matcher`, `name`, `revision`, `enabled`), combined collection count and a
cursor. It exposes no criteria and sends `Cache-Control: private, no-store`.
Desktop and mobile saved-search pages load this collection and support deletion
through the existing owned DELETE route. Pagination is independent of the cap,
so rollback overcap or lost client state never prevents listing/deletion. The
offline repository also provides `list_for_user` with validated full snapshots.

Rollback is binary-only. Never run Alembic downgrade on expand-only production
revisions or edit the stamp. Migration0074 explicitly refuses downgrade before
the stamp changes, preserving snapshots; deployment safety checks reject a
downgrade command in production deploy/rollback/Compose. Redeploy with the same
stamp and ordinary upgrade; never attempt to recreate retained objects. Any
schema recovery requires a separately rehearsed backup/restore procedure.
An old binary can exceed the combined cap because it counts manual rows only.
On return to this binary, preserve every row, show the full paginated collection,
allow deletion, and reject new saves until the combined count is below the cap.
Do not truncate saved searches or silently delete data during recovery.

Rollout prerequisite: deploy all legacy guards before allowing any AI saved
writes. Old binaries are not claimed to understand AI snapshots. Public runtime
and delivery remain disabled, so this change does not perform that rollout.


Snapshot save reads the original owned result on its existing collection-lock
transaction connection, through the same schema/vocabulary/hash/session checks
as ordinary result reads. It requires one checkout and supports pool_size=1 with
max_overflow=0; increasing pool capacity is not a correctness prerequisite.
