# Performance optimization report

Baseline: `1a9c76bad9c8094a59ce912a1b8582e3493b8d77` plus the existing PR #111 commit `f8ffc4878e12b0a0aa7343c8286af6bb582aa581`.

Measurements use production Vite builds. The original local measurement recorded exact emitted-file sizes. After CI exposed a CSS-order regression caused by async component CSS, the three base mobile stylesheets were restored to the synchronous entry in their original cascade position while the mobile JavaScript remained lazy. The final CSS figures below use the CI Vite report and are therefore rounded to the precision Vite prints.

| Metric | Before | Final | Delta |
| --- | ---: | ---: | ---: |
| Initial entry JS, raw | 625,868 B | ~548.8 kB | ~-12.3% |
| Initial entry JS, gzip | 211,258 B | ~188.4 kB | ~-10.8% |
| Global CSS, raw | 324,326 B | ~321.3 kB | ~-0.9% |
| Global CSS, gzip | 55,990 B | ~55.5 kB | ~-0.8% |
| Indicative production build | 14.7 s | ~13 s class locally; ~1 s Vite transform/render in CI after typecheck | indicative only |

The principal frontend gain is therefore JavaScript, not CSS. The initial desktop entry keeps the mobile shell implementation out of the synchronous JS graph, while the base mobile CSS remains synchronous so the established hardening and white-theme overrides keep their original cascade semantics.

## Async mobile JavaScript

The desktop entry no longer synchronously imports the mobile shell components. Vite emits the following JavaScript behind route-and-mobile-viewport gates (representative final CI build):

| Asset | Raw | Gzip |
| --- | ---: | ---: |
| `mobile-app-v2` JS | ~48.5 kB | ~16.0 kB |
| `mobile-search-results-v2` JS | ~20.2 kB | ~6.8 kB |
| `mobile-publication-gate` JS | ~4.0 kB | ~1.7 kB |

The base `mobile-app-v2.css`, `mobile-search-results.css`, and `mobile-publication-gate.css` are intentionally part of the synchronous stylesheet graph. An earlier attempt to make them async changed stylesheet insertion order: late base mobile rules overrode `white-theme.css`, hardening rules, approved card geometry, and accessibility colors. CI correctly caught that regression through visual, white-theme, and Axe tests. The final implementation keeps JS lazy while restoring the original CSS cascade instead of accepting changed screenshots.

## Backend query changes

Result projection now uses PostGIS `ST_X`/`ST_Y`, removing `ST_AsGeoJSON` serialization and Python `json.loads` while preserving numeric public and exact coordinates. On a disposable PostGIS 3.4 database with 30,000 published listings, returning coordinates alone took 48.21 ms with `ST_AsGeoJSON` and 28.05 ms with `ST_X`/`ST_Y` (41.8% lower); average coordinate payload text fell from 58.8 B to 37.2 B (36.7% lower). Both plans read the same 1,287 shared buffers.

The proposed lightweight COUNT relation was measured and rejected. PostgreSQL pruned the unused old response projection below `COUNT(*)`; equivalent 30,000-row plans used the same 1,288 shared buffers and took 21.75 ms (old) versus 22.84 ms (new). The code therefore retains the original COUNT shape rather than claiming a non-existent win.

Integration cleanup now excludes PostGIS's `spatial_ref_sys` metadata table. The old cleanup truncated it, causing all later radius searches to fail with `Cannot find SRID (4326) in spatial_ref_sys`.

## Validation

Local targeted validation covered:

- `npm run lint`
- `npm run typecheck`
- `npm run build`
- `npm run test:bundle-security`
- `npm run test:security`
- backend projection tests: 3 passed
- backend critical-flow and moderation tests: 32 passed
- backend count/filter equivalence before reverting the no-op COUNT rewrite: 4 passed, including bbox, radius, and polygon filters
- PostGIS migration chain through `0033_admin_moderation`
- direct browser contact -> auth -> map flow

CI additionally exposed and drove fixes for backend Ruff import hygiene and the lazy-CSS cascade regression described above. Final acceptance is determined only by all required GitHub workflows passing on the exact final PR head.

## Considered and rejected

- No `CustomerFeedbackFixes`, `ModerationGate`, or `PublishOccupancySync` changes: their behavior is security- and interaction-sensitive, and there was no isolated measured benefit sufficient to justify risk.
- No COUNT rewrite: measured query plans showed no benefit.
- No media aggregation rewrite or database indexes: representative PostGIS plans did not show an evidence-backed need.
- No production mock-isolation plugin change: the source-ID check is security-critical and profiling did not demonstrate a measurable build gain.
- The now-unused aggregate `radix-ui` package is not removed in this performance PR: runtime imports were eliminated, and lockfile-only dependency housekeeping would add unrelated churn without changing the shipped bundle.
