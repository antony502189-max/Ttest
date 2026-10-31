# R-01 synthetic map capacity protocol

Current evidence version: `r01-capacity.v2` (2026-10-29). Earlier artifacts remain
historical and cannot be certified under this version without new measurements.

The summarizer reports separate `dataset_file_present`, `seed_attested`
(`dataset_complete` is its alias), `load_complete`, `baseline_attested`,
`plans_attested`, `resource_attested`, `dataset_stable`, `protocol_complete` and
`slo_passed`. A scale completes the protocol only when every attestation passes.
Global COMPLETE additionally requires all three scales and no inconsistent
evidence. The summary CLI exits nonzero for both INCOMPLETE and INCONSISTENT;
it still writes a reviewable JSON/Markdown report. `load_completed_scales` never
substitutes for protocol-complete scales. A completed protocol can fail every SLO.

Authorized workload (2026-10-28): 100,000, 500,000 and 1,000,000 listings;
10 source providers; 20 facts/listing; 50, 100 and 200 concurrent map requests;
p95 <= 500 ms and p99 <= 1,000 ms. Only synthetic data in isolated infrastructure.

The owner subsequently stopped the large experiment and requested fixing the
identified SQL first. Historical 100k/500k raw attempts are retained, but their
provenance and actual cancellations cannot be certified retroactively; 1m setup
was interrupted at 900k and no 1m load measurement exists. Do not restart that
large workload as part of the SQL correction. The application now selects
authority IDs with the same indexed UNION used by the fixture optimization;
the historical timings describe the earlier OR expression. Validate correctness
with small regressions and agree a lighter workload separately.

On 2026-10-30 the owner explicitly authorized a new isolated baseline run at
100k/500k/1m with the resources below. This later approval is recorded in
[post-merge remediation](../post-merge-remediation.md). It permits fresh synthetic
labs; it does not permit reuse of the historical DB or public AI activation.

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
low. The optional ten-source-record profile splits the same 20 observations
two per record to investigate source fan-out. It was not run after the owner
stopped the experiment. It is not a claim that every real listing has ten
independent source records.

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

Bulk setup uses disjoint writers (four at 500,000, eight for the final
1,000,000 setup); this is separate from timed map concurrency. The existing per-row listing trigger
updates a single catalog-version row and serializes concurrent bulk inserts.
Only in this disposable fixture phase, suspend that one trigger, then restore
it in a finally block and advance the catalog version by the inserted-row count.
Every measurement refuses to run unless the trigger is enabled. All FK/check
constraints, application indexes and the trigger remain present. No trigger is
changed in application code or in any application database. Fixture creation
throughput is not a measurement of real importer throughput.

From source `ea333e15` the new live-proof/population fixture uses one writer
for both input and proof setup. Eight writers contended on transactional
population counters before any 100k measurement. Only setup was serialized;
the measured 50/100/200 concurrency, pool 30, deadlines and SLO are unchanged.
The failed setup remains historical; fresh experiment
`3056bd59405546c984354b07f2382a1f` completed 100k with SLO FAIL. Its larger
scales are deferred until the next optimization, not silently counted as done.
[Result and evidence](../../reports/AI_LIVE_INPUTS_20261031.md).

## Isolation and resources

Use a fresh PostGIS 16/3.4 container pinned to the same digest as integration CI,
an internal Docker network with no outside route, and no published DB ports.
The benchmark hardcodes a synthetic-only DB identity and requires an explicit
lab marker. The launcher verifies the task label, absent port bindings, exclusive
membership in the exact internal network, the `r01-db` alias, running container
ID and pinned PostGIS image ID. A read-only identity query inside that exact
container checks the synthetic role/database and PostgreSQL/PostGIS versions.
Python repeats the DB/version check before migrations or fixture writes.
The runner uses the inspected network ID and pins r01-db in /etc/hosts to that
container's inspected IP, so another container's DNS alias cannot redirect DDL.
An OS file lock records the owner run/PID and excludes concurrent phases writing
the same experiment directory; it is released automatically on process exit.
A database-wide advisory lock excludes initialize/seed/measure even across
different output directories. Initialize uses an AUTOCOMMIT session lock so
concurrent-index migrations do not wait for its own old transaction snapshot;
seed and measure use transaction locks in the same lock namespace.
During measure a dedicated transaction
holds SHARE locks on every lab-schema table before preflight until all queries
and pool cleanup finish. SELECT remains allowed; ordinary DML, TRUNCATE and DDL
are blocked, including writers that ignore the advisory lock. A concurrent
writer already holding a conflicting lock aborts preflight via NOWAIT. Every
seed advances r01_meta.generation; dataset/proof metadata and a final stability
artifact must attest the same generation before and after the frozen interval.
The source mount is read-only; only the results directory is
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
The retained `pool_ms` is time until the read-only transaction is established:
checkout plus one SET TRANSACTION round trip, not an exact pool-only timer.
`query_ms` includes repository SQL/DTO work and error cleanup, not server-only
execution time; EXPLAIN is the separate server-time evidence. This does not assert
that PostgreSQL executes 200 statements simultaneously.

For each scale, capture single-request results and exact emitted SQL plans at
zoom 8/12/13/21 with 0/299/300/301/302, 10,000 and whole-catalog candidates.
This deduplicated baseline matrix is mandatory for protocol completion. Every
record retains first-touch timing/outcome, capture_count/query_count/plan_count
and the ordered explicit SQL dispatch trace, including transaction control.
Only our explicitly marked SET TRANSACTION is transaction control; CTEs,
comments and other query text are never filtered. The historical map executed
one SQL query, or two for high zoom above 300 candidates. The new
`single-pass-jit.v1` trace requires exactly SET TRANSACTION, one explicitly
marked `SET LOCAL jit = off` configuration dispatch, and one map SQL query at
every zoom/count. Configuration time stays inside measured query/total time.
The single materialized eligible set feeds either markers or aggregation;
all proof/currentness/eligibility guards remain before count and rendering.
EXPLAIN uses the identical transaction-local JIT setting and records it in its
artifact. Missing/changed/extra configuration or map SQL rejects attestation.
Historical evidence remains checked against its original two-query contract.
Each query references a unique plan artifact with matching SQL SHA-256, binds,
scenario and run identity. Actual and explicitly estimated-only plans are valid
evidence; missing, malformed or failed plans prevent protocol completion.
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
If both actual and estimated EXPLAIN fail, retain both diagnostic errors and a
failed plan artifact, then continue gathering load evidence. The phase finishing
does not certify missing plans. Raw attempts require finite nonnegative timings,
success pool/query durations and count/items, or an error type and diagnostic
detail with a valid optional SQLSTATE. Scenario seconds and individual durations
must agree with their UTC intervals within max(5 ms, 1%); inconsistent fields
are reported and never accepted as complete.

Full load scenarios request exactly 200 attempts each, zoom 8/13, and
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
attempt count). Fewer than 200 requested attempts are labelled `probe` and never
complete the protocol. Raw attempt start/end timestamps must demonstrate the
declared client concurrency; this includes pool waiting. No one-sample preflight
is presented as a load test. Summary recomputes p50/p95/p99, samples, failures,
early-stop metadata and pass from raw attempts. Contradictory stored aggregates
produce INCONSISTENT and a nonzero summary CLI exit code.

The first touch after data preparation is not an OS-cold measurement: preparation
and VACUUM have warmed caches. Do not evict shared host caches or label these
results cold. Cancellation uses twenty controlled `pg_sleep(4)` operations, with
a server-side `pg_stat_activity` barrier confirming all twenty are actively
sleeping before cancellation. Retain requested/accepted/confirmed cancellations,
completed-before-cancel and failed counts. All twenty must actually be cancelled,
none may finish early or fail, no tagged SQL may remain active, and an actual map
request must confirm pool reuse. Save versioned JSON plans, attempts,
dataset counts/size/settings, container resource samples and a findings report.

## Historical invocation — stopped; separate approval required to resume

The commands below document the original experiment. They must not be run
again without the owner's separate explicit approval. Current review is limited
to small disposable regressions and ordinary CI. The runner rejects a missing
lab marker, any non-test environment or a DATABASE_URL different from its fixed
synthetic DSN before Alembic, including direct invocation. For an explicitly
approved fanout run, the resource monitor must also receive `-Profile fanout`.

Create the labelled internal network and fresh DB exactly as recorded in the
experiment report. From a clean source checkout with no .env:

```powershell
$experiment = [guid]::NewGuid().ToString('N')
./scripts/run-ai-map-benchmark.ps1 -Phase initialize -ExperimentId $experiment
./scripts/run-ai-map-benchmark.ps1 -Phase seed -Total 100000 -ExperimentId $experiment
$run = [guid]::NewGuid().ToString('N')
# Start the monitor in another terminal before measure; stop it after measure:
# ./scripts/monitor-ai-map.ps1 -OutputDirectory ./output/r01/$experiment -RunId $run
./scripts/run-ai-map-benchmark.ps1 -Phase measure -Total 100000 -Samples 200 -ExperimentId $experiment -RunId $run
# New-Item ./output/r01/$experiment/monitor.stop
# Wait for the monitor to stop; remove monitor.stop before monitoring another run.
# Grow the same synthetic catalog, analyze and repeat at 500000 and 1000000.
```

The private runner resolves the local `ttest-backend:latest` dependency image
for each invocation and verifies its immutable ID against experiment.json for
later phases while importing all project code from the read-only snapshot. Record
that image ID; do not infer its dependency versions from the tag. Running
this protocol does not approve an activation or a production configuration.

## Toolchain review corrections (2026-10-29)

The launcher rejects staged, unstaged and untracked checkout changes before
Docker. It exports the selected commit with `git archive`, mounts that separate
snapshot read-only, and records the commit, `checkout_clean`, source mode and
archive SHA-256 in runner metadata. Ignored files and subsequent checkout edits
are excluded from execution. Git, archive extraction and Docker inspection
failures stop the launcher. Python refuses missing archived-source provenance.
Every experiment has a separate output/r01[-fanout]/<experiment-id> directory.
Its immutable experiment.json binds commit, archive SHA-256, runner/DB image IDs,
DB container ID, profile and seed ID; the DB's r01_meta stores the same identity.
Changes require a fresh experiment and disposable DB seed. Unique phase-run
manifests are atomically written with running/complete state and time boundaries;
raw artifacts carry the same provenance and phase run ID. Incomplete phases,
mixed load/cancellation runs and missing/legacy provenance cannot certify completion.

Both entry points reject invalid numeric input before infrastructure actions:
total1..1,000,000, samples1..200, candidate0..total. Candidate and BaselineOnly
require measure; a candidate-specific probe requires BaselineOnly because the
load phase always executes its full matrix. These bounds do not authorize large
runs. The owner's stop instruction remains in force.
`--sources` is only accepted for initialize. Later phases derive the active
profile from the immutable experiment, and the launcher checks -Profile against it.
Before the first timed request, a repeatable-read, read-only transaction validates
exact entity, listing, room, external source, fact catalog, batch, fact source,
observation, projection and proof counts, provider count, template/dataset/profile
metadata, DB seed provenance and restored trigger. A mismatch emits no load files.

Reports derive source/observation counts from dataset metadata. For older
archives without explicit profile fields, exact row-count ratios identify the
profile; ambiguous or inconsistent counts are rejected. A template contributes
2 or10 sources and20 observations, so fanout subtraction and prose reflect10
sources rather than a hardcoded baseline. The raw historical archive is unchanged.

Load completion requires every expected load scenario, 200 requested
attempts with demonstrated concurrency (or the fully failed first-wave exception),
matching raw/derived counts and immutable phase provenance, and a
successful cancellation/pool-reuse check. Completed dataset creation alone is
insufficient. COMPLETE describes protocol completion, not a passing latency SLO.
Full protocol completion also requires the entire baseline/plan matrix, a frozen
unchanged seed and complete resource coverage. Stop-marker claims are compared with these files and produce INCONSISTENT when
they disagree; otherwise partial histories are INCOMPLETE.

The monitor validates container name/task label/network and any existing output
template against baseline/fanout before collecting samples. It writes start,
sample, error and stop events to resources.jsonl, with sanitized error categories.
After three consecutive failures by default it exits nonzero; a recovery resets
that counter. Reports expose missing/degraded/unknown/complete resource quality,
including malformed records, observed gaps and mixed profiles/containers. Each
row also binds experiment, DB container ID, phase run ID and unique monitor ID.
Every scenario must be inside one correctly paired lifecycle with bracketing
valid samples and no gaps/errors. Quality is reported per scenario and scale;
old monitoring cannot certify a new load. Legacy archives have unverified
provenance and cannot be marked complete under the current protocol.
One measured run must have exactly one paired monitor lifecycle. Extra/unpaired
lifecycles, errors, gaps or malformed resource rows also prevent global COMPLETE.

The small full-schema map regression exercises actual plans for 32/128/300/301
matching candidates at zoom 8/13, with 2,048 unrelated sources. It records node
types, total loops/visited rows/buffer touches and execution duration, and bounds
authority work by candidate count. This is a deterministic functional regression
covering the marker/probe/cluster paths, not a capacity or p95/p99 measurement.

Small toolchain regressions use fake Docker and temporary Git repositories,
including real PowerShell execution when pwsh/PowerShell is installed. They do
not start the synthetic lab. Run `python -m pytest -q
backend/tests/test_ai_map_toolchain.py backend/tests/test_ai_map_benchmark_safety.py`.

## Instrumentation corrections (2026-10-30)

Seed ANALYZE/VACUUM waits up to60s for maintenance locks and restores the1s query
lock timeout even on failure. The untimed repeatable-read/read-only dataset
preflight uses SET LOCAL statement_timeout60s: counting20m fixture facts must
not inherit the timed-query deadline5s. Closing that transaction restores the
engine setting; timed map queries and SLO thresholds are unchanged.

Attempt/phase timestamps and resource events use a UTC anchor captured at process
start plus monotonic elapsed time, so a wall-clock correction cannot invert or
shorten a measured interval. Raw wall-clock fields are retained separately.
The orchestrator brackets the final manifest timestamp with resource samples.
Raw consistency checks remain strict; older evidence with inconsistent clocks
is rejected and preserved. Any source change requires a fresh experiment/DB.
