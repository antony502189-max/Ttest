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
