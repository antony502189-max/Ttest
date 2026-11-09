# S2.1 / S4.1 / S6: disabled microphone after catalog expiry

The owner reported a disabled “Надиктовать запрос”. At17:35UTC the deployed
pilot returned catalog_ready=false / PILOT_CATALOG_STALE, approved=true,
voice=true, attempts8/50. The browser permission policy already allowed the
microphone. All13 initial records had fresh production imports at16:57UTC,
but the private pilot had retained its initial static snapshot.

The bounded host sync now reads only these immutable listing/source IDs from
existing imports using read-only repeatable-read SQL and the existing visibility,
freshness and consistent-price selection. It rebuilds facts and query proofs
inside the private database without reseeding or contacting an AI provider.
Importer observation timestamps are preserved. A minimized observation receipt
advances fact generation on a new real observation; replay is idempotent.
Unknown IDs, stale/future receipts, observation rollback and price disagreement
fail validation. The original source TTL is unchanged.

At17:51UTC the real sync refreshed13 records. A separate DB/state backup is at
`/srv/112233-ai-site-pilot-20261108/backups/catalog-refresh-20261109T175103Z`.
Provider journal logical contents, signing keys, original seed snapshot and
environment stayed identical; attempts stayed8/50, paid calls0, reseed0.
Authenticated status returned catalog_ready=true, halted=false, approved=true.
The30-minute systemd timer and a repeat one-shot completed successfully.

The microphone component now explains its disabled state immediately beside
the button, including stale data, daily quota, missing rental mode, pending
receipt and session synchronization. An invalid existing intent is guarded
before recording as it already was before text submit. Ordinary runtime voice
activation remains unchanged.

Validation before committing: disposable real PostGIS refresh regression PASS,
including recovery from expired data, same-observation replay, unchanged seed
marker/journal bytes, no spend and rejected cohort/stale/future/price mutations.
Pilot browser18/18 PASS (previous15 plus stale/quota/ready regressions);
TypeScript, Ruff, frontend lint/i18n PASS. The first browser invocation lacked a
Playwright browser cache; rerun used installed Chrome and passed. The first PG
run reached readiness=true but failed on an incorrect test-only SQL column;
the corrected regression passed. Full seed suite and new-head CI/release
evidence must be recorded separately; previous a8506724 CI is historical.

This restores this closed pilot's microphone availability. It does not close
human speech/accent/cross-browser quality, p95/capacity, broader S2.1 source
coverage/instant removal, saved searches, delivery or full-release gates.
Stopping upstream imports still causes real TTL expiry; timer failures need
operator monitoring. No main-production writes, new crawling or cohort expansion.
