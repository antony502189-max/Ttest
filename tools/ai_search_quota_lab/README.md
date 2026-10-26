# AI-07 disposable PostgreSQL quota experiment

**PROPOSED / OFFLINE LAB / NOT APPLICATION RUNTIME.** This is review preparation
while [AI-01 #376](https://github.com/antony502189-max/Ttest/pull/376) has no human
review. It installs no backend models, Alembic migrations, endpoints or workers.
It does not complete AI-07 or AI-08. No provider or Redis client exists here.

Authoritative requirements: [Product](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/01_PRODUCT_SPEC.md),
[implementation TZ](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/10_IMPLEMENTATION_TZ.md),
[proposed AI-01 ADR](https://github.com/antony502189-max/Ttest/blob/d46c44ee62aa89e0ac312e69d754aca9594f96d8/docs/ai-search-developer/adr/AI-01_CONTRACTS.md).

## Experiment

`schema.sql` is loaded into a fresh random schema for **each test**. Identity is
synthetic UUIDs; hash and results are synthetic. No existing application tables
are read. The fixture refuses non-loopback hosts and database names without
`ai_quota_lab_`. Use a disposable instance with only lab credentials: these checks
are accident prevention, not a sandbox or permission boundary. Schema cleanup is
restricted to the random schema created by the fixture.

```sh
python -m pip install -r tools/ai_search_quota_lab/requirements.txt
# Provision a fresh disposable local PG database named ai_quota_lab_local first.
# Set AI_QUOTA_LAB_DSN to its loopback connection string in your shell.
python -m pytest -q tools/ai_search_quota_lab --junitxml=output/ai-quota-lab.xml
```

The dedicated GitHub workflow uses disposable PostgreSQL 16/PostGIS, performs no
application migrations, and uploads JUnit evidence. Local PostgreSQL 18 is also
supported. Tests fail, rather than skip, when no lab DSN is supplied. They do not
read `DATABASE_URL` or `TEST_DATABASE_URL`.

## Design being tested, not approved for integration

- Composite subject `(kind, UUID)` separates guest/auth and unrelated owners.
  The real identity must eventually come from server authentication or a signed
  cookie, never from an untrusted model/client parameter.
- A PostgreSQL day lock serializes quota mutations; DB constraints enforce
  nonnegative `used/reserved` and the 3/200 bound. Unique subject+key prevents a
  second operation, independent of channel or reservation day.
- Reserve returns `created`, `inflight` or terminal `replay`. Only a successful
  claim gives one worker authority to call a provider. Calls are never performed
  by the lab. Same key with another hash fails. A new hash requires a new key.
- All counter changes lock day before operation. Claim only locks operation and
  never requests a day lock; this avoids opposite-order deadlocks.
- Successful synthetic result (including count zero), persisted result and
  counter update are one transaction. Failure releases exactly once. Rollback
  undoes both result and debit. Concurrent duplicate finalizes return the same row.
- A 60-second reserve/claim lease is an **experiment parameter**, not an approved
  SLA. Expiry cannot be reclaimed for another inference. Recovery increments the
  fence and releases with `LEASE_EXPIRED`; stale success cannot debit. A call on
  an already-terminal row returns that row, even from an old worker; it never
  changes the result or converts a recorded failure into success.
- The reservation date is DB-derived Madrid local day. Completion/replay uses
  that original date; reset is next Madrid midnight converted to UTC.
- Rows are never deleted by a retention worker. This intentionally avoids
  inventing a dedup expiry policy. Production needs approved retention, a bounded
  result envelope, tombstones and server-validated key lifetime before deletion.

## Deliberately absent gates

No clarification outcome, saved-alert quota, guest transfer, provider retry,
privacy, cookie identity, Redis abuse budget, retention duration or production
lease configuration is chosen here. No source/parser changes or TOP/Stripe/card
changes are involved. The lab accepts an arbitrary synthetic JSON result; it is
not an application response validator or a safe transcript store.

Before backend integration: human review of AI-01 quota lifecycle; reviewed
strict DTO/server hash construction; identity and anti-abuse fail-closed gates;
additive migration/schema parity; session CAS in the same finalize transaction
(AI-08); visibility-safe replay and retention/key-expiry design. Recovery of a
persisted validated result is future work; this lab only demonstrates release
without repeat inference. Real paid billing cannot be made exactly-once by a PG
fence. AI-07 is not complete until those required boundaries are implemented and
validated in the application. Merge, staging and production remain separate gates.
