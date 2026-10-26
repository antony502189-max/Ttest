# Combined integration journal — 2026-10-27

Both independent branch journals are retained below. These are historical records, not approval or main merge statements. Current integration evidence is recorded in COMBINED_RUNTIME.md.

# AI Search facts continuation — 2026-10-26

## Latest check after owner reports #373 ready

- #373 is now **merged into planning**, `a5650517`, from unchanged `bdd7ca93`.
  GitHub records APPROVED at 20:15:40 UTC; latest Parser/Payment/Security CI all
  succeeded. Main is still `1292c680`. Earlier state snapshots below are history.
- #374–384 remain open/unmerged, no submitted reviews; every returned workflow
  on their heads succeeded. [Review/integration order](PR_INTEGRATION_ORDER.md)
  explains docs, superseded lab #377 and the required `0066 -> 0067 -> 0068 ->
  0069 -> 0070` migration integration. No PR branch/state was changed here.
- Continued over #384 with [current-projection reads](CURRENT_FACT_READS.md):
  one bounded read-only PG snapshot, shared manifest, re-resolution and stale/
  pending/corrupt evidence rejection. No public query or parser activation.
- Next integrate complete typed matching and efficient pre-pagination current
  source/eligibility guards; prepare a separate reviewed #373 port onto current
  main, preserving payment changes. Do not merge planning wholesale.

## Continuation in the new chat — current correction

- #373 was **closed without merge** at `bdd7ca93` by explicit owner request
  and was still closed at this chat's first check. A subsequent external action
  reopened it: latest metadata shows open/unmerged, updated 20:10:40 UTC, plus
  a COMMENTED review explicitly marked AI verification. CHANGES_REQUESTED
  reviews remain; no APPROVED review exists. This chat changed no PR state/review.
  Earlier no-review statements below are history, not current status. Do not
  treat state changes as authority to merge/port/activate its builder.
- #374–376 and #378–383 remain open/unmerged; current main is `1292c680`.
  #383 final-head three workflows were rechecked completed/success.
- Partial independent AI-09 preparation on `codex/ai-offline-hard-predicates`,
  stacked over #383 `97494713`: [offline hard-value SQL](OFFLINE_HARD_VALUES.md).
  Confirmed capacity >= N and exact four booleans only, composable before
  count/order/seek/limit. No public query, parser port or catalog activation.
  Pinned local checks: 276 focused (176 unit + 100 PG), 1011 total backend unit
  passed/15 skipped; Ruff/mypy126/pip check passed. Owned cluster stopped clean.
- Next: current-source/projection read guards and complete typed hard matching,
  then reviewed integration with existing visibility/TOP/cards/cursors and
  AI-07/08. Reconcile migration branches before combined schema integration.
  Do not silently ignore remaining hard intent criteria or select pending policy.

## Earlier dated implementation journal

- [x] Read Product/TZ/plan, AI-01 proposed ADR and AI-07/08 reports.
- [x] Rechecked current main `1292c680`, open docs/parser #373–375 and backend
  #378/#379. AI-07 head `3293b9e2`: all 8 workflows succeeded. AI-08 head
  `206ee036`: all 3 triggered workflows succeeded. No submitted reviews on
  #373/#378/#379; none merged. Main-only Full/Mobile/Production workflows did
  not run on stacked #379. This is a dated snapshot, not ongoing monitoring.
- [x] Prepare independent AI-03 schema/strict DTO PR from current main, separate
  from quota/session branches. See [report](AI-03_BACKEND.md).
- [ ] Review AI-03 storage choices and final-head CI. Reconcile the independent
  unreleased migration with AI-07/08's linear chain before eventual integration.
- [ ] BASE-373: human review and separate safe port to approved current code;
  static file comparison here is not approval or completed port.
- [ ] AI-04: durable source generations and enqueue/reconciler, locked canonical
  identity checks, idempotent validated ingest, CAS stale-hash rejection,
  resolver conflict/authority rules and atomic projection/revision/rematch outbox.
  Use only synthetic/disposable data and fake workers until later gates pass.
- [x] AI-04 offline backend delta prepared on stacked branch
  `codex/ai-04-facts-queue` over #380 head `a5f4705a`; see
  [queue/resolver implementation and limits](AI-04_BACKEND.md). Actual durable
  transactions and source-only resolver are tested; importer/worker activation,
  real source packet bridge, canonical remap and owner precedence remain open.
- [ ] Review AI-03 and AI-04 separately; check final-head dedicated and payment
  CI. Do not treat stacked CI synthetic merge refs as actual merges. On the
  final verification AI-03 head `a5f4705a` has all eight triggered workflows
  completed/success, including Mobile. No submitted reviews; #380 remains open.
- [ ] Before live worker integration: review importer lock order and BASE-373,
  approved source vocabulary/minimization, durable snapshot-to-input hash bridge,
  privacy/retention and an explicit operating policy. No daemon is enabled here.
- [x] Independent offline bridge prepared on `codex/ai-05-offline-fact-bridge`
  over #381 head `ebcc1918` (all three workflows completed/success). See
  [partial AI-05 bridge](AI-05_OFFLINE_BRIDGE.md): coherent bounded snapshot capture,
  required injected sanitized builder, strict pinned #373 packet compatibility,
  exact spans/scopes, distinct hashes and synthetic AI-04 end-to-end transactions.
- [ ] Review bridge separately. #373 still has no submitted human review; its
  cleaner/grammar/importer are not ported and a real minimizer is not supplied.
  Approve actual field/scope mappings and minimization before real source ingestion.
  The optional pinned fixture generator is not an application dependency or gate
  approval. No default builder, activated worker or public AI endpoint exists.
- [x] One-job offline runner prepared on `codex/ai-offline-fact-worker` over
  #382 head `c9fab184` (all three workflows completed/success). See
  [runner behavior and limits](OFFLINE_FACT_WORKER.md). Explicit version dispatch,
  required fake builder/retry policy, guarded failure and commit-ack/cancellation
  safety; no scheduler/provider/endpoint activation.
- [ ] User requested a new project chat after completion to explain human review
  of #373. It must explain actual developer review and GitHub submission, not
  submit an AI approval, merge planning into main or treat green CI as a human gate.
- [ ] Review owner-fact precedence; do not silently adopt the proposed override.
- [ ] AI-02 authorized read-only DB role: measure real coverage/source health and
  query plans before production index/backfill/freshness claims.
- [ ] Approve source vocabulary/mapping, minimization and retention before real
  facts ingest. #373 cleaner alone does not authorize personal outbound data.
- [ ] AI-09 remains blocked on verified facts/resolver and query integration.
  Preserve hard predicates before count/order/seek/limit and existing TOP/cards.
- [ ] Provider privacy/account and paid-call approval, real staging/browser SLO,
  main merge and deployment remain separate gates. Keys are unnecessary now.

This journal belongs to the independent facts branch. Reconcile it with open
#374/#376/#378/#379 journals on review; no other branch's progress is overwritten
or treated as merged. Clarification debit/alerts/transfer/TTL/retention remain
pending; this increment does not select their policies.


---

# AI Search backend continuation — 2026-10-26

- [x] AI-01 contracts prepared in [#376](https://github.com/antony502189-max/Ttest/pull/376).
  Its six workflows succeeded on `d46c44ee62aa89e0ac312e69d754aca9594f96d8`.
- [x] Isolated PG quota experiment [#377](https://github.com/antony502189-max/Ttest/pull/377):
  25 local PG18.6 + CI PG16.4 passes; no application integration in that PR.
- [x] Owner explicitly approved backend continuation under the quota rules in
  this chat. Open business proposals remain undecided; no merge/deploy approval.
- [x] Implement actual backend AI-07 ledger, expand-only migration, mandatory
  transaction callback for AI-08 CAS/result writes and fail-closed Redis attempt
  gate on current main. See [implementation report](AI-07_BACKEND.md).
- [ ] Verify final head CI and review this standalone backend PR before merge.
- [x] AI-08 real strict sessions/intent patches and ownership-aware CAS callback;
  unnamed criteria preserved, same-version conflict releases quota, explicit
  closed reset, no automatic guest transfer. Stacked branch
  `codex/ai-08-search-sessions` over #378; [implementation/evidence](AI-08_BACKEND.md).
- [ ] Review AI-07 and AI-08 separately and check their final-head CI. They remain
  unmerged and are not the public AI query product.
- [ ] AI-09 query API: signed guest identity, server request hashing, enforce
  technical gates, durable validated result and visibility-safe replay.
- [ ] Decide clarification debit, background-alert quota, transfer and approved
  retention/key-expiry and production lease/attempt budgets before activation.
- [ ] Keep separate BASE-373 human review/port, facts/queue, approved read-only
  source inventory, privacy/provider and staging/production gates.

This file must be reconciled with the journals in open docs #374/#376/#377 when
those branches are reviewed. They are not silently merged or marked implemented.
