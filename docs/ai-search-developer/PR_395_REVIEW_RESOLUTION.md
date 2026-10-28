# PR #395 review resolution — 2026-10-28

Review source: owner's `PR_395_FULL_CODE_REVIEW_RU.md`, reviewed head
`37f78e266369736203bfd947e393ded27a105b38`. No public runtime activation,
provider/ASR call, application/staging database access or deployment is added.

| Finding | Resolution and evidence |
| --- | --- |
| R-01: possible expensive map SQL | Remains a public-activation gate, not a demonstrated slowdown. `VERIFIED_MAP_QUOTA.md` now specifies the representative dataset, operator-approved budgets, zoom/density matrix, probe/aggregate EXPLAIN ANALYZE BUFFERS, p50/p95/p99, resource and cancellation/concurrency measurements. Dense functional test records synthetic timings only. No representative capacity/SLO claim or invented production budget. |
| R-02: dense map coverage | Full PostGIS regression seeds 303 actual listings/sources/projections/proofs, one incompatible hard match, then checks 0/299/300/301/302 valid candidates at zoom 8/12/13/21. Includes inclusive corner cells, center cell, exact marker IDs/cluster counts and compatible promotion. Invalidates 101 sources, hides 100 rows and removes 50 proofs after initial results; alternating/concurrent reads recheck current data under the same intent. |
| R-03: old PR statuses | #392–395 are merged into main. #395 landed on 2026-10-27 through e50f96a5f62d0989d9d91c35c001ca35fd6db445 with these corrections. #396 now targets main and is the next owner review checkpoint; #397–400 remain dependent drafts. |
| R-04: incorrect API source lines | Regenerated all 143 operations with the existing AST generator. Stale output after earlier HTTP-policy changes caused the mismatch. Source lines now refer to actual handler definitions, including all four new routes. |
| R-05: duplicate compilation | Private `_verified_intent_predicate` accepts the plan compiled once by cards. Shared public `verified_intent_predicate` retains its safe intent-to-plan contract for maps/later consumers. Existing card regression now also asserts exactly one compilation and unchanged `pets` reason code for both rental modes. |
| R-06: HTTP negative coverage | Added direct foreign/missing/expired result metadata/result map/session map, guest/auth isolation, stale version, CSRF, injected semantics/identity, invalid bounds/ranges/zoom and strict version tests. Errors assert exact private detail and no-store. Quota rejects absent/forged/expired guests and blocked auth; repeated quota reads leave row count and session expiry/updated_at unchanged. Coordinate ordering is validated in the body model to return private 422 consistently instead of handler-time 400. |
| R-07: hash semantics | Documented intent identity versus live marker freshness, separate request snapshots and viewport sequencing/cancellation. Source/proof/publication/TOP changes may change map data with the same intent hash. No API revision/snapshot semantics were invented. |

All ten final-head workflows for corrected #395 (`e68a47e8ab1571309e89be721d61e60aefc7dc56`)
passed before merge. The dense and negative HTTP cases ran in the combined
PostGIS and production integration jobs. The subsequent #396 main-target
[production audit](https://github.com/antony502189-max/Ttest/actions/runs/40640709869)
also passed with these backend corrections. Synthetic JUnit timing properties
remain diagnostic evidence; functional assertions are not a load test.
No migration/dependency/manual-map SQL logic was changed by these corrections.

## Recheck against the supplied review — 2026-10-28

The supplied report reviews `37f78e266369736203bfd947e393ded27a105b38`,
before the fixes merged in #395. Rechecking the current implementation confirms
R-02 and R-05–R-07 remain implemented. Regenerating the API inventory on the
current source produces no difference (143 operations), confirming R-04.
The process-status text is refreshed above for R-03 after #395's merge.

R-01 is still **open**, not resolved by those successful checks. Closing it
requires a representative catalog profile and accepted numeric latency,
resource and concurrency limits, followed by recorded SQL plans and measured
results. None are inferred from the synthetic functional fixture. Until these
inputs and measurements are recorded, the activation gate remains open.
No application or staging database, provider, crawler or public runtime is
used by this recheck.
