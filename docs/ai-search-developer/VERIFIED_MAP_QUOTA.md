# Verified existing map and read-only quota — updated 2026-10-28

Cards and map now share one verified_intent_predicate: typed hard match, current-source proof and actual current economic/card-value guards, always before result processing. Existing map markers, native/external redirects, promotion flags and300marker/20x20clustering behavior are reused through an extracted _search_filtered_map. Ordinary manual map keeps its original filters/helper. No new map, routing, POI, provider/crawling or geometry inference is added.

VerifiedCardSearch map_owned and map_result read the same owned active normalized intent in read-only RR snapshots. Unknown/stale evidence, incompatible promoted rows and current listing/user restrictions are excluded before marker limit or cluster aggregation. API map view accepts only explicit viewport/zoom; semantic constraints remain the server-owned intent. Durable-result map preserves the original result intent after followups and returns intent_hash for client stale-result protection. Result metadata endpoint returns the original normalized intent/count/hash without transcript or re-inference. Ownership/expiry apply to all paths.

DailyQuotaView/daily_status provide current Madrid date/reset, limit/used/reserved/remaining from one read-only RR snapshot. A missing day returns approved guest3/auth200 with zero counters without creating a ledger row. Reads never renew sessions, debit, recover leases or transfer guest state. Existing generated database limits remain authority when a row exists; no business-policy/default changes. GET/quota uses the existing signed-guest or persisted-bearer boundary and is no-store.

Capabilities now declare map availability alongside text; all capabilities remain false without an explicitly constructed runtime. Application still constructs no runtime and activates no provider/worker. Sentry private-event filtering also handles malformed private URLs conservatively; unrelated telemetry remains unchanged.

Validation:3realPG daily-status cases(read-only/no writes, reserve/release/success, auth/guest isolation, Madrid midnight after DST). Existing map/HTTP integration cases extended for markers and clusters after source mutation, compatible promotion flags, permanent blocked owner, wrong owner/version, original-result map/hash/metadata, free quota reads and existing manual map parity. Exact-head full PostGIS CI is required; local cluster has no PostGIS. Ruff/mypy147 and local backend unit suite. No real coverage/freshness/native owner-fact precedence/SQL capacity/browser10s claim.

#392, #393 and #394 were merged into `main` on 2026-10-27. #395 targets that main
and is the next review checkpoint. #396 (home text panel) and #397 (result map UI)
remain dependent PRs. This is a source contract, not a deployment or activation.
Public runtime remains absent. Privacy/provider/freshness/performance gates still
require separate evidence before public activation.

## Intent identity and live data (R-07)

`intent_hash` identifies the normalized query, including session/version. It
rejects a response for a different intent; it is **not** a marker-set revision,
data freshness token, cache validator or shared card/map database snapshot.
Source/proof changes, publication/moderation and clock-driven TOP changes can
change items/counts/promotions while this hash stays the same. Each request
reevaluates current data in its own transaction. Separate card/map requests can
differ even with the same hash. A late response for the same intent still needs
the client's own viewport/request sequencing and cancellation. The hash cannot
order those responses. No cross-request snapshot synchronization is promised;
no new revision/snapshot API is introduced by this review.

## Added review regressions (R-02, R-05, R-06)

Cards compile once and reuse the exact same private plan for SQL and reason
codes; the public shared predicate still compiles its own plan from the intent.
HTTP invalid coordinate ordering is now validated with the body so it returns
the same private 422 as invalid ranges, fields or versions.

PostGIS regressions cover 0/299/300/301/302 valid candidates at zoom 8/12/13/21,
all four inclusive viewport edges, multiple cells, exact IDs/counts, promotions
and concurrent alternating viewport reads. A later phase changes 101 sources,
hides 100 rows and removes 50 proofs under the same intent, excluding them before
the marker threshold and aggregation. JUnit records synthetic query timings;
these single-source fixtures do not establish representative SQL capacity.
HTTP tests cover foreign/missing/expired result metadata/maps, guest/auth
isolation, stale versions, CSRF, injected fields/invalid bounds, blocked auth
quota, missing/expired guest quota, no row creation and unchanged session TTL.

The API inventory was regenerated using `python scripts/security-inventory.py`.
Earlier HTTP policy changes moved handlers without regenerating line references;
the cause was stale generated output, not a new generator algorithm defect.

## R-01: required capacity measurements before public activation

Performance risk remains open. No slowdown or p95/p99 success is claimed.
Representative measurements require a separately authorized isolated catalog
with realistic listing/source/fact multiplicity and density. This review does
not authorize application/staging DB access, crawl or production load.

Before running or accepting this gate, the activation reviewer must approve
the workload and numeric latency/resource/concurrency budgets. No default budget
or product policy is selected here. Record the dataset distribution, PostgreSQL/
PostGIS versions, CPU/RAM/IO limits, indexes/statistics, sources/facts per row,
valid/stale/hidden mix and exact code revision. Use bounded read-only transactions
with operator-chosen statement timeouts. Capture `EXPLAIN (ANALYZE, BUFFERS,
FORMAT JSON)` for the high-zoom 301-row probe, its fallback cluster query and
low-zoom aggregation at zoom 8/12/13/21 with 0/299/300/301/302 and thousands of
candidates. Explain executes the query: use only the approved isolated dataset.

For each viewport record warm/cold samples, sample counts, p50/p95/p99,
execution/planning times, returned/visited rows, shared/temp buffers, CPU/IO and
cancellations. Repeat with the approved parallel map workload and rapid viewport
changes; prove previous-request cancellation and server resource release rather
than only hiding late responses. Test a separate heavy-map concurrency budget
and its fail-closed behavior. Compare measurements with approved budgets; optimize
from actual plans and repeat correctness tests after any SQL change. An HTTP
rate gate alone does not bound one map request's work. Save sanitized plans and
results as release evidence. Keep public runtime disabled until this and the
remaining privacy/provider/freshness gates pass.
