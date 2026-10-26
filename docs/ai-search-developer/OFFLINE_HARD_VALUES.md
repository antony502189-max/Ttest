# Partial AI-09 preparation: offline hard-value SQL

Date: 2026-10-26. Branch: `codex/ai-offline-hard-predicates`.
Stacked base: [#383](https://github.com/antony502189-max/Ttest/pull/383),
`97494713989377c34fc7756caaddfcdc09ba2ad7`, above unmerged #382/#381/#380.
Main remains `1292c680` (payment #372). All three final-head #383 workflows
were rechecked completed/success; none of these branches is merged.

## Current parser decision

The owner explicitly requested closing [#373](https://github.com/antony502189-max/Ttest/pull/373)
without merge. At this chat's initial check it was closed, merged=false, at
preserved head `bdd7ca93`. During implementation a later external action reopened
it: fresh GitHub metadata shows open, merged=false, updated 20:10:40 UTC, with a
new COMMENTED review explicitly described as AI verification on the same SHA.
Two CHANGES_REQUESTED reviews remain on earlier heads; no APPROVED review exists.
This chat did not change #373's state or submit any review. Neither closing nor
reopening, AI fixes or green CI authorize this chat to port/activate its builder.
Earlier dated reports saying no reviews are superseded by this snapshot. Real
extraction/minimization remains an unresolved integration dependency requiring
a separately authorized approach.

## Implemented scope

`HardValueRequirements` is a strict, internal, deliberately partial value
contract. It requires at least one of: confirmed rented-unit capacity >= N;
exact furnished, bills_included, balcony or terrace boolean. It rejects
unsupported keys, coercion, duplicate keys and unbounded quantities. It is not
a replacement for AI-08 SearchIntent. No partial intent adapter silently drops
other hard criteria; such an adapter does not exist in this increment.

`hard_value_predicate(features, requirements)` returns a composable SQLAlchemy
PostgreSQL expression. It does not execute a query or access catalog data.
Requirements remain bound parameters. Each requested key needs exactly one
explicit_allow feature with the exact supported scope and typed value. Unknown,
conditional, conflict, legacy, missing values, mismatched scopes and duplicate
peers fail closed. Confirmed boolean false is distinct from missing evidence.
Capacity uses >= and never reads legacy room_capacity, available_spots or
current_room_residents. A guarded CASE prevents unsafe numeric casts on malformed
JSON. Optional null qualifiers from the actual DTO serializer are normalized.

This is a value predicate, **not a provenance or current-source authorization
gate**. Its caller must supply a projection validated by the authoritative writer
and revalidate current source generations/status, projection/resolver versions,
visibility, user/moderation/price restrictions in the eventual query transaction.
No arbitrary client/model JSON may be treated as verified input. There is no
freshness TTL or owner override policy here. Source-current read guards remain
required before endpoint integration; persisted projections alone are insufficient.

Apply this predicate with all other hard/eligibility predicates **before**
count/order/seek/limit. Existing commercial order must remain unchanged. Tests
demonstrate this composition on the actual projection table joined to synthetic
ranked candidates; they do not integrate or certify the existing listing query.
The implementation is shared SQL expression groundwork for future interactive
and saved-search matching, not a complete shared matcher or AI-09 endpoint.

Pets/species/size/count, smoking scope, couple/children, price/period/deposit,
geography, accommodation, dates/stay and amenities remain unsupported here.
No reason-code/card response, signed cursor, session/quota integration, index
tuning or notification consumer is introduced. Callers must not advertise a
whole intent as satisfied merely because this subset passed.

## Validation

Local final verification on Python 3.14.4, pinned SQLAlchemy 2.0.51/Pydantic 2.13.4,
owned disposable PostgreSQL 18.6:

- **276 focused passed**: 176 unit + 100 PG. Increment: 12 unit + 10 PG;
  all 254 existing focused cases retained.
- **1011 backend unit passed, 15 platform/opt-in skipped, 413 integration
  deselected**. Focused units are included, not additional.
- Ruff app/tests, mypy 126 modules, pip check and diff checks passed.
  Migration governance tests are included in the full unit suite.
- Zero test schemas left; owned loopback cluster stopped. JUnit is ignored at
  `output/ai-hard-focused-pinned.xml` and `output/ai-hard-unit-pinned.xml`.

Initial checks with the shared unpinned Python 3.12 environment (SQLAlchemy 2.1.5)
passed the 22 new cases and 1011 unit cases, but 44 existing queue/worker PG cases
failed on lease-check/autoflush ordering. The same complete suite passed with
the project's pinned environment, borrowed read-only with this worktree supplied
via PYTHONPATH. No shared environment or queue code was modified. Attempted fresh
pinned installation could not resolve a pinned package from the available index;
the already-installed pinned environment was used instead. CI uses constraints.

New coverage includes
strict requirements, actual SQL values/scopes/statuses, corrupt JSON/numeric
bounds/duplicate peers and a combined capacity+balcony+unfurnished query with
count, commercial order, seek and page limit. A larger verified capacity passes
for a smaller party; a high-ranked incompatible candidate does not consume a
page slot. All data are synthetic in an owned disposable loopback PG cluster.

No schema/migration changes, production query-plan or performance claims.
The independent facts chain still needs reconciliation with unmerged quota/
session migrations before schema integration. Full historical PG16/PostGIS chain
and alembic check remain required CI; local PG18.6 lacks PostGIS.

## Boundaries and rollback

Rollback removes the unconnected expression and DTO. No persisted data changes.
No endpoint/importer/provider/daemon is activated; public AI-09 remains incomplete.
No live catalog/DB, paid call, crawling/backfill, staging, merge or deployment.
Current search/cards/TOP/Stripe/map/gallery and saved alerts are untouched.
Real coverage, freshness and browser p95 <=10s remain unmeasured. API keys are
unnecessary. No undecided quota/clarification/alerts/retention/transfer policy
is selected. The managed worktree is owned by this new chat; other checkouts
and the dirty primary workspace are preserved.
