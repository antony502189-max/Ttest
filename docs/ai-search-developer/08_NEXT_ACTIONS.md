# AI Search continuation — 2026-10-26

This main-based branch does not copy or merge the open handoff #374 or AI-01 #376
documents. Reconcile this journal with their next-actions files when reviewed;
do not replace their entries or describe them as merged.

- [x] Read Product, implementation TZ, implementation plan and next actions at
  handoff `d086fec3f0c4286d66493082982e2ac55a14d174`; read proposed AI-01 ADR.
- [x] Confirm current main includes payment #372; #373/#374/#375/#376 remain open.
- [x] Confirm #376 has no human reviews/comments; dependent runtime gate remains.
- [x] Prepare isolated AI-07 quota SQL lab with real disposable PostgreSQL tests.
  Draft [#377](https://github.com/antony502189-max/Ttest/pull/377), branch
  `codex/ai-07-quota-lab`, executable-code SHA
  `b4680e88ebde3cd47b0b2a21d9d13357584d4a6d`; local PG18.6: 25 passed.
  Final head/checks are available in the PR; CI is not presumed green.
  See [validation](AI-07_LAB_VALIDATION.md) and [run instructions](../../tools/ai_search_quota_lab/README.md).
- [ ] Human review of [AI-01 #376](https://github.com/antony502189-max/Ttest/pull/376),
  especially section 6 operation lifecycle, before dependent backend runtime PR.
- [ ] AI-07 application integration: identity/hash/anti-abuse, additive migration,
  retention/tombstones, validated bounded results and safe replay; then AI-08
  session CAS in the same finalize transaction. Lab is not completion of these.
- [ ] Separate decisions on clarification, guest transfer and background alerts.
- [ ] Preserve separate BASE-373 review/port, approved DB-readonly and provider
  privacy/staging/production gates. No merge or deployment authorized here.
