# Admin Listings performance

Baseline: main `7f0feb8bd4cc649a52afc92b9bfb6153e16ce360`. No CSS, dependencies, schema migrations or production infrastructure changes.

`src/api/admin.ts::drainAdminPages` waits for every 200-row page before resolving. `src/pages/AdminPage.tsx::visibleListings.map` then mounts the entire collection. These are confirmed by the synthetic browser and PostgreSQL benchmarks; listing restrictions are already batched, with no per-row restriction query.

The Listings view now requests 50 rows, continues via the existing `(createdAt, id)` cursor when the last row approaches the viewport, and searches/filters the complete dataset on the server. `displaySearch` preserves the previous literal title/owner/area substring matching, including whitespace and SQL wildcard characters. Legacy API search remains compatible. Related user/report views retain their complete collections. New requests cancel obsolete searches; mutation protection lasts only for an in-flight page, so subsequent requests accept fresh server state. External abort signals now retain the API timeout budget.

Measured once per initial/repeated visit, using Chromium, Vite development React profiling, 1440×900, synthetic responses with 100 ms latency per request. Browser numbers are local measurements, not production timings. Full raw results, heap usage, long tasks, commit durations and SQL measurements are in `admin-performance-results.json`.

| Listings | First usable content before | After | Listing requests before / after |
|---|---:|---:|---:|
| 100 | 704 ms | 578 ms | 1 / 1 |
| 1,000 | 4,261 ms | 673 ms | 6 / 1 |
| 5,000 | 21,038 ms | 735 ms | 26 / 1 |
| 10,000 | 33,859 ms | 910 ms | 51 / 1 |

At 10,000 rows, initial heap usage fell from 561 MB to 31 MB and initial rendering is limited to 50 rows. The independent local PostgreSQL benchmark reduced collection time from 2,133 ms to 38 ms and SQL statements from 101 to 2. Individual SQL execution was not materially accelerated: eliminating the full traversal produces the reduction. No new index is justified by this evidence.

Limitations: initial Users loading is substantially unchanged. Small cached collections can be slower on repeated visits/search because the new search makes a fresh request with a 150 ms typing debounce. Scrolling through the entire dataset eventually accumulates all visited rows; no virtualization or design changes were introduced. The unidentified “FaceFL/Failed…” production error could not be identified without an authorized production session; a read-only visit redirected to login with no page errors or failed requests.

Local validation: frontend typecheck, existing lint/i18n guard, production build, bundle/dependency security; backend Ruff and mypy; 658 backend unit tests passed, 3 skipped; 228 PostgreSQL integration tests passed, and the remaining Redis test passed after provisioning a dedicated local Redis instance. All 11 new PostgreSQL pagination/search/authorization cases passed. Existing admin Playwright tests: 25 passed. New admin loading tests: 8 passed; opt-in benchmark/capture suite: 24 passed. Visual comparison includes all six admin tabs, Spanish/Russian/English and widths 320/390/768/1440. Exact latest comparison results are recorded in the raw results file.

Reproduce browser measurements with `ADMIN_BENCHMARK_PHASE=before` against the baseline checkout, then `ADMIN_BENCHMARK_PHASE=after` against this branch, using `npm run test:admin-performance`. Keep dependencies and fixtures identical. The database benchmark requires a migrated, explicitly isolated local `ttest_adminperf_test` database. Run `python scripts/benchmark-admin-listings.py` in each phase, then `python scripts/compare-admin-screenshots.py <before-directory> <after-directory>`.

CI is launched through the PR, including Production audit (with the new admin suite), Full audit and existing required checks. At the user's request, work stops after launch without waiting for CI, merging or deploying.
