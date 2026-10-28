# Registered saved intent and rematch dry run (disabled)

Migration 0072 adds a top-level matcher (`manual.v1` for existing rows) and an
`ai.v1` child containing a strict immutable criteria snapshot and its own content
hash. There is no result/session foreign key or conversational expiry dependency.
AI parents have no legacy mode/query/filters/polygon and cannot enable legacy
alerts, including writes from older binaries. A composite foreign key prevents
attaching an AI child to a manual matcher. Historical migrations stay immutable.

Legacy notification SQL and per-row conversion reject non-manual matchers before
filter interpretation. Legacy write/patch/import reject reserved AI metadata;
hybrids in persisted filters are skipped. Manual lists and updates do not route
AI rows back into legacy filters. Registered delete/account deletion cascades to
the child. The existing shared saved-search collection lock and total limit also
cover explicit AI saves; no separate background quota policy is selected.

The injected `RegisteredAISearches.save` accepts an owned committed result
reference, never caller criteria/hash or a mutable session. It checks registered
identity, ownership, vocabulary and schema and stores an independent snapshot.
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

Rollout prerequisite: deploy all legacy guards before allowing any AI saved
writes. Old binaries are not claimed to understand AI snapshots. Public runtime
and delivery remain disabled, so this change does not perform that rollout.


Snapshot save reads the original owned result on its existing collection-lock
transaction connection, through the same schema/vocabulary/hash/session checks
as ordinary result reads. It requires one checkout and supports pool_size=1 with
max_overflow=0; increasing pool capacity is not a correctness prerequisite.
