# AI-03 — inert facts storage and search projection

Date: 2026-10-26. Branch: `codex/ai-03-facts`. Independent base: current main
`1292c6807ece59999238bb31c80e09ef7e2c3212`, including payment #372.
This is a reviewable schema/DTO increment, not completion of the facts pipeline.

The owner authorized continued backend work. References:
[Product](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/01_PRODUCT_SPEC.md),
[implementation TZ](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/10_IMPLEMENTATION_TZ.md),
[plan](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/05_IMPLEMENTATION_PLAN.md),
[proposed AI-01 ADR](https://github.com/antony502189-max/Ttest/blob/d46c44ee62aa89e0ac312e69d754aca9594f96d8/docs/ai-search-developer/adr/AI-01_CONTRACTS.md).
No GitHub approval, merge, rollout or unresolved business decision is implied.

## Implemented

- Expand-only migration `0069_ai_listing_facts`, parent `0066_complimentary_ads`.
  Three registered tables: `ai_listing_fact_batches`, `ai_listing_facts`,
  `ai_listing_search_features`. No alterations/backfill of existing tables.
- A batch identifies canonical listing, optional external source record, explicit
  generation, sanitized-input hash, schema/taxonomy/extractor, observation time
  and source-state snapshot. Last successful check, last content change and last
  check error are separate. Refreshing a check does not mutate content-change time.
- Observations retain per-key typed value, status, typed qualifiers, origin and
  bounded evidence spans. Negative quotes are preserved exactly. Spans use Python
  Unicode character offsets in the sanitized mapping, not raw HTML/byte offsets.
  Structured spans retain a named `provider_field`; text cannot claim owner-form
  evidence. Null source is representable only for explicit owner observations.
- Strict DTOs cover all 21 AI-01 fact keys. Policies differ from confirmed values:
  numeric/money/category/date/boolean facts cannot use policy `explicit_deny`.
  Unknown/conflict/legacy carry no winning value; defaults never acquire evidence.
  Conditional permissions remain conditional. Capacity has explicit rented-unit
  scope; deposit whole months and one-off EUR remain distinct; no currency/period
  conversion or inference of available capacity from legacy `room_capacity`.
- A canonical projection stores revision, resolver/input/schema/taxonomy versions,
  computation time and bounded typed features with supporting observation IDs.
  Structural validation rejects cross-listing/key/scope references, inverted
  explicit values and inactive/uncertain evidence promoted to explicit features.
  This validator does not choose authority, resolve conflicts or prove a generation
  is current. AI-04 must do that transactionally before publication of a projection.
- Required server-supplied `FactVocabulary` allowlists validate custom catalog,
  amenity, tenant-group and municipality-zone codes. Tests use synthetic mappings;
  there is no approved real-catalog mapping or permissive production default.
- DB checks enforce basic versions/enums, hashes, positive revisions/generation,
  value/status nullability, JSON shapes and storage bounds. The complete tagged
  key/value/qualifier/evidence contract is validated by Pydantic, not by arbitrary
  SQL inserts. No production writer/reader is introduced in this PR.

## Proposed engineering choices and integration boundaries

These storage choices are submitted for review, not approved product policy:
`ai-facts.v1` with `ai-search.v1` taxonomy; 128 observations/features, 16 spans per
observation, 512 characters/span; person/stay quantities bounded by signed PG int;
128 supporting IDs/feature and 512 KiB projection JSON. Individual JSON values,
qualifiers and evidence have additional DB byte bounds. DTOs reject coercion,
unknown fields/versions, fractional months, invalid INE relationships and dates.
An unknown scoped key still names its scope; it does not assert a value.

Projection features use JSONB in this first storage increment. Only identity,
source-generation and canonical-listing lookup indexes are installed. There is
no claim of indexed hard-filter retrieval, production query plans or tuned GIN/
expression indexes. AI-02 authorized DB measurements inform the later AI-09 index
and SQL shape; filtering must eventually precede count/order/seek/limit.

No new FKs point into existing listing/source tables, so legacy import/deletion
paths cannot become blocked by AI history. The internal fact-to-batch FK protects
batch membership. Supporting IDs inside projection JSON are not DB FKs. AI-04
must validate current canonical/source association, ownership authority, retirement,
input generation/hash and all references under its transaction/locks, publish
projection+revision+outbox atomically, and ignore stale/deleted sources on reads.
An observation source-state snapshot alone is never a live eligibility decision.
`scope_hash` identifies the complete qualifier object; equality is not proof that
different scopes do not overlap. Resolver/matcher must compare semantic species,
size/count, smoking and approval conditions, not treat distinct hashes as disjoint.

Batch uniqueness includes canonical identity, source/owner namespace, coalesced identity,
generation, content hash and schema/taxonomy/extractor. The unique expression also
covers null-source owner batches. Fact uniqueness includes batch/key/scope/origin.
No production queue, idempotent ingest writer, lease, resolver or rematcher exists
yet; insert retries are only protected by the DB identity, not automatically replayed.

`digest` and `validate_evidence_against` verify an already-sanitized string mapping;
structured keys use `structured.<provider_field>`. Include every selected extraction
input (canonical structured values/metadata serialized as strings) in that mapping
before hashing. This is a proposed internal evidence-mapping hash, not #373's
legacy import fingerprint or its differently shaped `ListingEvidenceInput` hash.
The future bridge must explicitly version/recompute this mapping and preserve all
selected content changes. No sanitizer is duplicated or claimed to detect PII.
Only synthetic sanitized inputs were used; activating real-content persistence
requires reviewed minimization/privacy/retention rules and the AI-04 writer.

Owner precedence, retention/GC and source TTL are not decided. No owner override
mechanism or stale-age threshold is enabled. The approved signed intent/quota
contracts in AI-07/08 are not imported, changed or stacked into this branch.

## Bounded BASE-373 compatibility review

On this date #373 remains open, head `fcae378d9dbbc8447f18df150327180f6f2c8231`,
base `planning/ai-voice-search-architecture` (`f203807d4507f68b34cd4407e326b3bc671a3552`).
GitHub reports no submitted reviews. AI analysis is not human approval; the
required human review/port gate remains open. No planning code is transplanted.

Compared the main/planning versions of `external_sources.py`,
`services/external_import.py` and `models/__init__.py`: no difference in those
files. The #373 runtime delta in `external_sources.py` contains the conservative
policy grammar call and expanded scalar fingerprint. This is a static compatibility
observation, not proof of a complete cherry-pick or payment/import integration.
The new schema touches none of these runtime paths; model registration is additive.

Remaining bridge work is concrete: #373 uses `explicit` plus value, spans without
offsets, structured `provider_field`, and a whole input-packet hash. An adapter must
translate allow/deny, reconstruct exact unambiguous sanitized spans, preserve
conditional/conflict, distinguish total vs available capacity, and version the new
evidence mapping. Scalar defaults and substring presence cannot supply proof.
#373's input cleaner is not outbound privacy approval. Run importer/gallery/
dedup and current payment regressions when an authorized port is prepared.

## Validation and rollback

Local environment: borrowed existing pinned Python 3.14.4 executable without
changing that venv; current branch supplied via `PYTHONPATH`. A new disposable
PostgreSQL 18.6 cluster on loopback port 55439, DB `ai_facts_test_local`, was created
for this chat. No existing application/production cluster was started or queried.
Every PG case applies the actual migration in a random schema and removes it.
Fixtures use `AI_FACTS_TEST_DATABASE_URL` or explicit `TEST_DATABASE_URL`, never
`DATABASE_URL`; loopback plus `ai_facts_test_*`/`ttest_test` names are required.
The latter supports existing isolated Production audit CI without new credentials.

Local final code: **121 focused passed** (93 DTO + 28 real PostgreSQL cases),
**928 backend unit passed / 15 platform or opt-in skipped / 341 integration
deselected**. The 93 new DTO passes are included in 928, not additional to it.
Ruff app/tests, mypy 116 app modules, pip check, immutable/expand-only migrations,
supply-chain pins and `git diff --check` passed. No ORM/migration differences;
zero temporary test schemas remained. The new cluster was stopped after checks.
Ignored local JUnit: `output/ai-facts-local.xml`, `output/ai-facts-unit-local.xml`.
Final-head CI evidence is recorded in the PR. Checks cover
strict types, negatives/conditionals/units, exact sanitized spans/hash, version and
JSON bounds, source/owner identity, source-status provenance, real migration/ORM
comparison, DB rejection bypassing DTOs, duplicate null-source batches, preserved
history, atomic transaction rollback and non-destructive downgrade. These are
synthetic cases, not source-extraction evaluation, real coverage or browser latency.

Dedicated CI requires pinned PG16/PostGIS, the complete historical migration chain,
`alembic check`, all backend unit tests, Ruff/mypy and focused PG tests with JUnit.
Local PG18 has no PostGIS: full historical-chain success is a CI result only.
Existing payment CI also exercises PostgreSQL payment/schema parity.

The independent branch has one linear migration head, as repository governance
requires. Before combining it with unmerged #378/#379, reparent the appropriate
**unreleased** revision onto the approved integration head and rerun chain/schema
checks; do not produce multiple Alembic heads or rewrite released migrations.

Rollback reverts application code; downgrade preserves new provenance/projection
tables. Older binaries ignore them. Nothing reads/writes these tables from current
endpoints/importers/workers; no activation flag is needed for an unconnected schema.
No provider/client/worker activation, public AI API, raw transcripts/audio, real DB
inventory, crawling/backfill, live staging, merge or deployment was performed.
Card/TOP/Stripe/map/gallery behavior is unchanged. API keys are not needed.
