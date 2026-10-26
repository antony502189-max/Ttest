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
