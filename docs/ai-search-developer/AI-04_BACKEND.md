# AI-04 — durable offline fact queue and source resolver

Date: 2026-10-26. Branch: `codex/ai-04-facts-queue`.
Stacked base: [AI-03 #380](https://github.com/antony502189-max/Ttest/pull/380),
`a5f4705a7b08de0cc901af1c43713cbe170f059c`; main underneath remains
`1292c6807ece59999238bb31c80e09ef7e2c3212`, including payment #372.
AI-03 is not merged. Review this delta separately from facts storage and quota/
sessions #378/#379. The owner's continued-backend authorization covers this offline
increment; it does not authorize live data, provider calls, merge or deployment.

References: [Product](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/01_PRODUCT_SPEC.md),
[TZ](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/10_IMPLEMENTATION_TZ.md),
[AI-01 proposed ADR](https://github.com/antony502189-max/Ttest/blob/d46c44ee62aa89e0ac312e69d754aca9594f96d8/docs/ai-search-developer/adr/AI-01_CONTRACTS.md),
[AI-03 storage boundaries](AI-03_BACKEND.md).

## Actual code

- Expand-only `0070_ai_fact_pipeline` over `0069_ai_listing_facts`: registered
  canonical revision anchors, current source generations, durable jobs and immutable
  rematch signals. Internal FKs only; no new FK or mutation to legacy listing/source
  tables. Downgrade preserves all new data.
- `FactPipeline.observe` takes a strict server-owned source identity, sanitized
  input hash, expected snapshot token and extraction versions. Under a canonical anchor and existing row
  locks it verifies the real `Listing` / `ExternalListingSource` selected fields,
  rejects implicit canonical reassignment, advances generation only when input/
  fingerprint/status/version changes, supersedes old active jobs, and enqueues once.
  A new sanitized hash advances generation even when the legacy fingerprint did
  not change; the #373 freshness bug cannot be bypassed by trusting that digest alone.
- A separate coarse SHA-256 token is computed inside PostgreSQL over stored raw/
  normalized JSON, source price text and routing identity. Only the digest returns
  to Python or enters queue metadata; no raw payload is copied. Enqueue rejects an
  expected token captured before a concurrent snapshot change. Finalize/reconcile
  compare the current token even if the legacy fingerprint was never updated.
  This CAS token is not sanitized content or approval to send source data. The
  future server input builder must derive the input hash and expected token from
  the same stored snapshot. Hashing unselected fields may conservatively trigger
  extra invalidations; its production SQL cost has not been measured.
- `claim` uses PostgreSQL `FOR UPDATE SKIP LOCKED`, DB time, monotonic fencing and
  explicit retry/lease/attempt policy. A returned claim holds no session/connection.
  Expired offline work can be reclaimed within the attempt budget. `fail` persists
  a bounded reason code and retry delay or terminal failure, never raw error text.
  Claim inspects one eligible candidate: `None` can also mean that this candidate
  was terminally cleaned up; callers must not infer global queue exhaustion.
- `complete` validates a copied strict batch, all server vocabulary allowlists,
  exact sanitized spans/hash and claim-bound input. Existing canonical/source,
  current fingerprint/status, shadow generation/hash and DB lease/fence are checked
  again under locks. Missing/retired/remapped sources or hidden/deleted listings
  cannot publish old results. Server assigns batch/fact identities and authoritative
  observation/check/content times; extractor-supplied identity/freshness is not
  publication authority. Receipt hashes bind normalized fact output, independent
  of caller-chosen fact UUIDs/order.
- Facts, current batch pointer, canonical projection, monotonic revision, rematch
  event and successful job receipt commit in one PG transaction. A final DB-clock
  check uses the stored lease deadline after writes; even a forged future deadline
  in the returned claim cannot extend it. Any late expiry/storage failure rolls
  everything back. Same terminal output replays its original receipt without a
  second publication; different output raises `FactResultConflict`.
- `reconcile_listing` rechecks current source identity/status/fingerprint, cancels
  obsolete active jobs, repairs a missing job for a prepared current generation
  and recomputes the projection idempotently. `reconcile(limit, after)` pages only
  registered canonical anchors using a bounded UUID cursor. It does not discover
  or hash the production catalog, invent source inputs, or reopen exhausted jobs.

## Conservative source-only resolution

Only current ready batches of active external sources participate. Ingested
native/owner facts are deliberately unsupported here: owner precedence is still
pending review. No origin/confidence/latest-timestamp override is introduced.

- Equal explicit values in the same key/scope aggregate their supporting IDs.
  Equal-authority contradictory values produce `conflict` with no winning value.
  Unknown/legacy defaults do not outvote actual explicit evidence.
- Conditional observations remain unresolved. Differently qualified overlapping
  rules produce an unresolved conditional projection rather than a blanket permit.
  Explicit dog/cat and known size scopes can be disjoint; indoor smoking differs
  from balcony/terrace, while broad outdoors may overlap them. Counts/approval and
  unknown tenant-group relationships are treated conservatively. No price-period
  conversion, capacity arithmetic, owner override or search ranking is inferred.
- AI-03's structural support check now permits cross-scope IDs only for unresolved
  `conditional`/`conflict` diagnostics of the same key. Explicit features still
  require identical scopes, equal explicit values and active supporting batches.
- A current active source with missing/stale/invalid/unsupported extraction puts
  the entire canonical projection behind a pending barrier (`features=[]`). This
  proposed offline safety choice prevents temporarily ignoring a possible denial
  while another source is still being processed. It reduces coverage; it is not a
  claimed production UX rule. Inactive sources are excluded; another ready active
  source can still support the listing after retirement.
- Input identity includes all source descriptors, readiness/publication guard,
  extraction/schema/taxonomy versions, coarse snapshot token, resolver version and a deterministic hash
  of the required vocabulary. A change emits one durable signal per new canonical
  revision. Revision never decreases even if AI-03 already contained a projection.

Reviewable engineering bounds: at most 128 source identities and 1024 observations
per canonical resolution; AI-03 retains its 128 features and 128 supporting IDs/
feature limits. Reads stop at explicit bounds; excess/invalid input cannot broaden
matching. Sanitized input mappings are ephemeral, at most 256 string entries/
1 MiB. Lease, retry delay and max attempts have no production defaults; tests use
60s/1s/2, with a separate 1s expiry fixture. No retention/GC or source-age TTL exists.

## Integration and remaining gates

This is real backend repository/ORM/migration code exercised on disposable PG,
with a handwritten fake extractor in tests. There is no importer hook, hash/input
builder port, CLI daemon, scheduler, provider client, public endpoint or activated
worker. Source packets must be rebuilt through the reviewed #373 bridge/minimizer;
the `SourceInput` hash is trusted only from that future server-owned boundary.
Minimal code that manipulates source metadata is not privacy approval.

Lock order for mutations is AI canonical anchor -> existing listing -> existing
source rows ordered by UUID -> AI source state -> job. Claim/failure lock one job
only. BASE-373/current importer transaction ordering must be reviewed before live
concurrent activation; no assertion of production deadlock/throughput evidence is
made. Canonical remap currently fails closed and requires a separate reviewed
move/reconciliation workflow. Real-content persistence, source discovery/backfill
and production retention/TTL require their own approvals and DB measurements.

The listing guard here checks publication/deletion only. It is not the complete
existing user/moderation/restriction/price eligibility query. AI-09 must reuse all
current visibility and TOP/card policies, enforce verified hard predicates before
count/order/seek/limit, bind cursor versions and revalidate source/projection state.
Without importer hooks, invalidation happens only when these explicit methods are
called; no claim of instant live-catalog invalidation is made. Terminal receipt
replay returns metadata and does not refresh/reinstate old facts or return cards.

The rematch table is a durable signal, not an email/alert delivery implementation.
AI-10 still needs current saved-filter/ownership checks, delivery/outbox handling
and notification dedup. No background notification is sent here. API keys are not
needed until separately approved provider integration.

## Verification and rollback

Focused tests apply the actual 0069+0070 migrations to fresh random schemas in this
chat's own loopback PG18.6 cluster. Queue tests use clearly synthetic minimal legacy
tables for the selected `Listing`/`ExternalListingSource` columns; they exercise the
actual asynchronous repository and real SQL locks, constraints and transactions.
Full historical PG16/PostGIS migrations and `alembic check` are separate required
CI steps. No full historical PostGIS chain was run locally.

Coverage includes 12-way observe/claim races, pending barriers, equal/conflicting/
scoped rules, source updates without legacy fingerprint change, delete/retire/
canonical remap, hidden/deleted listing, source-vs-complete race, lease/fence crash
recovery, lock wait expiry, late lease rollback even with a forged claim deadline,
retry delay/attempt exhaustion, malformed/unsupported facts, no duplicate replay/
rematch, resolver-version change, missing-job repair, existing revisions and
non-destructive downgrade. Fake patches/quotes prove transaction behavior, not LLM
quality, actual source coverage, freshness, latency, cost or the browser 10s SLO.

Local final code (Python 3.14.4 / disposable PG18.6): **172 focused passed**:
111 DTO/resolver unit cases and 61 real PostgreSQL cases. The AI-04 increment
adds 18 unit + 33 PG cases; the 121 original AI-03 cases remain included.
Full backend unit: **946 passed, 15 platform/opt-in skipped, 374 integration
deselected**; the 111 focused unit cases are included in 946, not additional.
Ruff app/tests, mypy 120 modules, pip check, immutable/expand-compatible migration
history, supply-chain pins and diff checks passed. All seven new AI tables have
no ORM/migration differences. The temporary cluster was stopped with zero
remaining test schemas. Final-head CI evidence is recorded in the PR. Ignored JUnit:
`output/ai04-focused-local.xml`, `output/ai04-unit-local.xml`. The original AI-03
cases remain included; report incremental and combined totals separately.

Rollback stops use of these unconnected components and reverts the binary; new
queue/fact/revision history remains. No legacy importer/search/cards/TOP/Stripe/
map/gallery/notification behavior is changed. No production DB, live data, outbound
API, paid call, crawling/backfill, staging, merge or deployment was performed.
The single linear migration chain remains independent of unmerged quota/session
revisions and must be reconciled before eventual integration, as AI-03 documents.
