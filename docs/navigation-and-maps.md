# Map navigation, local history and geographic zones

## What the user sees

- **Never visited the results map:** default camera is `{lat:32.45,lng:-11.2,zoom:5.25}`, a deliberately broad Atlantic overview covering mainland Spain and Tenerife/Canary Islands.
- **Explored the map:** the last interacted-with geographic point is remembered in this browser. On a **fresh** return, the point resolves to the nearest deterministic **virtual 70 km-radius zone** and the map fits the entire **140 km diameter** on the current screen. The goal is predictable regional context, not restoring a tiny close-up.
- **No listing view required:** user drag/pan, wheel/pinch/zoom, marker selection and leaving by route change, page hide or close are considered by persistence logic. Merely mounting an untouched map is not exploration and must not overwrite the previous zone.
- **In-app Back from an advertisement:** the generated exact map camera can be restored within the same document/session. A newly loaded or refreshed map page must not mistakenly treat an auto-written URL camera as an explicit bookmark.
- **Named geographic selection or deep-link camera:** intentional query coordinates, a drawn zone or selected autonomous community can override the remembered anonymous zone. A selected region scopes **listings**, not just the visual camera.

The 70 km circles are virtual; **no circle overlays** are shown by this feature. This is separate from users drawing custom search polygons.

## Source of truth and math

`src/lib/map-visit-history.ts` exports:

- `FIRST_MAP_VIEWPORT`, `MAP_RECALL_RADIUS_KM = 70`, `MAP_VISIT_KEY = "112233:map-last-search-area:v2"`.
- `rememberMapViewport`: persists an explored point with a `savedAt` timestamp. Movements within the same resolved zone avoid needless rewrites.
- `readLastMapCenter`: validates browser storage, checks freshness, and snaps the point to `mapZoneForCenter`; invalid/unavailable storage yields no remembered camera.
- `mapZoneForCenter`: virtual **staggered hexagonal lattice**, nearest-center assignment with overlapping 70 km circles; row spacing `1.5×radius`, column spacing `√3×radius`. Coordinates in Spain/Canaries are covered without gaps for user recall.
- `viewportForRememberedArea`: spherical angular-distance and Web Mercator projections produce a zoom fitting the selected circle to the supplied width and height **without** the previous 20% safety padding or quarter-zoom rounding.
- History entries expire after **180 days**; the existing `v2` key and old point records remain compatible, with mapping to the new zones at read time.

Because Mercator scaling and actual map-canvas dimensions vary, "70 km" is the geographic radius fed to the calculation, **not** a fixed zoom number and **not** 70 km of driving distance.

## URL priority and lifecycle

Relevant location components:

- `src/components/mobile-app-v2.tsx`: main mobile map screen, last-user-camera writes, `pagehide` / `visibilitychange` handlers, `mapAuto` URL flag, and region camera.
- `src/components/mobile-map-listings-layer.tsx`: marker, price callout and sibling selection; saves the focused position.
- `src/components/map/results-map.tsx`: desktop initial camera, interaction listener, request-on-idle/viewport bounds, history save on unmount.
- `src/pages/SearchPage.tsx`: route query normalization and desktop search state.
- `src/lib/spain-communities.ts`: `communityMapCamera` for an explicit region selection.

`mapLat`, `mapLng`, `mapZoom` can describe exact camera position in a URL; `mapAuto=1` identifies a **generated transient camera**. Do not include `mapAuto` in search filters or use an auto-generated exact camera as the fresh-visit override. Links intentionally specifying a camera without the auto flag are treated as explicit.

On `/#/buscar?vista=mapa` the query/region, saved polygon, nearby coordinates, explicit camera and remembered last zone can all be present. Preserve the existing source-code precedence instead of adding another state store with a competing priority.

## Search is not equal to viewport recall

Applied list/map searches use a single geographic constraint, with this priority:

1. Explicitly drawn `poligono` (point-in-polygon through PostGIS).
2. Explicitly submitted visible map bounds (`norte`, `sur`, `este`, `oeste`).
3. Explicit nearby search (`cerca=1` with valid `lat` and `lng`, plus radius).
4. Named city or selected `comunidad` when no map region is applied.
5. Nationwide results only when none of the above has been selected.

A map polygon or viewport search must not be intersected with a stale city, autonomous community or previously submitted map bounds. Selecting a new named location clears the previous drawn/viewport constraint. A remembered **70 km map camera** does not itself activate a listing filter; it is a viewport-restoration affordance, not a saved user search.

The desktop search page and the independently paginated mobile-results overlay both derive their server request geography from the same URL parser (`src/lib/search-geography.ts`). The backend already filters cards and markers through PostGIS; never filter only visible marker UI while allowing non-matching cards. The request contract is covered by `tests/phase1/geographic-search.spec.ts`.


Map history remembers the user's **position**, not which listings they viewed. Filtering still happens server-side by published visibility, mode, price, location and/or selected `comunidad`. The API uses:

- `POST /api/v1/listings/map`: bounded markers and grid clusters for an explicit viewport.
- `POST /api/v1/listings/search/cards`: scrolling result list.
- `POST /api/v1/listings/regions/counts`: per-community facet counts; not used to infer a specific map pan.
- An explicit polygon is a separate user-owned drawn search region and must not be silently replaced with a 70 km zone.

History is stored locally in this browser, not synced between devices and not the same as the server's `/search-history` or `/saved-searches` records.

## Testing checklist

1. New browser context with no map history → wide Spain/Canary overview.
2. Pan/zoom in Tenerife → leave without opening an ad → fresh map entry covers 70 km zone.
3. Pan to Gran Canaria, Madrid or Cuenca → new entry changes to the corresponding zone.
4. Reload with generated `mapAuto=1` → re-fit 70 km instead of restoring close-up. Explicit bookmarked camera still works.
5. Tap a marker → Back in same document retains precise camera; new page visit fits zone.
6. Geolocation Madrid/Barcelona → "near me" works inside supported Spain geometry; coordinates outside Spain give location error.
7. Selected `comunidad` remains applied after list/map switch and is not lost to old Tenerife filters.
8. Verify mobile and desktop viewport sizes independently; test `localStorage` failures and hidden-tab transitions.

Tests: `tests/navigation-history.spec.ts`, `tests/spain-community-search.spec.ts`, `tests/mobile-location-map.spec.ts`, and map visual snapshots. See [Testing](testing.md).
