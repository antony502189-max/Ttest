# Performance optimization report

Baseline: `1a9c76bad9c8094a59ce912a1b8582e3493b8d77` plus the existing PR #111 commit `f8ffc4878e12b0a0aa7343c8286af6bb582aa581`.

Measurements use the production Vite build in this workspace. Asset sizes are exact emitted-file sizes; build timing is one warm local run, so it is reported as indicative rather than a median.

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Initial entry JS, raw | 625,868 B | 548,927 B | -76,941 B (-12.3%) |
| Initial entry JS, gzip | 211,258 B | 187,324 B | -23,934 B (-11.3%) |
| Global CSS, raw | 324,326 B | 294,953 B | -29,373 B (-9.1%) |
| Global CSS, gzip | 55,990 B | 50,902 B | -5,088 B (-9.1%) |
| Emitted JS/CSS chunks | 42 | 64 | +22 async chunks |
| Indicative production build | 14.7 s | 13.3 s | -1.4 s (not medianed) |

## Async mobile output

The desktop entry no longer imports mobile shell code. Vite emits the code only behind route-and-mobile-viewport gates:

| Asset | Raw | Gzip |
| --- | ---: | ---: |
| `mobile-app-v2` JS | 48,560 B | 15,973 B |
| `mobile-search-results-v2` JS | 20,190 B | 6,731 B |
| `mobile-publication-gate` JS | 4,040 B | 1,710 B |
| Mobile-only CSS (three entry CSS files) | 29,647 B | 8,048 B |

## Backend query changes

Result projection now uses PostGIS `ST_X`/`ST_Y`, removing `ST_AsGeoJSON` serialization and Python `json.loads` while preserving numeric public and exact coordinates. On a disposable PostGIS 3.4 database with 30,000 published listings, returning coordinates alone took 48.21 ms with `ST_AsGeoJSON` and 28.05 ms with `ST_X`/`ST_Y` (41.8% lower); average coordinate payload text fell from 58.8 B to 37.2 B (36.7% lower). Both plans read the same 1,287 shared buffers.

The proposed lightweight COUNT relation was measured and rejected. PostgreSQL pruned the unused old response projection below `COUNT(*)`; equivalent 30,000-row plans used the same 1,288 shared buffers and took 21.75 ms (old) versus 22.84 ms (new). The code therefore retains the original COUNT shape rather than claiming a non-existent win.

Integration cleanup now excludes PostGIS's `spatial_ref_sys` metadata table. The old cleanup truncated it, causing all later radius searches to fail with `Cannot find SRID (4326) in spatial_ref_sys`.

## Validation

- `npm run lint` - passed (four pre-existing exhaustive-deps warnings in `App.tsx` and `moderation-gate.tsx`)
- `npm run typecheck` - passed
- `npm run build` - passed
- `npm run test:bundle-security` - passed
- `npm run test:security` - passed
- backend projection tests - 3 passed
- backend critical-flow and moderation tests - 32 passed
- backend count/filter equivalence test before reverting the no-op COUNT change - 4 passed, including bbox, radius, and polygon filters
- targeted Playwright `apk-parity` desktop route check - passed; direct browser exercise of the contact-to-auth-to-map flow passed with `map-search` and the test map canvas present

The PostGIS migration chain was run successfully through `0033_admin_moderation` against the disposable database. The full frontend and backend collections were attempted, but their runner connection exited without a final result after starting; they remain CI-required rather than marked passed.

## Considered and rejected

- No `CustomerFeedbackFixes`, `ModerationGate`, or `PublishOccupancySync` changes: their behavior is security- and interaction-sensitive, and there was no isolated measured benefit sufficient to justify risk.
- No media aggregation rewrite or database indexes: the representative PostGIS plans did not show an evidence-backed index need for the exercised query.
- No production mock-isolation plugin change: the two-entry source-ID check is security-critical and profiling did not demonstrate a measurable build gain.
