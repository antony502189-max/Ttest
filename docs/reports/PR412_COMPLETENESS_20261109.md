# PR412 completeness audit

The owner confirmed the released voice scenario works and requested verification
that all changes are in the pull request. GitHub PR412 is open/draft, not merged.
Before this documentation supplement, local HEAD, fetched origin branch and PR
head all equalled255b65ef3efffcfb2606000204a8dfb47163b307; the checkout was clean.
Base is merged411/main1a91d8fe6025ef49fc17765ed97b7638116870b8.

All application changes were already present in these five pushed commits:

| Commit | Included change |
|---|---|
| e7ba3cbf | Microphone capture, bounded local ASR, durable one-debit voice search and tests |
| 1fc200d5 | Same-origin microphone permission policy |
| a8506724 | ASR cold-start bounds and dedicated pilot browser discovery |
| 857d8c41 | Incremental original-cohort catalog refresh, timer and disabled-button explanation |
| 255b65ef | Russian700 recognition, finite cardinal grammar, busy/replay/rejection UI and regressions |

The audit found documentation gaps: the final Russian700 release appendix and
some final CI/runtime/live artifacts existed only in the canonical local report
copy. This supplement includes the final reports/plan and the existing safe
evidence folders for the initial voice release, catalog/button repair and Russian
recognition. Successful and failed proofs remain separate, each bound to its
original application SHA. Historical release records are labelled accordingly.

The owner confirmation is recorded as a single observed voice scenario.
It does not close broad ASR human/accent/cross-browser/p95 quality or the other
S0–S7 data/provider/performance/saved/delivery/full-release gates.

Verification for this documentation supplement: JSON/XML artifacts parse,
report-relative links resolve, evidence is checked for credential material,
and the entire runtime-input projection equals the verified255b65ef projection
(1031inputs). No application, model asset, test implementation or deployment
configuration changes are introduced by the supplement. The application255b65ef
CI remains13successful workflows/2conditional skips; new-head CI triggered by
the documentation push must be reported separately rather than inheriting those
results as an exact-head claim. Merge, deployment and paid calls are outside this
audit and were not performed.
