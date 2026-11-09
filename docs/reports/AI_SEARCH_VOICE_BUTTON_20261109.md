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


## Final deployed repair (source857d8c41)

Frontend857d8c4118360c89a84b54eb4019baa7aa905522 was deployed at17:56UTC:
image sha256:a3f4f9df008588bf1ec776c14a079be61fffe85c7dd68ad7bdb75af03ac510cd.
Backend/maintenance/egress remain on the verified a8506724 local-ASR release;
Postgres/Redis and those container IDs were unchanged. The bounded host refresh
operator files match857d8c41 after explicit CRLF→LF normalization. No backend
image rollout, migrations, reseeding, approval/key changes or journal resets.

Actual HTTPS1440/390: enabled microphone→recording→cancel, with no voice/query
dispatch. The deployed stale-data explanation was separately verified with only
the browser status response mocked; the actual catalog stayed fresh. Provider
attempts8→8, paid0. The UI backup is
`/srv/112233-ai-site-pilot-20261108/backups/microphone-ui-20261109T175605Z`.
The30-minute systemd timer is active, one-shot Result=success/ExecMainStatus=0.

Full disposable PostGIS seed/recovery suite24PASS in406.28s; targeted refresh
regression is included. Pilot browser18PASS. Exact857d8c41 CI:13workflows
SUCCESS/2conditional SKIPPED, no failed/incomplete workflows. The previous
a8506724 counts remain historical. Updated source provenance1028inputs PASS;
historical old-container acceptance is explicitly false for new source.
PR test merge875571b9f76fd4cc7a40dc1316cd14546d537cf6 and source857d8c41
have identical tree9d64d72dce86a53613ce34c7415041e2d7509a23.
See [evidence](ai-voice-button-20261109-evidence/ci-final.json),
[live proof](ai-voice-button-20261109-evidence/live-final-proof.json) and
[PR412 checks](https://github.com/antony502189-max/Ttest/pull/412/checks).

Next: owner human microphone/review412, then S2.1 standing quality/freshness
measurements. This bounded existing-import sync does not close broader real-data,
instant-removal/monitoring, human ASR quality/p95, saved/delivery/full-release gates.

## Owner question: previous-attempt hint (18:38UTC)

Read-only diagnosis: home-ai-search sets pending before awaiting the voice HTTP
response. Its new disabled reason does not distinguish normal busy processing
from ambiguous/lost-ack replay, so “Сначала проверьте результат предыдущей попытки”
can appear while the operation is simply running. The existing “Comprobar el mismo
intento” action reuses the operation key and immutable payload; it is not a new
independent search. This session did not alter or replay any owner's operation.

Private PG aggregate over the last2h showed3voice operations, all terminal
INTENT_UNSUPPORTED, latest18:36:59→18:37:04UTC; none reserved/running in that window.
These aggregate rows are not proof of any specific user's identity or utterance.
Status18:38:43UTC: catalog fresh, approved, not halted, provider8/50. No new agent
paid calls, runtime changes or transcript/audio inspection. Unsupported input
could reflect grammar rejection or ASR output; the spoken phrase is needed to
reproduce it. Human acceptance remains open. A busy-specific hint is a confirmed
UX correction to make in the next implementation increment, not a deployed fix.
