# One-job offline fact runner

Date: 2026-10-26. Branch: `codex/ai-offline-fact-worker`.
Stacked base: [offline bridge #382](https://github.com/antony502189-max/Ttest/pull/382),
`c9fab1846b9480a51e2a9ade78e76282467c03e5`, above unmerged #381/#380.
#382 final-head CI is all three workflows completed/success: dedicated facts/bridge,
Security and Payment. Dedicated CI: 236 focused, 1004 backend unit / 7 environment
skips, full PG16/PostGIS migration chain and schema check. These are synthetic merge
ref checks, not actual merges. Current main underneath is payment #372 `1292c680`.

The owner asked to continue the offline work and then create a new project chat
explaining human review of #373. This increment finishes the explicit one-job seam;
it does not supply a daemon, production minimizer or any paid provider integration.

## Implemented

`OfflineFactJobRunner.run_once` explicitly processes at most one claimed job:

1. Claim only its configured extractor version using the existing PostgreSQL
   lease/fence/attempt machinery. Other versions remain pending/unattempted; the
   previous unfiltered `FactPipeline.claim()` behavior remains compatible.
2. Capture the current stored source through the bounded reader, release the DB
   connection, invoke the required injected sanitized builder and strict bridge.
3. Bind all prepared input fields to the original claim, then submit the batch to
   AI-04's atomic fact/projection/revision/event/receipt transaction.
4. Return only typed metadata: no_claim, succeeded, retry_scheduled, failed or stale;
   fixed failure codes, job UUID and optional durable receipt. No raw errors/text.

Unsupported/invalid input is a permanent `INVALID_RESULT`, not an unlimited retry.
Builder errors use `EXTRACTOR_FAILED`; retry is a required explicit boolean policy
with no production default and stays within AI-04's persisted delay/attempt limits.
Before rejecting input the runner reconciles the canonical state. A changed/retired
source may supersede the old claim; the runner never overwrites its successor's
state. Complete's authoritative checks still handle changes after capture/build.

Lease/fence loss returns stale without facts. Cancellation propagates, leaving the
durable lease for bounded offline crash recovery. SQLAlchemy failures are redacted
as `OFFLINE_FACT_STORAGE_UNAVAILABLE`; they do not trigger a second inference or a
fabricated failure/success receipt. In particular, if commit succeeded but its ack
was lost, another run sees no eligible job and does not invoke the builder twice.

There is no loop, scheduler, command, environment activation flag, provider client,
network default, public endpoint or notification consumer. A caller must explicitly
construct a pipeline, bounded reader, exact extractor version, mapping, builder and
retry policy. Tests use only handwritten fixture builders on disposable data. A
future real builder remains subject to BASE-373 human review/port, source/scope/
vocabulary/minimization and privacy/retention review. Hashes do not prove PII absence
or natural-language truth. No real-content ingestion/paid call is authorized here.

`no_claim` means this attempt did not claim a matching eligible job; it is not a
global queue-exhaustion signal (another version or cleanup candidate can remain).
The listing guard remains partial publication/deletion only. Existing moderation,
price, user restriction, TOP/cards, session/quota and signed cursor integration
still belong to AI-09, not to this background fact receipt.

## Verification and rollback

New PG cases exercise success/no-claim, eight concurrent runners with one builder
invocation, version isolation, explicit retry/no-retry and attempt exhaustion,
permanent packet rejection, changed payload/retirement/hidden listing, source row
lock release during building, late source mutation, cancellation/recovery, actual
storage rollback, commit-ack ambiguity without second builder, and lease expiry.
Separate unit cases check strict version/retry configuration.

Local final code (Python 3.14.4 / owned disposable PG18.6): **254 focused passed**:
164 unit + 90 PG cases. Incremental runner coverage is **3 unit + 15 real PG**;
all 236 prior focused cases remain included. Complete backend unit:
**999 passed, 15 platform/opt-in skipped, 403 integration deselected**; focused
unit cases are included in 999. Ruff app/tests, mypy 124 modules, pip check,
migration compatibility/supply-chain and diff checks passed. No new schema or
ORM drift. Zero temporary test schemas remained; the owned cluster was stopped.
Final-head CI is recorded in the PR; ignored JUnit is in
`output/offline-worker-focused-local.xml` and `output/offline-worker-unit-local.xml`.
Full historical PG16/PostGIS chain remains a CI result: local PG18.6 has no PostGIS.
No production coverage, source quality, live freshness, cost or 10s SLO is asserted.

No migration/schema change is added. Rollback removes this unconnected runner and
optional version filter; durable history remains. Importer, search, cards/TOP,
Stripe, map/gallery and notification behavior is unchanged. No live catalog/DB,
provider, crawling/backfill, staging, main merge or deploy operation occurred.
Keys are still unnecessary. The separate human-review guide will be explained in
the new project chat; no AI approval is submitted or passed off as human review.
