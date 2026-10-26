# AI Search facts continuation — 2026-10-26

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
