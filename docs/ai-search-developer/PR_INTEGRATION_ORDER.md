# PR #373–384: checked state and proposed integration order

Snapshot: 2026-10-26. GitHub refs/reviews/workflows rechecked in this chat.
Main is still `1292c6807ece59999238bb31c80e09ef7e2c3212` (payment #372).
This is a review/integration recommendation, not execution of merges or closures.

## #373 is accepted in planning

[#373](https://github.com/antony502189-max/Ttest/pull/373) is merged=true into
`planning/ai-voice-search-architecture` at `a5650517`, preserving head `bdd7ca93`.
GitHub records GeorgePetarda's APPROVED review at 20:15:40 UTC and merge at
20:18:10 UTC. The latest Parser, Payment and Security workflows on this head
are completed/success. Earlier dated closed/reopened/no-approval reports are
history and are superseded by this check. This chat submitted no review/merge.

The parser code is **not on main**. The merge does not import the planning branch
into current production. A focused port of the reviewed delta onto current main,
with payment/import/gallery regressions, remains a separate reviewable change.
The bounded cleaner also does not complete the outbound privacy gate, approve
real-content persistence, paid providers or catalog backfill.

## What to do with the remaining PRs

All eleven PRs #374–384 are still open/unmerged. Every workflow returned for
their recorded heads completed/success. None has a submitted GitHub review.
CI coverage differs by base/path; stacked green checks do not mean main-only
Full/Mobile/Production workflows ran on every delta.

| PR | Purpose | Recommended action |
| --- | --- | --- |
| [#374](https://github.com/antony502189-max/Ttest/pull/374) | Product/TZ/developer handoff | Review and land documentation first; retain dated production baselines. |
| [#375](https://github.com/antony502189-max/Ttest/pull/375) | Gap closure, based on #374 | Land after #374, updating its base and resolving overlaps; preserve owner scope above recommendations. |
| [#376](https://github.com/antony502189-max/Ttest/pull/376) | Proposed AI-01 contracts | Reconcile README/journal overlap with #374/#375, then land reviewed contracts. Proposed policies do not become owner decisions automatically. |
| [#377](https://github.com/antony502189-max/Ttest/pull/377) | Disposable quota design lab | Keep as reference until #378 is accepted, then close as superseded. Preserve branch/report; it need not become a second runtime implementation on main. |
| [#378](https://github.com/antony502189-max/Ttest/pull/378) | Actual quota foundation | Review/land first backend migration `0067` after docs/contracts reconciliation. |
| [#379](https://github.com/antony502189-max/Ttest/pull/379) | Sessions, stacked on #378 | Review/land after #378; adds `0068`. Refresh its base and checks. |
| [#380](https://github.com/antony502189-max/Ttest/pull/380) | Independent facts `0069` | Before combining, reparent this still-unreleased migration from `0066` to `0068` in a reviewed integration update; rerun all schema checks. |
| [#381](https://github.com/antony502189-max/Ttest/pull/381) | Facts queue `0070` | Rebase/retarget after corrected #380; review transaction/resolver delta. |
| [#382](https://github.com/antony502189-max/Ttest/pull/382) | Offline bridge | Follow #381; preserve injected-builder boundary and synthetic fixture provenance. It is not the production minimizer. |
| [#383](https://github.com/antony502189-max/Ttest/pull/383) | Explicit one-job runner | Follow #382; no daemon/provider activation follows from merging an inert component. |
| [#384](https://github.com/antony502189-max/Ttest/pull/384) | Partial hard-value SQL | Follow #383; retain unsupported-hard-criteria rejection and pre-pagination requirements. |

Target migration ancestry after review:
`0066 -> 0067 quota -> 0068 sessions -> 0069 facts -> 0070 queue`.
Do not merge the two current migration roots unchanged, produce multiple heads
or rewrite released migration history. No existing PR branch has been rewritten
here. If main advances, first verify whether a revision has become released.
Each base update needs fresh CI against that actual integration state; previous
synthetic merge checks are not evidence for a different combined tree.

## Continued implementation

The next small delta over #384 adds [current-projection reads](CURRENT_FACT_READS.md):
a bounded read-only snapshot check against current source state and current
evidence, sharing the writer's manifest/resolver. It neither connects a public
query nor performs repair/enqueue. Subsequent work still includes a reviewed
main port of #373, complete typed hard matching, efficient SQL current-source
guards before pagination, existing eligibility/TOP/cards/cursors, and quota/
session orchestration. Read-only DB inventory, actual minimization/privacy,
retention, provider and release gates remain separate.

No PR was merged/closed/reviewed by this chat. In particular, #377's closure
above is a recommendation, not a completed action.
