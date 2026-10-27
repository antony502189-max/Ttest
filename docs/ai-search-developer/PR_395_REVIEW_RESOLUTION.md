# PR #395 review resolution — 2026-10-28

Review source: owner's `PR_395_FULL_CODE_REVIEW_RU.md`, reviewed head
`37f78e266369736203bfd947e393ded27a105b38`. No public runtime activation,
provider/ASR call, application/staging database access or deployment is added.

| Finding | Resolution and evidence |
| --- | --- |
| R-01: possible expensive map SQL | Remains a public-activation gate, not a demonstrated slowdown. `VERIFIED_MAP_QUOTA.md` now specifies the representative dataset, operator-approved budgets, zoom/density matrix, probe/aggregate EXPLAIN ANALYZE BUFFERS, p50/p95/p99, resource and cancellation/concurrency measurements. Dense functional test records synthetic timings only. No representative capacity/SLO claim or invented production budget. |
| R-02: dense map coverage | Full PostGIS regression seeds 303 actual listings/sources/projections/proofs, one incompatible hard match, then checks 0/299/300/301/302 valid candidates at zoom 8/12/13/21. Includes inclusive corner cells, center cell, exact marker IDs/cluster counts and compatible promotion. Invalidates 101 sources, hides 100 rows and removes 50 proofs after initial results; alternating/concurrent reads recheck current data under the same intent. |
| R-03: old PR statuses | Documents #392/#393/#394 merged into main on 2026-10-27; #395 is the next review checkpoint. #396/#397 remain dependent. |
| R-04: incorrect API source lines | Regenerated all 143 operations with the existing AST generator. Stale output after earlier HTTP-policy changes caused the mismatch. Source lines now refer to actual handler definitions, including all four new routes. |
| R-05: duplicate compilation | Private `_verified_intent_predicate` accepts the plan compiled once by cards. Shared public `verified_intent_predicate` retains its safe intent-to-plan contract for maps/later consumers. Existing card regression now also asserts exactly one compilation and unchanged `pets` reason code for both rental modes. |
| R-06: HTTP negative coverage | Added direct foreign/missing/expired result metadata/result map/session map, guest/auth isolation, stale version, CSRF, injected semantics/identity, invalid bounds/ranges/zoom and strict version tests. Errors assert exact private detail and no-store. Quota rejects absent/forged/expired guests and blocked auth; repeated quota reads leave row count and session expiry/updated_at unchanged. Coordinate ordering is validated in the body model to return private 422 consistently instead of handler-time 400. |
| R-07: hash semantics | Documented intent identity versus live marker freshness, separate request snapshots and viewport sequencing/cancellation. Source/proof/publication/TOP changes may change map data with the same intent hash. No API revision/snapshot semantics were invented. |

Run backend Ruff/mypy/unit tests and all fresh final-head main-target CI before
marking this PR ready again. The dense and negative HTTP cases run in the
existing combined PostGIS and production integration jobs. Synthetic JUnit timing
properties are diagnostic evidence; do not treat functional assertions as a load
test. No migration/dependency/manual-map SQL logic is changed.
