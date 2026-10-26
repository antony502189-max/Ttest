# Reviewed #373 backend port onto current main

Date: 2026-10-26. Branch: `codex/ai-parser-main-port`.
Independent base: `1292c6807ece59999238bb31c80e09ef7e2c3212`, payment #372.
Source: [#373](https://github.com/antony502189-max/Ttest/pull/373), approved on
GitHub and merged into planning at `a5650517` from head `bdd7ca93`.

The owner authorized continued AI Search work after confirming #373 ready. This
is the separate reviewable main port required by the implementation plan, not a
merge of the planning branch or a production rollout. Existing source #373 and
backend PR branches #378–385 are not rewritten.

## Selected delta

The twelve backend files (four app modules plus eight test/fixture files) are
copied exactly from accepted head `bdd7ca931cb6ae3e166fb361f6b3d7a4534f960a`.
Their staged Git blobs are checked against that source. Planning-only roadmap,
historical audit artifacts and unrelated documentation changes are not included.
The only existing runtime file changed on current main is `external_sources.py`.
The current importer implementation, payment code and released migrations are
preserved. No schema change or data migration is introduced.

- Shared conservative policy evidence preserves questions, adjacent conditions,
  ban exceptions, species scope in both clause orders and explicit conflicts.
  Only explicit scalar permissions/capacity are projected by existing adapters;
  unknown/conditional/conflict do not become canonical defaults.
- Expanded normalized fingerprint detects optional-fact changes while retaining
  null/false/zero distinctions and existing photo identity/gallery behavior.
- Existing bounded offline packet preparation/cleaner and aggregate read-only
  audit command are provided as reviewed code. No audit of a real DB is executed.
  No default builder is connected to the facts queue/provider. Cleaner remains a
  bounded minimizer, not a complete outbound privacy gate.
- The dedicated parser CI now also targets main, uses the integration marker
  for unit selection, checks Alembic drift and uploads JUnit. Source workflow
  pins and synthetic PostgreSQL/PostGIS import tests are retained.
- The pre-existing external-source contract workflow now skips its live discovery
  step for pull requests; adapter regressions still run. Existing scheduled/manual
  audit paths retain their behavior. On the first PR head this pre-existing job
  auto-started; it was cancelled while installing dependencies, before its live
  discovery step. Final-head PR checks must stay offline. No audit was requested
  manually and no provider or application credentials were exposed.

## Verification

Pinned local Python 3.14.4 / SQLAlchemy 2.0.51:
**139 focused passed** and **974 backend unit passed / 15 platform-or-opt-in
skipped / 321 integration deselected**. Ruff app/tests, mypy 117 modules,
immutable/expand-compatible migrations, supply-chain and diff checks passed.
Focused tests are included in the full unit count.

Local PostgreSQL has no PostGIS. Full historical migration chain, schema parity,
real importer/gallery/deletion/payment and browser checks must pass in this PR's
own CI against current main; #373's green CI is not a substitute. Final run links
and any disposable combined-facts checks are recorded in the PR description.
No live catalog/DB, external crawl/backfill, paid provider call, staging or deploy.

## Merge checkpoint

Once this port's final-head checks pass and review is complete, begin the first
integration checkpoint rather than extending an indefinitely independent stack:

1. Documentation #374 -> #375 -> reconciled #376. Resolve journal/README overlap;
   proposed ADR policies remain proposed until explicitly decided.
2. This independent parser port onto main; preserve payment #372. #373 itself
   is already merged into planning and needs no additional merge there.
3. Quota #378 -> session #379, refreshing bases and checks after parent changes.
4. Before facts #380 lands, update its still-unreleased `0069` parent to `0068`:
   target `0066 -> 0067 -> 0068 -> 0069 -> 0070`. Refresh #381 -> #382 -> #383 ->
   #384 -> #385 and rerun combined schema/backend regressions.

The facts migration ancestry correction has not been applied to other authors'
PR branches here. Do not land two independent Alembic heads unchanged. Recheck
released history if main advances. Green CI alone is not a submitted review.
#377 remains a design lab; after #378 acceptance, close it as superseded while
preserving its branch/reference instead of adding duplicate runtime code.

No main merge/deploy is executed by this port. The owner requested notification
when merges become useful; the checkpoint above will be called out after CI.

## Remaining boundaries and rollback

The public query, complete hard matcher/current-source SQL before pagination,
session/quota orchestration, existing cards/TOP/cursor integration and provider
work remain separate. Catalog coverage/freshness and browser p95 <=10s remain
unmeasured. No TTL, retention, owner precedence or clarification/alert policy is
selected. API keys are unnecessary for this port.

Rollback reverts the parser port's application files; no AI schema/history is
removed. Expanded fingerprints may cause a conservative refresh on the next
explicit import; this PR does not execute an import or backfill. Existing search,
TOP/Stripe/card/map/gallery behavior must retain regression coverage.
