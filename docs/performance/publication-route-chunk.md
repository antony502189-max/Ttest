# Publication route enhancer chunk

## Change

The application layout previously imported `PublishLocationEnhancer` and `PublishAddressLifecycle` statically even though it mounted them only on `/publicar` and `/editar` routes. Their location/address dependencies and stylesheet therefore entered the first shared JS and CSS request on unrelated routes. The layout now lazy-loads a small `PublishRouteEnhancers` wrapper only for those routes. `PublishOccupancySync` remains mounted as before because it has application-wide listing synchronization behavior.

The behavior check verifies that the home route does not request the new route chunk or its stylesheet and that a direct publication route requests both before the existing unauthenticated redirect. The publication flow suite also passes against the candidate.

## Build evidence

Both builds use the same `63ca366ca97f51558b3db4e1778ef24938d474ad` base, production Vite build settings, dependency lockfile, and browser. This comparison is built from source maps and uses Node zlib level 6 for JS/CSS transfer estimates. It is a local build comparison, not a production network measurement.

| Asset | Main baseline | Candidate | Change |
| --- | ---: | ---: | ---: |
| Entry JS, raw | 776,118 B | 738,521 B | -37,597 B |
| Entry JS, gzip estimate | 252,047 B | 240,692 B | -11,355 B |
| Entry CSS, raw | 369,729 B | 365,037 B | -4,692 B |
| Entry CSS, gzip estimate | 64,002 B | 63,070 B | -932 B |
| Initial JS+CSS, gzip estimate | 316,049 B | 303,762 B | -12,287 B |
| Publication-only JS, raw | none | 37,146 B | route-only |
| Publication-only CSS, raw | none | 4,693 B | route-only |

The four enhancer modules move out of the entry chunk and into `publish-route-enhancers-*.js`; their stylesheet moves into the matching dynamic CSS chunk. The route chunk still must be downloaded by people who open publication or edit forms.

## Browser measurement

`scripts/measure-route-performance.mjs` records three repeated cold-cache-disabled and cache-primed navigation samples against a main baseline build and this candidate under four deterministic local browser profiles. `scripts/serve-build-for-measurement.mjs` serves each build with immutable caching for fingerprinted files and ETag revalidation for stable files. The raw samples are stored in `artifacts/performance/route-critical/`.

Both builds use `VITE_ENABLE_MOCK_MODE=1`; the harness replaces external Unsplash image URLs with a tiny data URI before requests begin. This makes the comparison repeatable but does not represent production catalog/API traffic, production images, server latency, or user traffic. There is no browser-visible evidence of a stable FCP/LCP improvement, so this change claims bundle transfer reduction only.

| Profile | Cold JS, before → after | Cold CSS, before → after | Cold total, before → after | Warm cache hits, before → after | Warm JS/CSS transfer, before → after |
| --- | ---: | ---: | ---: | ---: | ---: |
| Desktop | 973,237 → 939,329 B | 382,862 → 378,170 B | 1,391,707 → 1,353,281 B | 61/62 → 62/63 (60/61 hashed assets) | 0/0 → 0/0 B |
| Mobile | 952,290 → 918,671 B | 376,697 → 372,005 B | 1,447,343 → 1,409,206 B | 58/60 → 59/61 (57/58 hashed assets) | 0/0 → 0/0 B |
| 4G | 952,290 → 918,671 B | 376,697 → 372,005 B | 1,441,435 → 1,403,124 B | 58/60 → 59/61 (57/58 hashed assets) | 0/0 → 0/0 B |
| Constrained 4G + CPU ×4 | 898,655 → 864,875 B | 372,850 → 368,158 B | 1,271,505 → 1,233,033 B | 47/59 → 49/60 (46/48 hashed assets) | 44,969/3,847 → 44,314/3,847 B |

Browser cache hits are verified by CDP `requestServedFromCache`/disk-cache events. With the local server, HTML uses `no-cache` plus ETag: a direct conditional request returned 304. Warm JS/CSS response bytes were zero in the first three profiles; constrained emulation still transferred about 48 KB of script/style resources. Warm reused decoded resource bytes were 1.23–1.42 MB depending on the profile. Cold total response sizes include resources used on the home route, not only the entry. CSS/JS bytes are raw in this mock-mode experiment, not gzip. Cold FCP/LCP varies across profiles and is not an acceptance claim.

The local static server reproduces the cache header semantics in PR #299 but does not perform compression or represent production network paths. These are synthetic browser-cache measurements; they do not claim production warm-visit latency.

## Reproduction

Build main at `63ca366ca97f51558b3db4e1778ef24938d474ad` and this branch with `VITE_ENABLE_MOCK_MODE=1` and `VITE_GOOGLE_MAPS_TEST_SDK=1`. Serve the two `dist` directories with `scripts/serve-build-for-measurement.mjs` on ports 4174 and 4175, then run:

```powershell
node scripts/serve-build-for-measurement.mjs --root=C:\path\to\main\dist --port=4174
node scripts/serve-build-for-measurement.mjs --root=C:\path\to\candidate\dist --port=4175
```

In a third terminal, run:

```powershell
node scripts/measure-route-performance.mjs --baseline=http://127.0.0.1:4174 --candidate=http://127.0.0.1:4175 --runs=3 --profile=desktop --output=desktop.json
```

Use `--profile=mobile`, `--profile=4g`, or `--profile=constrained` for the other profiles. The script primes a separate browser context before measuring warm navigation and records cache hits. The server returns 304 for revalidated stable files and long-lived immutable headers only for fingerprinted files. The script uses Chromium via Playwright; set `PLAYWRIGHT_EXECUTABLE_PATH` if the browser is installed outside Playwright's default cache.

## Validation

- Candidate production build, typecheck, and lint passed (lint has four existing warnings).
- Dependency and production bundle security policies passed.
- Warm-cache hit verification passed against the measurement server: fingerprinted assets were reused, and an ETag conditional request for the stable entry returned 304.
- Production-preview lazy-load regression passed.
- Publication flow suite passed: 15 passed, 0 failed.
- The broad `npm run test:e2e` run was stopped after more than 15 minutes without a reporter summary; it is not counted as a pass.
- `tests/visual-parity.spec.ts` could not compare visuals because this checkout has no committed Playwright snapshot baselines. The spec wrote local actual screenshots and failed each comparison for the missing baseline; no baseline image was changed.
- An independent paired screenshot comparison in mock mode found exact pixel equality against main for mobile home, mobile search, mobile publication, and desktop publication (`390×844` and `1440×900`). The generated images are retained outside the repository at `C:/Users/hamez/.codex/audits/phase2-route-critical/visual-pair/`; they are not substitutes for the full approved visual matrix.
