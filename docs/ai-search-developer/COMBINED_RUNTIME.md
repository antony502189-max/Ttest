# Combined parser, facts, quota and sessions — 2026-10-27

Reviewable integration of actual refs: #386 `5856dfa7`, #385 `4b10de28`, #379 `206ee036`, based on main `1292c680`. This branch does not merge/deploy main or modify the source PR branches. The overlapping model registry retains all four AI modules; both independent execution journals remain in 08_NEXT_ACTIONS.md.

## Migration reconciliation

The still-unreleased 0069 parent is 0068. One chain: 0066 -> 0067 quota -> 0068 sessions -> 0069 facts -> 0070 queue. No released revision changes. This PR is an alternative combined integration vehicle for #378–385 and #386; do not merge those old roots separately without reconciling bases and the parent. Owner must decide the merge vehicle after review; no automatic closing of existing PRs, including reference lab #377.

New disposable PostgreSQL test applies all four new migrations in order in one random schema, compares all 11 AI models and CHECK names, and removes that schema. The existing facts and session tests remain separate correctness suites. Combined workflow additionally runs both suites on the same head with PostgreSQL16/PostGIS and real Redis, full historical upgrade and alembic check. Parser/Payment/Production/browser CI still matter; do not infer those results from another PR.

## Local evidence

Pinned read-only Python3.14.4/SQLAlchemy2.0.51. 1202 unit passes /15 platform-or-opt-in skips. Existing real PostgreSQL18 suites:169 passes /1 Redis unavailable skip; corrected new combined schema test passed separately. The initial combined test attempted additive downgrade stubs; fixed to use its own fresh schema, without changing migration rollback semantics. Full corrected run and CI recorded in the PR. Ruff/mypy136, immutable/expand-only migration governance and supply-chain checks. No local PostGIS or Redis; CI required.

## Activation boundary

No public AI endpoint, query integration, importer hook, provider, scheduler, crawl/backfill or live DB. Full hard matching and current-source guard BEFORE count/order/seek/limit, existing cards/TOP/cursors, quota/session orchestration still pending. Current single-listing reader is not the catalog query. Existing legacy roomCapacity equality remains unchanged. No coverage/freshness/privacy/10s SLO claim. Clarification debit, alerts quota, production TTL/retention, guest transfer, owner precedence remain pending.

PR public-source discovery guard from #386 is retained: live step only schedule/workflow_dispatch, PR uses fixtures. CI network steps inspected before opening this PR; no deployment workflow is triggered by opening a PR. Rollback uses older binaries while preserving additive history.
