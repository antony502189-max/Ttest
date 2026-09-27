# Navigation and page performance audit

Baseline: `origin/main` at `f120b54`. The branch also incorporates the exact map-to-detail change from open PR #248 (`4b1aa3e`, `53f3a1b`) before the changes below. The original navigation inventory was made by searching `navigate(`, `Link`, `window.location`, `location.hash`, `history.pushState`, `history.replaceState`, `history.back`, `CustomEvent`, `replace: true`, and `URLSearchParams` across `src`.

## Navigation inventory

| Source | User action | Previous destination and mechanism | Expected destination | Defect and disposition |
| --- | --- | --- | --- | --- |
| `mobile-app-v2.tsx` | Home search | `/buscar` via router push | Results with search URL | Correct push; kept. |
| `mobile-search-results-v2.tsx` | Results back arrow | Hard-coded `/` push | Actual previous screen, or `/` for a direct link | Fixed with `useAppBack`. |
| `mobile-search-results-v2.tsx` | Results to map | `/buscar?vista=mapa` via router push | Map preserving URL filters | Kept push. |
| `mobile-map-listings-layer.tsx`, `mobile-search-results-v2.tsx` | Map preview to internal detail | Custom event that opened the general results list and scrolled to a card | `/habitacion/:id` via router push | Incorporated PR #248; removed the obsolete event listener. External listings still use their source URL. |
| `mobile-app-v2.tsx` | Map back arrow | Hard-coded `/?panel=ubicacion` push | Previous list/location screen, or list fallback | Fixed with `useAppBack`. |
| `mobile-app-v2.tsx` | Map camera change | Component-only map state | Current map URL | Camera is saved with `replace` because dragging or zooming is an adjustment to the same map screen. |
| `SearchPage.tsx` | Desktop map viewport / polygon | Local map bounds, polygon replacement | Shareable search URL and progressive Back | Bounds and polygon now enter the URL; map interaction adjusts the current map entry. |
| `SearchPage.tsx`, `mobile-search-results-v2.tsx` | Filter and sort change | Several `replace` updates | Back to prior visible search state | User choices now push; canonical parameter cleanup still replaces. |
| `ListingPage.tsx` | Detail back arrow | Fixed results route | Actual map/results/detail source, or results fallback | Fixed with `useAppBack`. |
| `AccountPages.tsx`, `ListingEditPage.tsx`, `ListingCreatePage.tsx`, `ProfilePage.tsx` | Account, edit, publish back arrows | Fixed menu or listing route | Actual prior route, safe fixed fallback for direct links | Fixed with `useAppBack`. |
| `UnifiedAuthPage.tsx`, `mobile-publication-gate.tsx` | Auth and protected publication | Mixed fixed redirects | Preserve forward intent; replace transient auth/canonical redirects | Reviewed and updated back controls; gate cleanup uses replace. |
| `moderation-gate.tsx` | Restriction back arrow | Raw `history.back()` | Prior route or safe fallback | Fixed with `useAppBack`. |
| `App.tsx` | Any route transition | Global scroll-to-top effect | Restore on Back/Forward; top on new route | Replaced with key-based `ScrollRestoration`. |
| `mobile-drawn-zone-search-navigation.ts` | Finish drawing | Direct document hash mutation | Router navigation | Removed; route update uses `navigate`. |

`Link` navigation in header, footer, cards, bottom tabs, and desktop results already pushed a router history entry. `window.location.assign` is used for telephone or external-source behavior, not internal route transitions. The remaining `replace` uses serve canonicalization, redirects, transient gate cleanup, or map camera updates.

## History and state policy

React Router `HashRouter` remains the sole internal route owner. `useAppBack` uses React Router's `navigate(-1)` when the current history entry has a prior router index; direct deep links use a safe fallback with `replace`. Bare-root entry is canonicalized to `/#/` before the router mounts. Search query, rental mode, filter parameters, sorting, polygon, map bounds, and map camera are represented in the hash URL. Map camera and polygon edits update the current map entry, while filter and sorting choices push entries. Search requests ignore presentation-only URL parameters, abort superseded requests, and keep camera movement from triggering another listing fetch. Scroll positions are stored per router location key for the document and mobile results pane; POP restores position and focus to the main content.

## Performance baseline and changes

Measurements use local mock-mode production builds from the same `origin/main` base and the changed branch, Vite output, and a single Playwright browser pass at each representative route. Browser timings vary between runs and are descriptive, not regression thresholds. Image bytes are transferred response bytes. The deterministic test Google Maps SDK has no real map network timing, so real Google Maps initialization time is not measured.

| Measure | Before | After | Interpretation |
| --- | ---: | ---: | --- |
| Production main JS, gzip | 252.46 kB | 224.21 kB | 11.2% smaller shared chunk. |
| Mock production main JS, gzip | 144.60 kB | 109.46 kB | 24.3% smaller shared chunk. |
| Mobile home route JS bytes | 291,783 | 288,547 | 1.1% less JS; requests 27 → 50. |
| Desktop home route JS bytes | 334,181 | 309,482 | 7.4% less JS; requests 43 → 60. |
| Mobile results route JS bytes | 291,783 | 299,829 | 2.8% more JS; requests 36 → 60. |
| Desktop results route JS bytes | 348,486 | 323,208 | 7.3% less JS; requests 53 → 67. |
| Mobile map route JS bytes | 294,211 | 314,418 | 6.9% more JS; requests 27 → 59. The map SDK readiness was not measured by this route probe. |
| Mobile detail route JS bytes | 341,079 | 316,156 | 7.3% less JS; requests 44 → 62. |
| Mobile my listings route JS bytes | 349,131 | 325,751 | 6.7% less JS; requests 45 → 63. |
| Mobile publish route JS bytes | 344,973 | 329,140 | 4.6% less JS; requests 47 → 66. |

The same pass transferred 1,048,062 → 762,867 image bytes on mobile results (27.2% less) and 1,247,203 → 1,075,503 on desktop results (13.8% less), after removing speculative next-photo preloads from result cards. Mobile detail transferred 450,145 image bytes in both builds. Home and map transferred no listing images in the measured state. The higher JS request counts are the cost of splitting the shared JS into route modules. Single-run visible-content and LCP timings were mixed: mobile results visible-content changed 2,561 → 1,795 ms and LCP 1,332 → 1,212 ms, while mobile detail visible-content changed 2,232 → 2,915 ms and LCP 1,212 → 1,616 ms. These observations are not evidence of a reliable timing win. CLS and INP/TBT were not measured reliably; no values are claimed. The architectural map-loading tests establish when map code is requested rather than a real Google Maps network initialization time.

The original shared bundle included mobile map components and the Google Maps loader path on unrelated screens. Mobile shell, map marker layer, results, and publication gate now load for their own screens. Publication location enhancers remain eagerly imported because the publication form emits mount-time events that they must receive; their Google Maps calls load on demand. Owner listing routes no longer preload on idle; the account route preloads on account-menu intent. Focus and visibility refreshes now check the catalog version before fetching the catalog again, coalesce simultaneous version checks, and wait for initial hydration instead of racing it. Search request cancellation prevents stale responses from replacing newer search state. Static CSS import order remains stable to preserve approved visual snapshots.

React Profiler render counts were not captured in the production browser pass. The map's marker construction is now tied to the actual marker geometry and stable initial-camera decision, which prevents camera URL updates from rebuilding every marker; no broad memoization changes were made without a measured render bottleneck.

### Remaining scale constraint

Production `RemoteAppProvider` still calls `getStablePublicCatalog()`, which calls `getPublicListings()` and `fetchAllSearch()` repeatedly until the entire catalog is downloaded. Desktop search also calls `searchPublicListings()` via `fetchAllSearch()`, while mobile list and map derive their items from the context catalog. This does not satisfy a Spain-wide bounded or viewport-aware loading model. It requires a coordinated API/UI pagination and map-viewport design, including accurate totals, favorites lookup, and map marker coverage. A hard cap on the existing method would silently hide listings, so this branch does not claim to have solved that scaling requirement. Production listing snapshots are already excluded from localStorage (`readListings` and persistence run in mock mode only).

## Validation

Navigation regression coverage exercises mobile Home → Results → Map → Detail with browser Back and Forward, URL reload, direct detail fallback, list scroll restoration, account edit flow, and desktop results → detail. Performance regression coverage checks that Home and list mode do not request map implementation modules and that map mode does. Full test and final build results are recorded in the PR description.
