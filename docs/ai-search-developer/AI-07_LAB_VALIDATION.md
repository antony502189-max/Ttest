# AI-07 — offline preparation, 2026-10-26

Status: **PROPOSED / REVIEW PREPARATION**, not AI-07 runtime completion.
Draft PR: [#377](https://github.com/antony502189-max/Ttest/pull/377), branch
`codex/ai-07-quota-lab`; executable-code SHA
`b4680e88ebde3cd47b0b2a21d9d13357584d4a6d` (follow-up only records PR metadata).
Base: main `1292c6807ece59999238bb31c80e09ef7e2c3212`, includes payment #372.
AI-01 dependency: [#376](https://github.com/antony502189-max/Ttest/pull/376),
head `d46c44ee62aa89e0ac312e69d754aca9594f96d8`, open, no submitted reviews or
discussion comments at inspection. #373/#374/#375 also remain open.

AI-01 ADR explicitly requires review before dependent runtime PRs. This change
therefore provides only an isolated SQL experiment, synthetic tests and a CI
workflow; no import path to backend, migration, route, provider or live operation.
[Lab README](../../tools/ai_search_quota_lab/README.md) explains assumptions and
the remaining integration requirements. No proposed decision is marked approved.

## Evidence

- Local fresh PostgreSQL **18.6**, loopback-only separate port and database;
  Python **3.14.4**, psycopg **3.2.13**, pytest **8.4.2**.
- Tests use fresh random schemas, separate DB connections, real PG transactions
  and row locks, not SQLite or a dictionary mock. Docker daemon was unavailable;
  installed PostgreSQL binaries were used to initialize a separate temp cluster.
- First revision: 19 passed. Expanded suite: **25 passed in 21.34s**, zero
  failures/skips. JUnit: `output/ai-quota-lab-local.xml` (local ignored artifact).
  Ruff 0.14.3 check passed; final formatting and whitespace checks passed.
  CI on PostgreSQL 16 is separate evidence, not inferred from the PG18 result.

Covered scenarios: 3/200 quota, shared text/voice successes, zero-result debit,
same-key in-flight/replay/hash conflict, subject isolation, invalid hash rejection,
12-client last-slot races (same/different keys), single worker claim, duplicate
concurrent finalize, ASR/LLM/backend release, rollback with no partial debit,
reserved/running crash recovery, expiry fences, late success vs recovery,
reservation-day completion/replay and Madrid 23/25/24-hour reset fixtures.

The server clock is not changed. The cross-midnight completion test moves only
its synthetic reservation bucket inside its disposable schema. Actual dates and
UTC resets use PostgreSQL IANA timezone calculations. Provider calls and actual
session CAS are not tested. This is not a performance/coverage/SLO claim.

## PR #376 CI observation

On its exact head: Security dependency and static audit, Audit Source Snapshot,
Capacity smoke safeguards and Production audit workflows completed successfully.
Full audit and Mobile validation were in progress on initial inspection; no
whole-PR green claim is made. The name `Production audit` is a GitHub workflow
name, not evidence of a deployment in this chat.

## Safety and next step

Primary checkout remains untouched. Lab runs used no application DSN or existing
PG cluster. No Redis/production DB, paid provider, parser port, merge or deployment.
Rollback: remove the lab files/workflow; nothing is installed in the application.

Required decision before dependent runtime work: human review/approval of the
AI-01 section 6 quota operation lifecycle. Clarification debit, guest transfer,
background alert quota and retention remain separate pending decisions; this lab
does not silently choose them. AI-08 atomic session CAS must accompany eventual
application finalize; the standalone synthetic result commit is not sufficient.
