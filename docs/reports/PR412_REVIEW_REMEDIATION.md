# PR412 remediation — 10 November 2026

Baseline fde63c90. Source-only fixes; no merge/live deployment/crawl/paid calls,
approval changes, production migrations or journal resets.

| Finding | Fix and regression |
|---|---|
| PR412-01 P1 | Complete immutable cohort receipt with explicit tombstones; retire IDs, delete proofs and reconcile. PG covers missing/unpublished/inactive/stale/price mismatch, all gone and restoration, with actual verified card reads. |
| PR412-02 P1/P2 | Durable publication barrier and generation fences on pilot cards/maps and HTTP responses. Faults after source commit/observe/claim/complete/proof block reads; rerun completes. Exhausted jobs retain history and get a new work generation without changing upstream timestamps. |
| PR412-03 P2 | All whitelisted CARD_FIELDS/public coordinates sync includingNULL. Public digest invalidates evidence. Tests change pets/furnished/amenities/price/position. Complete fields and minimized price payload required. |
| PR412-04 P2 | Exact voice400 AI_REQUEST_INVALID clears pending/locator/persistence. This code is guaranteed pre-execution; post-handoff ValueError is uncertain503. Other400 stays ambiguous. Browser390/1440 tests cover reload/retry and absent-operation avoidance. Terminal failures clear old locators before another attempt. |
| PR412-05 P2 | Typed LocalASRBusy→VOICE_CAPACITY_LIMIT, distinct UX/zero debit. Concurrent adapter/PG test proves one slot, replay without inference and unchanged rejected quota. |
| PR412-06 P2 | Dedicated voice execution/ASR/parser histograms and bounded outcome counters. Success/replay/capacity/claim/finalize/timeout/cancel/private-label tests. Buckets cover declared budgets. Counters describe responses, not unique debits. |
| PR412-07 P2 | Last success/consecutive failures,75min read cutoff, OnFailure callback, minute textfile metrics and alert rules. Actual isolated systemd failure→callback→recovery PASS; production units/state untouched. Loopback metrics reject forwarded-IP spoofing. |

Baseline RED reproduced three actual PG failures (removal/partial refresh/fields),
two voice PG failures (metrics/capacity) and the invalid400 browser failure.
These local reproductions are separate from the auditor's static report.

Pre-final validation:1873unit PASS/16explicit skips,26pilot browser PASS,
27focused disposable PG refresh/recovery PASS,2focused metrics/capacity PG PASS;
Ruff/mypy179 PASS. Final-source PG/HTTP/CI recorded separately. Counts overlap.
Initial browser invocation lacked Playwright cache; installed Chrome is used for
local contracts. Initial systemd fixture lacked its staged helper directory;
corrected staging passed actual failure callback/recovery. No failure is claimed
as a production acceptance test. No schema migration was added.

## Retained acceptance blockers

- QA-01: old unexplained synthetic rejection remains retained. Owner confirmed
  one Russian scenario; broader human/accent/noise/Firefox/Safari quality untested.
  No user audio/transcript was stored or inspected.
- QA-02:19s total/8s ASR/10s intent/20s HTTP budgets unchanged. Metrics enable
  measurements; p95/p99/full15s speech/capacity are not certified. No paid load test.
- QA-03: closed pilot only. Coverage/quality, instant removal between syncs,
  provider account, saved/delivery/full release remain open. Live collector/rule/
  notification installation is a release gate; source definitions and isolated
  systemd rehearsal do not establish production alert delivery.

Model/media bounds, default-off ordinary voice, immutable cohort and one-debit
receipts remain. A future rollout must bootstrap the new health receipt before
opening traffic; do not remove the barrier or reset journals to bypass failure.
