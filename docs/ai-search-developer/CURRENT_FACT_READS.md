# Bounded offline current-projection reads

Date: 2026-10-26. Branch `codex/ai-current-fact-reads`, stacked on
[#384](https://github.com/antony502189-max/Ttest/pull/384) head `d5e260d7`.
All three #384 final-head CI workflows are successful; it remains unmerged.
Main remains `1292c680`. See [PR integration order](PR_INTEGRATION_ORDER.md)
for the newly merged/approved #373 in planning and unmerged #374–384.

## Behavior

`FactPipeline.read_current_projection(listing_id)` explicitly reads one canonical
projection in a new PostgreSQL REPEATABLE READ, READ ONLY transaction. All
authority, source-generation, batch, observation and projection statements share
one MVCC snapshot. No row locks, repair, enqueue, revision update, outbox event,
provider or network builder is performed. Missing catalog identity creates no row.

The read verifies stored schema/types, anchor revision, configured resolver and
vocabulary, current source identity/status/fingerprint/coarse snapshot token,
batch identity/generation/hash/versions and bounded typed evidence. It uses the
same extracted manifest/pending-barrier helper as the writer. It then recomputes
the source-only resolution and compares the complete typed projection, including
supporting IDs, to stored output. Matching metadata alone does not authenticate
corrupted feature JSON. The writer's manifest and hash format are unchanged.

Return values:

- A detached validated SearchProjection means it agrees with evidence/state in
  that transaction's snapshot. Unknown/conditional/conflict remain unresolved;
  the read never upgrades them into permission.
- `None` means unavailable/stale/unsupported/incomplete evidence. A pending
  generation is not a verified zero-result. No fallback to old projection JSON.
- DB failures propagate. The caller must fail closed rather than broaden a
  search or count an unavailable read as a successful empty result.

Missing/retired/remapped sources, changed payload without a legacy fingerprint
update, new unobserved active sources, invisible/deleted listings, mismatched
revision/configuration and corrupt observations/projections invalidate old output.
After explicit reconciliation a retired peer can be omitted while another
current active source continues supporting the projection.

## Limits

This is an offline single-listing correctness boundary, not the AI-09 catalog
query. It re-reads bounded batches/observations and is not intended as an N+1
per-card filter. It must not be applied after count/order/seek/limit to fabricate
a correct page. Efficient set-based source/projection guards and all hard intent
criteria must be integrated into the eventual existing SQL query before paging.

The snapshot can become old after it starts or after the method returns. The
test deliberately commits a concurrent source change/new source: the in-flight
read consistently sees its original snapshot, and the next read rejects the old
projection. The result is not a lasting authorization/cached proof and does not
establish a global catalog snapshot or prevent later deletion. Existing full
user/moderation/restriction/price eligibility and card/cursor revalidation remain
required. Only the existing publication/deletion guard is reused here.

No source-age TTL is chosen. Last successful check is not an availability promise.
Real freshness/coverage, query plans, source hash cost and browser p95 <=10s are
unmeasured. Owner precedence, retention and outbound minimization/provider gates
are unchanged. Parser approval in planning is not production privacy approval.

## Validation and rollback

New disposable PostgreSQL cases cover read-only/isolation settings, no writes or
missing-anchor insert, detached results, source/price/fingerprint changes,
retirement/deletion/remap/hidden listing, new-source/pending-generation barriers,
revision/config changes, corrupt feature/fact/batch data, bounds, reconciliation,
conflicts, concurrent changes and storage failure. Final test counts and CI links
are recorded in this increment's PR.

Local pinned Python 3.14.4 / SQLAlchemy 2.0.51 / owned loopback PG18.6:
**300 focused passed** (176 unit + 124 PG), including **24 new PG cases**;
all 276 prior focused cases remain included. **1011 backend unit passed / 15
platform-or-opt-in skipped**. Ruff app/tests, mypy 126 modules, supply-chain and
immutable/expand-compatible migration checks passed. No temporary test schemas
remained; owned cluster stopped. Ignored JUnit: `output/current-projection-focused-final.xml`
and `output/current-projection-unit.xml`. Historical PG16/PostGIS/alembic check,
Payment and browser validation remain CI checks, not local PostGIS claims.

No migration/schema change. Rollback removes the unconnected read method and
inlines the unchanged shared manifest code. No persisted history is discarded.
No live catalog/DB, paid provider, crawling/backfill, staging, main merge/deploy
or endpoint/daemon activation. Existing cards/TOP/Stripe/map/gallery/importers
and notification delivery are untouched. API keys remain unnecessary.
