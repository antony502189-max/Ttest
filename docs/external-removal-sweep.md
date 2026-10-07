# External listing removal sweep

This is prospective backend lifecycle work for PR #287. It runs in the existing
external-listings worker, never in a public request handler. It does not sweep
historical soft-missing records. No deployment or production sweep is authorized
by this change.

## Baseline audit

Reviewed baseline: `4dad3fce00ccc24be29dd050f97464d2ebb80135`.
The previous enabled-by-default removal job ran every 900 seconds, selected at
most 50 stale active/missing source records per provider, and soft-deactivated
confirmed missing sources. The final source closed its canonical listing;
alternatives could be promoted through upsert. Selection had no inventory-wide
cursor guarantee. Import and removal shared the local lock and Redis key
`ttest:external-listings-import`; removal TTL was `max(1800, interval * 2)`.
Simply changing the interval would have left most of a large inventory unchecked
and produced a 43,200-second lease. Generic redirects and the second unknown
discovery reconciliation could also imply removal without authoritative evidence.

Inspected importer, worker, generic adapters, production Habitaclia installer,
settings/examples/Compose, Listing/source/media models, listing deletion helpers,
media lifecycle and durable storage deletion services, and lifecycle/lease tests.
Foreign keys and indexes were verified in isolated PostgreSQL/PostGIS after the
repository migration chain, rather than inferred solely from ORM declarations.

## Configuration and scheduling

```dotenv
EXTERNAL_REMOVAL_CHECK_ENABLED=1
EXTERNAL_REMOVAL_CHECK_INTERVAL_SECONDS=21600
```

These defaults agree in application settings, backend example, deployment example
and production Compose. Existing explicit environment values still override them:
an operator must inspect actual config during the separately authorized rollout.
Full import remains 7,200 seconds. Removal remains due on worker startup; a due
startup import runs first. Successful/partial sweeps advance the previous removal
deadline by whole six-hour periods; duration does not add drift. Overdue periods
are skipped rather than triggering catch-up storms. Busy locks or failures retry
after 60 seconds. A restarted worker makes removal due again.

## Finite sweep and load limits

```text
acquire shared local/Redis lease
capture sweep_started_at; obtain effective configured adapters (including Habitaclia)
for providers (at most two concurrently):
    count active rows with first_seen_at <= sweep_started_at
    cursor = none
    fetch next 100 (id, URL), source_name + active + snapshot, ORDER BY id
    commit read transaction
    probe direct URLs using existing persistent client, global <= 4, provider <= 3
    for each result:
        lock/re-read canonical then source; reject native, changed URL/status,
        changed canonical relation, or last_seen_at newer than sweep snapshot
        apply state/purge in a short transaction; commit
    advance cursor to last fetched id; repeat until empty or provider circuit opens
log JSON summary; close clients; release only the owned lease
```

Each record is attempted at most once per sweep. All province scopes participate;
there is no scope predicate. Rows added after the snapshot wait for the next sweep.
A row refreshed after the snapshot keeps its newer state. There is no OFFSET or
per-record discovery query. At most two batches of 100 probe tasks are resident;
the semaphores bound actual HTTP. At most two provider sessions run concurrently;
their connections are returned before HTTP, alongside the separate short-lived
heartbeat session. Existing API pool sizing is unchanged.

The sweep calls only `check_listing_state`, without catalogue discovery, image or
video download, image hashing, gallery rebuilding, deduplication or storage I/O.
Direct checks do not retain a catalogue-wide HTML diagnostic dictionary. Adapters
reuse their existing httpx clients and provider-host/SSRF request protections.
Provider failures are isolated; database/heartbeat/lease failures cancel remaining
provider tasks, preserve previous commits and produce a failed sweep. Limits
reduce shared VPS contention; actual production latency/load still requires
measurement and is not promised by mocked tests.

The existing single-column source index required a sort for ordered keyset reads.
Migration `0055_external_removal_cursor` adds only a partial `(source_name, id)`
index for active rows; no data is modified. The isolated PostgreSQL query plan
uses `Index Scan using ix_external_removal_source_cursor`, with source/id index
conditions and a snapshot filter, without Sort. Small tables may still legitimately
use a sequential scan. Downgrade removes only the additive index.

## States and purge

| Evidence/state | Action |
| --- | --- |
| Real active detail | Keep; update check/success/seen timestamps; reset missing/unknown counters |
| Explicit removed / HTTP 410 | Purge source |
| Explicit expired | Purge source |
| HTTP 404 / not_found | Purge source |
| HTTP 403 / challenge / empty access-denial 202 | Keep; blocked diagnostic |
| HTTP 429 / 5xx / timeout / connection failure | Keep; temporary-error diagnostic |
| Unknown HTML / unproven catalogue redirect | Keep; unknown diagnostic/counter, including repeated unknown |
| Absent from partial discovery | No purge without direct confirmation |

`purge_confirmed_removed_source` accepts only removed/expired/not_found. The
existing `deactivate_source_record` stays soft for rejected, retired and legacy
lifecycle reasons. Direct confirmation during ordinary import/reconciliation
also uses the dedicated purge so it cannot strand newly removed rows outside
the active sweep. Historical missing/closed records are not mass-deleted.

Lock canonical before source with populate_existing refresh (never trust cached ORM
fields), require `is_external`, then delete the confirmed
source. If an active alternative remains, preserve canonical and, when the
primary was removed, select the existing best snapshot by location/completeness.
The shared metadata helper applies it without upsert, network or intermediate
commit. Non-primary removal leaves canonical metadata unchanged. Duplicate
closures retain the existing deduplication policy. An unusable active alternative
is a systemic error, not permission to purge the canonical. With no active
alternative, physically delete the external canonical; dependent inactive source
rows cascade as part of that specific canonical purge. Malformed native relations
are refused and logged, without changing source, canonical or media.

## Actual Listing dependencies

| Relation inspected in PostgreSQL | Deletion contract |
| --- | --- |
| favorites | CASCADE; notify unavailable before deleting canonical |
| discarded_listings | CASCADE |
| message_threads | CASCADE; messages cascade from threads |
| reports | CASCADE; user_report_targets cascade from reports |
| listing_status_history | CASCADE |
| listing_images | CASCADE; capture media IDs first |
| listing_views | CASCADE |
| external_listing_sources | CASCADE |
| listing_restrictions | CASCADE |
| listing_room_details | CASCADE |
| listing_promotions | CASCADE |
| homepage_hero_promotions | CASCADE |
| notifications.entity_listing_id | SET NULL; notification retained |

AuditLog.target_id is a plain UUID without a Listing FK: immutable history is
retained. Saved searches store JSON filters, not Listing FKs. There is no separate
saved-collection relation beyond favorites in this model. Map/location fields are
columns on Listing. Commercial advertisements reference MediaAsset, not Listing,
and remain intact. Mail outbox notification history is not erased. Listing's video
asset ID has no FK; the service layer validates/reference-checks it.

Before final canonical delete, capture gallery/video asset IDs and lock media in
the existing deterministic order. Delete references, then reuse
`mark_orphaned_media` and its transactional `enqueue_storage_deletions`. References
from other listings, videos, avatars and commercial advertisements protect shared
assets. Only truly orphaned assets receive deleted_at and durable storage jobs.
MinIO deletion occurs later in the existing deletion worker. The summary counter
`storage_deletions_enqueued` counts durable orphan deletion intents, not guaranteed
new INSERTs (the queue is idempotent by storage key).

## Lease, circuit and observability

Removal lease TTL is fixed at 1,800 seconds independently of the schedule. The
existing lease helper renews ownership by atomic compare/EXPIRE every 15–60 seconds
and keeps DB heartbeat alive. Lost ownership or heartbeat DB failure cancels the
sweep. Release uses compare/DELETE; client/Redis close failures cannot strand the
local lock. Removal heartbeats do not set full-import run ID/last_started_at.

Five consecutive blocked/temporary completions open a provider-local circuit.
Other outcomes reset the streak; one or two isolated failures do not stop a
provider. At most two already-in-flight probes can complete after the threshold.
Queued and remaining rows are deferred untouched. Other providers continue. The
circuit resets on the next sweep; it is not a permanent provider-disable switch.

Each sweep logs JSON containing sweep ID, times/duration, per-source reports,
candidate_records, checked, active, confirmed_removed, expired, not_found, blocked,
temporary_error, unknown, source_rows_purged, canonical_listings_purged,
canonical_sources_promoted, media_assets_orphaned, storage_deletions_enqueued,
deferred_by_circuit_breaker, failed and batches. Results distinguish success,
partial, failed and a busy distributed-lease skip. Partial means conservative
provider/unknown deferral; failed means systemic trouble. No high-cardinality
Prometheus labels were introduced.

## Validation and separately authorized rollout

Focused tests cover every state, repeated unknown, primary/non-primary promotion,
native protection and snapshot races, 150-row multi-province batching, both
provider circuits/reset, global concurrency and adapter failure isolation,
favorites/FKs/audit/media queue/shared native assets, partial discovery, no DB
transaction during HTTP, effective production Habitaclia, six-hour scheduling
separate from full import, TTL/renewal/ownership loss and cleanup after failure.
The 150-row fake-network run measured 150 checks, two batches, three batch SELECTs
including the terminal empty read, maximum provider concurrency three, and 3.021
seconds on the development machine. A two-provider test saturates global four.
These are architecture checks, not production timing estimates.

Future rollout requires separate authorization: deploy reviewed code/migration;
inspect effective enabled/21600 settings; inspect a small controlled sample using
read-only adapter state checks and DB audit; check CPU/DB/network/storage queue;
authorize one manual full sweep; inspect summary/purge/notification counts; then
allow the normal loop. There is no new production dry-run CLI in this change.
Providers may block/change HTML; ambiguous offers remain conservatively active.
The first real 3,000-record production duration has not been measured.
