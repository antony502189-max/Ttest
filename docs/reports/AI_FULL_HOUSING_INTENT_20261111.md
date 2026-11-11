# S2.1 / S3 / S4.1 / S6: composite housing intent, 11 November 2026

Owner explicitly replaced the monthly-only product restriction with full housing requirements. The existing shared Criteria/IntentPatch, DecisionDeepSeekIntent, sessions/ledger, typed matcher, proofs, cards/map and voice execution remain the implementation. This is an increment of the existing application, not a new project or acceptance stand.

## Source behavior

The housing input boundary consumes the complete request, creates only schema-generated housing conditions, and sends that minimized patch plus current typed criteria to the existing metered model. Raw request words, identity, history, listing data and contacts are excluded from the provider payload. Unknown clauses, incomplete party composition, uncertain locations/units, contradictions and unsupported vocabulary request clarification before provider IO. Patch validation compares the complete merged candidate, preserving unrelated conditions. Adults/children can be changed individually once their composition is known; amenities and other pet species survive additions. Text and local ASR use the same parser instance. Explicit monthly/nightly/weekly prices are never converted or used to infer rental mode.

Coverage checks require known current facts for every hard requirement before a zero-match operation can debit. Known explicit denial counts as coverage, but cannot match. Missing, legacy, conditional or conflicting facts do not become a meaningful empty result. The pre-provider check and SQL candidate check are independent. Display uses official location names and supported amenity names.

Existing public source data from the same thirteen IDs is enriched conservatively: official city/source-slug mapping, explicit /habitacion/ route category, complete standalone phrases and exact list labels inside seccionesFichaAnuncio + contCaract/contTwocols. Navigation, filters, related ads, hidden/disabled elements, partial clauses and conditional prose cannot assert a positive property fact. Full HTML/source prose is minimized in the host-to-backend pipe; only recognized evidence enters the isolated normalized snapshot. Refresh publication/fencing, freshness, tombstones, proof preparation and currentness guards remain mandatory. No source crawl/cohort expansion or legacy card-default promotion occurs.

## Checks so far

- Current origin/main 6f089919 and GitHub merged PR414 independently verified. Existing clean worktree reused; old root checkout not switched/reset/stashed.
- 173 focused backend checks passed before the final additional date/zone/HTML cases; final housing unit cases: 49 PASS. Ruff and TypeScript passed; targeted mypy: six source files pass (untyped-body limitation remains visible).
- Public desktop/mobile mocked browser contracts: 4 PASS. Existing pilot/voice contracts: 26 PASS after updating the intentionally changed copy and input scope. First run retained 4 expected assertion failures (old copy / duplicate text locator), then corrected assertions passed. Missing Playwright browser startup was retained; installed Chrome was used.
- PostgreSQL typed/refresh run: 92 PASS, six harness failures because /deploy was not mounted. No product assertion failed in that run. Corrected focused run with /deploy mounted: 7 PASS / 81.39s, including all six producer/tombstone cases and a new composite model-boundary -> SQL -> refinement -> unknown-party -> map -> replay/old-result recovery scenario. Separate temporary PG container has no production data/provider/network access and is removed after validation.
- Actual thirteen source snapshots, read-only / provider0 / database writes0: accommodation13, geography13, deposit13, bills12, furnished5, balcony1; four amenity facts (Wi-Fi/lift), pets deny13 and couples deny13. First conservative text-only scan (geography1, no amenities) is retained and superseded by inspected structured source labels and exact source-slug mapping, not by treating defaults as facts.

## Release and remaining gates

No new deployment or paid call has occurred at this checkpoint. Primary remains061474ec, isolated backend90b68f36. Full housing mode requires explicit housing-v1 runtime selection and matching public-nonpersonal-housing-criteria.v1 operational scope. Existing lifetime50 calls/$1, original binding/journal/keys and expiry2026-11-11T20:59:59Z remain unchanged; no reset/refund/reseed.

Next: exact-source CI/build, actual-image offline ASR/composite/data checks, then authorized staged rollout and real provider-backed text/voice, individual refinements, map/reload and design comparison on the site. Source readiness, test validation and actual release must be recorded separately.

S4.2 saved-search creation after registration and S4.3 notifications remain mandatory and OPEN, alongside party/free-place/date coverage, broader language/human ASR, standing quality, provider/account/privacy, p95/capacity/ISSUE-004 and full-release gates. None of S0–S7 or A1–A12 is declared fully complete by this increment.

## 12 November: explicit extension and candidate verification
Owner explicitly approved extending the same cumulative50/$1 spending window until2026-11-12T20:59:59Z. Existing attempts/binding/journal must be retained. Only the full-housing scope gains this explicit date; old approval scopes keep their prior expiry. Focused extension/journal/expiry tests24PASS. PR415 f06383a2 has13SUCCESS/2conditionalSKIP; full local unit1930PASS/16skip. Candidate imagee2b4012ab164154b6e16def27a0c30667d13d36f31443f2507170a44d2c8ef51 built from exact source; four actual-image offline ASR samples PASS4.042–6.25s/provider0. No new paid call or deployment yet at this checkpoint.
