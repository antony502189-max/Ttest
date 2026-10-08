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

`scripts/measure-route-performance.mjs` records three repeated cold-cache-disabled navigation samples against a main baseline build and this candidate under four deterministic local browser profiles. The raw samples are stored in `artifacts/performance/route-critical/`.

The app is served locally. API requests are stubbed to an empty JSON response and Unsplash images to a tiny SVG. This makes the comparison repeatable but does not represent catalog rendering, production images, server latency, or user traffic. There is no browser-visible evidence of a stable FCP/LCP improvement, so this change claims bundle transfer reduction only.

| Profile | Entry JS bytes, before → after | Entry CSS bytes, before → after | Total response bytes, before → after |
| --- | ---: | ---: | ---: |
| Desktop, cold | 339,628 → 327,402 | 68,262 → 67,330 | 438,496 → 425,338 |
| Mobile, cold | 333,687 → 321,430 | 66,987 → 66,055 | 514,028 → 500,839 |
| 4G, cold | 315,152 → 303,237 | 65,600 → 64,668 | 381,054 → 368,207 |
| Constrained 4G + CPU ×4, cold | 305,304 → 293,858 | 64,302 → 63,370 | 369,908 → 357,530 |

The reported totals include the page's observed requests under the mock fixture; the exact transfer total can vary with whether an image or lazy resource was requested before the sample was taken. The static entry JS/CSS deltas are stable across runs. The cold FCP/LCP samples have wide timing ranges under throttling and are not used as acceptance claims.

The preview server does not apply the Nginx immutable cache headers. The harness performs a second navigation with browser cache enabled but the result is labeled `repeat-cache-enabled`, not a validated warm-cache measurement. Production warm-cache results require exercising the relevant Nginx headers and are not claimed here.

## Reproduction

Build main at `63ca366ca97f51558b3db4e1778ef24938d474ad` into one output directory and this branch into another, serve them on ports 4174 and 4175, then run:

```powershell
node scripts/measure-route-performance.mjs --baseline=http://127.0.0.1:4174 --candidate=http://127.0.0.1:4175 --runs=3 --profile=desktop --output=desktop.json
```

Use `--profile=mobile`, `--profile=4g`, or `--profile=constrained` for the other profiles. The script uses Chromium via Playwright; set `PLAYWRIGHT_EXECUTABLE_PATH` if the browser is installed outside Playwright's default cache.

## Validation

- Candidate production build, typecheck, and lint passed (lint has four existing warnings).
- Dependency and production bundle security policies passed.
- Production-preview lazy-load regression passed.
- Publication flow suite passed: 15 passed, 0 failed.
- The broad `npm run test:e2e` run was stopped after more than 15 minutes without a reporter summary; it is not counted as a pass.
- `tests/visual-parity.spec.ts` could not compare visuals because this checkout has no committed Playwright snapshot baselines. The spec wrote local actual screenshots and failed each comparison for the missing baseline; no baseline image was changed.
