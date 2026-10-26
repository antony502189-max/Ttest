# AI-07 — PostgreSQL backend quota foundation

Date: 2026-10-26. Base: main `1292c6807ece59999238bb31c80e09ef7e2c3212`
(payment #372 included). Branch: `codex/ai-07-quota-backend`.

## Authorization and scope

The owner explicitly authorized backend continuation in this chat on 2026-10-26:
«Да, продолжай backend по этим правилам». This satisfies the AI-01 review gate
for implementing the agreed quota lifecycle. It does not approve open business
decisions or represent a GitHub APPROVED review, merge or deployment permission.

References: [product](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/01_PRODUCT_SPEC.md),
[TZ](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/10_IMPLEMENTATION_TZ.md),
[AI-01 proposed ADR](https://github.com/antony502189-max/Ttest/blob/d46c44ee62aa89e0ac312e69d754aca9594f96d8/docs/ai-search-developer/adr/AI-01_CONTRACTS.md).
The offline experiment remains separately reviewable in [#377](https://github.com/antony502189-max/Ttest/pull/377).
It is not imported by the backend or merged into this branch.

This PR implements backend building blocks, not the public AI query endpoint.
No provider, frontend, listing/card/TOP/Stripe/parser change or running worker.
Current manual search and application endpoints retain their existing behavior.

## Implemented contracts

- Additive migration `0067_ai_search_quota`, registered ORM tables
  `ai_usage_days` and `ai_search_requests`, DB constraints, expiry partial index.
  Limit is generated from subject kind (guest 3 / auth 200); clients cannot pass
  a quota limit. Auth and guest are separate server-owned UUID namespaces.
- Exact byte/text digest, channel, session/version and contract bind the server
  request fingerprint. No text/audio/transcript/provider JSON is stored. Same
  subject+key+hash replays terminal metadata or reports in-flight; changed body,
  channel, session or version is rejected before claim.
- Reserve and claim use short independent PG transactions. Only the single
  successful claimant can proceed to future inference. Caller runs network work
  after claim returns, without retaining a connection. DB errors propagate;
  there is no in-memory business-quota fallback.
- Day-row locking and unique subject+key serialize the last-slot and duplicate
  key races. Counter mutations lock day before request. Claim locks only request.
- `finalize_in_transaction` requires a session CAS/durable-result callback using
  that exact PG transaction. Terminal retry returns before invoking the callback.
  CAS conflict rolls back callback-local writes, releases reservation, and stores
  `SESSION_VERSION_CONFLICT`, without debit. Successful zero-results debit one.
- Session/result/CAS, result reference and counters share a savepoint inside the
  enclosing transaction. Expiry after a slow DB lock undoes CAS even if a caller
  catches the stale-worker exception and commits the outer transaction. Unexpected
  callback errors also roll back callback-local writes; caller can then release
  failure separately, or let crash recovery release it.
- ASR/LLM/backend failures release once. Reserved operations can be released
  before claim (e.g. technical gate rejection). Failed keys never reopen. Fence
  and DB clock reject expired or stale worker writes. Recovery waits for explicit
  grace and only releases; it never starts another provider call. Bounded recovery
  batches run only when explicitly called; no scheduler is enabled here.
- Madrid bucket/reset use PostgreSQL IANA tzdata and server time. Completion and
  replay keep the reservation day across midnight; a new operation gets the new
  day. This is calendar-day quota, not a rolling 24h counter.
- Dedicated Redis attempt gate reuses the existing atomic Redis limiter and
  fails closed on missing Redis/outage. It never uses the existing memory
  fallback or treats Redis as business-quota authority. Caller supplies an
  explicit technical budget; values used in tests are not production decisions.

## Integration boundary

AI-08 must supply the real strict intent/session implementation, ownership-aware
CAS and durable validated response reference. Tests use a clearly named synthetic
session/result table with real SQL CAS to validate the transaction seam. A UUID
receipt is not evidence that actual search cards or current visibility were
checked. AI-09 must revalidate visibility on replay and map internal errors to
HTTP; no old cards are stored by this component.

The caller must derive `QuotaSubject` from server authentication or a signed
HttpOnly Secure SameSite guest cookie, never a request/model-owned subject. No
automatic guest-to-auth transfer is implemented. Before a paid call the query
pipeline must pass the attempt gate and endpoint-specific IP/audio/inflight
guards; constructing a ledger alone does not constitute the whole outbound gate.

LeasePolicy requires explicit reservation/running/grace settings (bounded internal
values, no production defaults). Test values are engineering fixtures. Clarification
debit, saved-alert quota, guest transfer, retention/key lifetime and provider
privacy remain undecided. There is no clarification terminal outcome and no row
deletion/GC. Retaining tombstones avoids treating old retries as new operations;
approved expiry/retention and bounded result storage are required before rollout.
No monthly spending cap is introduced.

## Validation and rollback

The focused tests execute the actual migration against fresh isolated schemas in
a disposable local PostgreSQL 18.6 cluster. They test the production repository,
not the lab SQL, and cover 3/200, shared voice/text, zero-result/replay, errors,
12-way races, CAS conflict/rollback, expiry, recovery, midnight and DST, DB bounds,
and full new-table ORM/migration comparison. The dedicated CI uses PostgreSQL
16/PostGIS + Redis, applies the complete Alembic chain and runs `alembic check`.
Local Redis is unavailable; its real integration test is explicitly skipped
locally and required by that CI. Outage handling is unit-tested locally.

Executed locally on Python 3.14.4 / PostgreSQL 18.6:
- Focused quota suite: **37 passed, 1 skipped** (only real Redis).
- Complete non-integration backend suite: **849 passed, 15 skipped, 337 deselected**;
  the 14 quota unit cases are included, not additional to those 849.
- Ruff over all app/tests and mypy over 118 app modules passed.
- Immutable migration history / expand-only check and supply-chain check passed.
- New-table Alembic comparison against ORM metadata: no differences.

Local JUnit artifacts: `output/ai-quota-backend-local.xml` and
`output/ai-quota-unit-local.xml` (ignored; CI publishes its own JUnit).
Full historical PostGIS chain is a CI check: installed local PG18 lacks PostGIS.

Validation results and final-SHA CI links are recorded in the PR. Local results
are not a claim of full GitHub CI success, production readiness, coverage or SLO.

Rollback: revert application code and stop using the component. Migration
downgrade intentionally preserves these additive tables so history, reservations
and idempotency records cannot be discarded. Older binaries ignore the new
tables. No migrations were applied to existing application or production DBs.
No paid APIs, live staging, production audit/write, merge or deployment performed.

API keys are unnecessary for AI-07/08. Provider credentials are needed only at
the separately approved ASR/intent/enrichment integration and should be installed
through server-side secret configuration, never source control or chat messages.
