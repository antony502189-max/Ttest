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

`search_public()` still executes exactly two statements (COUNT plus page results). The COUNT statement now uses the same visibility/filter relation but projects only `listings.id`; it no longer includes `ST_AsGeoJSON`, the correlated media `array_agg`, user response columns, or the full listing projection. Result projection now uses PostGIS `ST_X`/`ST_Y`, removing `ST_AsGeoJSON` serialization and Python `json.loads` while preserving numeric coordinates.

PostgreSQL/PostGIS plan timing is unavailable in this workspace because Docker Desktop is not running, so no latency or plan-cost claim is made. SQL compilation and focused response/count regression tests prove the projection exclusions and public/exact coordinate values.

## Validation

- `npm run lint` — passed (four pre-existing exhaustive-deps warnings in `App.tsx` and `moderation-gate.tsx`)
- `npm run typecheck` — passed
- `npm run build` — passed
- `npm run test:bundle-security` — passed
- focused backend regression tests — 25 passed
- focused mobile Playwright checks — 12 canonical flows passed before map initialization test runs stalled without a test failure; the desktop responsive route check passed.

The full frontend suite and PostGIS query-plan/migration validation remain required in CI or a Docker-enabled environment.

## Considered and rejected

- No `CustomerFeedbackFixes`, `ModerationGate`, or `PublishOccupancySync` changes: their behavior is security- and interaction-sensitive, and there was no isolated measured benefit sufficient to justify risk.
- No media aggregation rewrite or database indexes: no representative PostGIS database was available for `EXPLAIN (ANALYZE, BUFFERS)` evidence.
- No production mock-isolation plugin change: build time was not profiled sufficiently to preserve its security invariant with confidence.
