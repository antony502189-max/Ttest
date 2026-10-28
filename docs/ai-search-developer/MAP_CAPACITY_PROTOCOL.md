# R-01 synthetic map capacity protocol

Authorized workload (2026-10-28): 100,000, 500,000 and 1,000,000 listings;
10 source providers; 20 facts/listing; 50, 100 and 200 concurrent map requests;
p95 <= 500 ms and p99 <= 1,000 ms. Only synthetic data in isolated infrastructure.

## Architectural meaning

A fact is one row of `ai_listing_facts`: a typed observation, scope, status,
origin and exact evidence span belonging to a source-generation batch. It is
not a free-form JSON field, a filter, or an independently queried listing.
The resolver publishes `ai_listing_search_features`; a proof additionally binds
that projection to current canonical data, source identities, batches and facts.
There are 21 key families, at most 1,024 observations from 128 source records,
and at most 128 resolved features per listing.

The baseline distributes 20 distinct compatible observations across two source
records per listing, selected from ten synthetic providers. This preserves 20
observations total rather than silently multiplying them by ten. The fixture
uses all key families except availability; its query has one broad hard pets
criterion, exercising the full proof digest while keeping candidate selectivity
low. A separate ten-source-record profile splits the same 20 observations two
per record to investigate source fan-out. It is an additional stress profile,
not a claim that every real listing has ten independent source records.

Rows are generated from a template published and verified by the actual
`FactPipeline.complete` and `QueryProofs.prepare` implementations. The writer
replaces extractor fact IDs, so bulk fixture provenance maps the persisted IDs.
Bulk SQL recomputes source snapshot hashes and the exact canonical JSON input
manifest. Sampled first/middle/last rows must pass the actual Python verifier
before measurements are accepted. The template remains outside measured bounds.

Bulk proof preparation uses an equivalent indexable UNION of current/known
source IDs to avoid spending the whole experiment on the identified quadratic
setup path. Sampled digests must equal the production expression exactly.
**Measured queries always call the unmodified production map implementation.**
No preparation-time optimization is applied to the map, its predicates or its
plans. This distinction is necessary when interpreting setup timings.

Bulk setup uses four disjoint writers. The existing per-row listing trigger
updates a single catalog-version row and serializes concurrent bulk inserts.
Only in this disposable fixture phase, suspend that one trigger, then restore
it in a finally block and advance the catalog version by the inserted-row count.
Every measurement refuses to run unless the trigger is enabled. All FK/check
constraints, application indexes and the trigger remain present. No trigger is
changed in application code or in any application database. Fixture creation
throughput is not a measurement of real importer throughput.

## Isolation and resources

Use a fresh PostGIS 16/3.4 container pinned to the same digest as integration CI,
an internal Docker network with no outside route, and no published DB ports.
The benchmark hardcodes a synthetic-only DB identity and requires an explicit
lab marker. The launcher verifies the task label, internal network and absent
port bindings. The source mount is read-only; only the results directory is
writable. No project .env, credentials, application DB, providers, ASR, workers,
crawlers, public endpoints, notification or deployment are used.

The DB has 8 CPU quota, 8 GiB RAM, 1 GiB shared buffers, 4 MiB work_mem and 260
max connections. The driver has 2 CPU quota and 2 GiB RAM. Report the actual
machine, Docker/kernel/PostgreSQL/PostGIS versions and image digest with results.
Existing unrelated containers are not queried or stopped. Resource samples are
taken only from this experiment's DB container. These are lab limits, not
production hardware or recommendations for production configuration.

## Measurement and interpretation

The repository `_map_intent` path includes actual SQL and marker/cluster DTO
construction. It excludes HTTP/TLS/rate gate and subject/session lookups;
therefore a passing result alone would not certify end-to-end API latency.
Transactions use repeatable-read/read-only. The client has the application's
30-connection ceiling (10 base + 20 overflow); it preallocates that ceiling to
avoid confusing connection establishment with SQL work. Measure 50/100/200
simultaneous client operations, including pool waiting, in separate scenarios.
Pool wait is separately retained on successful operations. This does not assert
that PostgreSQL executes 200 statements simultaneously.

For each scale, capture single-request results and exact emitted SQL plans at
zoom 8/12/13/21 with 0/299/300/301/302, 10,000 and whole-catalog candidates.
Coordinates use a deterministic dense 1,000-column grid, not sampled real
geography. All sources/projections are active and valid: this is a deliberately
broad aggregation workload. Successful counts and marker/cluster transitions
must match the known fixture. Existing dense functional regressions separately
cover hidden, stale and missing-proof cases; they are not load evidence.

Capture `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` for each actual emitted
statement, including the high-zoom probe and aggregation. If execution exceeds
the lab's 5-second SQL cap, retain the timeout and an explicitly estimated-only
plan. The actual application default is 60 seconds; the shorter experimental
cap bounds resource use after the 1-second target is already exceeded. A timeout
is a failed sample, never a successful 5-second response or a measured true
latency percentile for that unfinished query.

Load scenarios request up to 200 attempts each, zoom 8/13, and
300/10,000/whole-catalog viewports. At 100,000, run the full 200 attempts. At
500,000 and 1,000,000, stop a scenario after its first full concurrency wave
if every attempt failed: that already rejects the target, and avoids repeated
resource saturation with no successful latency samples. Record requested and
actual sample counts and the early-stop flag. Retain every attempt and failure.
Nearest-rank p50/p95/p99 describe
observed completion/error durations including queue time. Error-containing
scenarios fail acceptance regardless of these quantiles. With 200 attempts,
p99 is an exploratory tail estimate, insufficient for high-confidence passing
certification; already large failures can still reject the target. This is
closed-loop load and does not characterize open-loop overload/coordinated
omission. The maximum effective concurrency is min(requested concurrency,
attempt count). No one-sample preflight is presented as a load test.

The first touch after data preparation is not an OS-cold measurement: preparation
and VACUUM have warmed caches. Do not evict shared host caches or label these
results cold. Record cancellation completion and verify no query from the
benchmark application remains active. Save versioned JSON plans, attempts,
dataset counts/size/settings, container resource samples and a findings report.

## Invocation

Create the labelled internal network and fresh DB exactly as recorded in the
experiment report. From a clean source checkout with no .env:

```powershell
./scripts/run-ai-map-benchmark.ps1 -Phase initialize
./scripts/run-ai-map-benchmark.ps1 -Phase seed -Total 100000
./scripts/run-ai-map-benchmark.ps1 -Phase measure -Total 100000 -Samples 200
# Grow the same synthetic catalog, analyze and repeat at 500000 and 1000000.
```

The private runner resolves the local `ttest-backend:latest` dependency image
once, pins its immutable ID in the results directory and uses that ID for later
phases while importing all project code from the read-only checkout. Record
that image ID; do not infer its dependency versions from the tag. Running
this protocol does not approve an activation or a production configuration.
