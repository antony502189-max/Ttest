# AI-08 — structured sessions and atomic intent patches

Date: 2026-10-26. Branch: `codex/ai-08-search-sessions`.
Stacked base: [AI-07 #378](https://github.com/antony502189-max/Ttest/pull/378),
`3293b9e201f76867b5a9e6a749d4d5ab42baa425`; main underneath includes payment #372.
AI-07 is not merged. This PR does not replace main with a planning branch.

The owner authorized continued backend work in this chat. Product decisions in
[Product](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/01_PRODUCT_SPEC.md)
and [TZ](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/10_IMPLEMENTATION_TZ.md)
remain authoritative. Technical vocabulary follows
[AI-01 section 4](https://github.com/antony502189-max/Ttest/blob/d46c44ee62aa89e0ac312e69d754aca9594f96d8/docs/ai-search-developer/adr/AI-01_CONTRACTS.md).
Implementing these internal components does not approve every proposed business
decision, or authorize merge, providers, staging or production.

## Actual code

- Expand-only `0068_ai_search_sessions`: owned `ai_search_sessions` and durable
  `ai_search_results`. Tables are registered in Alembic ORM metadata. New-table
  DB checks bound versions/counts/JSON size and result hash; result belongs to
  the exact subject+idempotency operation and references its session.
- Required v1 schema/taxonomy, strict generic criterion values, rental mode,
  EUR+explicit period, INE province/municipality, accommodation, party, pets,
  smoking scope, furniture/bills/deposit/balcony/terrace, amenities, dates/stay.
  Unknown fields, coercion, unknown versions, explicit null criteria, partial
  party/budget replacements, duplicate/overlapping removes and JSON paths fail.
- Optional criterion means absent, not inferred false. `set` replaces whole
  criteria; `remove` is an explicit allowlist. Merge validates the final state,
  including hard dates vs nights. Months are not converted to 30 nights; EUR
  weekly is not converted to monthly. User budget is not clamped to EUR1000 by
  a session: current catalog policy must still be applied by AI-09 SQL.
- `SearchSessions` uses PostgreSQL only, with server-owned subject and UUID.
  GET does not extend expiry. Successful commit extends inactivity expiry using
  the DB clock and an explicit injected policy; no production 24h default is
  chosen. Expired/closed sessions fail; none silently becomes an empty search.
- The real ownership-aware CAS callback joins AI-07's savepoint/transaction:
  session version+criteria, durable intent receipt and quota debit commit together.
  Same-version race yields one next version; loser releases with no debit. The
  test also races operations reserved on different Madrid dates, so success
  cannot be attributed only to a shared day-row lock.
- Session not found/expired/invalid produces a specific failure and releases
  reservation after callback rollback. AI-07's existing CAS-conflict exception
  remains compatible; its callback rejection handler now supports these reasons.
- Terminal retries skip callback. Original result returns its stored typed intent
  and hash, even after a later successful follow-up. It does not reapply the old
  patch or debit. Expired/closed replay requires a new explicitly requested query;
  no automatic provider retry. AI-09 still must validate card visibility/cursors.
- Explicit reset closes the old identity and creates a fresh empty UUID/version0
  in one transaction. It is a server method, not an utterance heuristic. Pending
  old workers cannot resurrect it; the closed marker remains authoritative even
  if expiry is later changed. Reset changes neither subject nor daily quota.

## Technical choices requiring integration review

`IntentVocabulary` requires explicit server allowlists for amenity codes,
`catalog_other` codes and municipality zones. There is no permissive default.
Tests use synthetic allowlists, not an approved real-catalog mapping. Normalized
`one_bedroom` is representable and is not silently mapped to studio. AI-09 needs
the reviewed mapping to current catalog fields and matching SQL; this PR does
not claim that every normalized criterion is already searchable.

DTO engineering bounds follow AI-01's proposal: party/pet count <=10, amenities
<=100, changes <=20, bounded version/quantity/string fields. Deposit is a tagged
one-off EUR money value or a quantity of whole months; fractional months are
unsupported in this v1 implementation, never coerced or converted into euros.
These bounded DTO choices remain reviewable, not new product promises.

`SessionPolicy` requires explicit inactivity seconds (bounded to 30 days for
configuration validation); tests use 3600 seconds. This is not retention approval.
There is no deletion/GC or automatic guest-to-auth transfer. Owner namespace is
checked on reads, reset, callback and replay; the new query API must derive it
from auth/signed cookie and apply technical guards before any paid call.

No clarification debit decision is introduced. Invalid structured state is a
failed operation, not a successful clarification outcome. Background alerts,
transfer/retention/key lifetime, production TTL/lease/attempt budgets, provider
privacy and current source coverage remain separate gates.

## Verification

Local Python 3.14.4, fresh isolated schemas on PostgreSQL 18.6. Tests apply the
actual 0067+0068 migrations and use the actual quota/session repositories.
The legacy synthetic AI-07 seam tests remain separate from real AI-08 tests.

- Focused intent/quota/session set: **97 passed, 1 skipped**, only real Redis
  unavailable locally. 38 new DTO unit cases are included in that total.
- Covered: the three example follow-ups, strict negative DTOs, ownership and
  guest/auth separation, concurrent v7->v8 on same/different days, outer rollback,
  real result-write failure, lease expiry after CAS with caller catching the error,
  expiry after row-lock wait, terminal replay, closed reset and quota preservation,
  invalid persisted versions and corrupted result hash.
- Ruff app/tests and mypy over 121 app modules passed. Immutable migration,
  expand-only and supply-chain checks passed. The new-table Alembic comparison
  covers all four AI tables, with no schema drift.
- Full local backend unit regressions: **887 passed, 15 skipped, 359 deselected**
  (38 new intent unit cases included in 887, not additional to it). Local skips
  are Bash/jq, native FFmpeg and opt-in public-source tests, not new session cases.
  JUnit: `output/ai-sessions-unit-local.xml` and `output/ai-sessions-local.xml`.
- Final-head GitHub CI results are recorded in the PR.
  Dedicated CI requires real Redis, full historical PG16/PostGIS migration chain,
  `alembic check`, full unit tests, lint/types and focused tests with JUnit uploads.

Follow-up examples are handwritten synthetic patches. They demonstrate patch
application, not ASR/LLM extraction accuracy, real inventory coverage or the 10s
browser SLO. Stored results contain normalized intent/count only, not cards or
invented evidence/reasons; counts in tests are synthetic.

## Rollback and remaining work

Old code can ignore these additive tables. Downgrade preserves structured state,
results and quota history. No endpoint, provider client, worker, frontend or
listing/card/TOP/payment/parser behavior is enabled or changed here. No raw user
text, transcript or audio is persisted. No live DB, provider, staging, merge or
deployment operation occurred.

AI-09 needs an authorized query pipeline, strict extraction/critical-field handling,
technical gates, shared verified-fact matcher, existing cards/TOP and signed cursor
integration. Facts/queue and BASE-373 remain independent prerequisite work. API
keys are not needed for this session stage.
