# Frontend handbook

## Entry and routing

`src/main.tsx` imports global and feature styles and mounts `src/App.tsx`. The application uses React 19, TypeScript, Vite, `HashRouter` and lazy route imports. Product-facing labels support Spanish, Russian and English through `src/contexts/i18n-context.tsx` and mobile copy dictionaries.

| UI | Main implementation |
| --- | --- |
| Main navigation and protected routes | `src/App.tsx`, `src/components/layout.tsx` |
| Mobile home, onboarding, location picker and map | `src/components/mobile-app-v2.tsx` |
| Search cards (mobile) | `src/components/mobile-search-results-v2.tsx` |
| Desktop search and result state | `src/pages/SearchPage.tsx` |
| Map canvas, viewport and clusters | `src/components/map/results-map.tsx`, `src/components/mobile-map-listings-layer.tsx` |
| Listing details and galleries | `src/pages/ListingPage.tsx` |
| User publication/edit | `src/pages/ListingCreatePage.tsx`, `src/pages/ListingEditPage.tsx` |
| User state | `src/contexts/`, `src/api/`, `src/lib/` |
| Admin | `src/pages/AdminPage.tsx`, `src/api/admin.ts` |

The historical Tenerife-specific helper `src/lib/tenerife.ts` still handles legacy named-location and deep-link behavior; it **must not** be used as a blanket restriction on the Spain-wide autonomous-community picker.

## Key search flow

1. A fresh user sees an unselected location on mobile Home. The old hard-coded default `Tenerife` is not used as a selected countrywide location.
2. Opening the existing location screen reveals an input and the working shortcuts **draw zone**, **search on map**, **search nearby**. There is no extra intermediate suggestion page.
3. Focusing/typing opens an inline list of 17 autonomous communities with published-listing counts. Recognized capitals and municipalities, e.g. Barcelona, match their enclosing community. Rankings prefer exact region and major-city names.
4. Clicking a community creates a `/#/buscar?...&comunidad=<id>` route and opens the **scrolling** result list, not the map. The result header uses the selected community name.
5. The map view and sorting/filters preserve the `comunidad` parameter and the backend applies the same region predicate. Map camera history operates independently of a selected named region.

Source/contract details: [Regional search](spain-regional-search.md) and [Maps](navigation-and-maps.md).

## Search and rendering

Real production search uses `src/api/listings.ts` for cursor card search, map marker requests, region counts and detail hydration. `VITE_ENABLE_MOCK_MODE=1` instead uses `src/data/listings.ts` and local filter code; browser tests explicitly exercise both modes. The public list and map are bounded; do not reintroduce an eagerly downloaded nationwide catalog into `AppContext`.

`Vivienda` and `Turismo` are separate. The €1,000/month long-term maximum does not apply to holiday pricing. Existing image/video gallery sizes, listing preview, map price markers and favorites are product-sensitive: preserve approved layouts and test them under `tests/` before changing style layers.

## URL and local state

- `q`: display/search term; `alquiler`: long-term/holiday route mode; `comunidad`: selected autonomous-community ID; `vista=mapa`: map presentation.
- `mapLat`, `mapLng`, `mapZoom`: transient or bookmarked camera; `mapAuto=1` denotes a generated camera and should not act as a listing filter. `lat/lng` and other map modifiers have separate nearby/explicit intent.
- Browser key `112233:map-last-search-area:v2` retains the **last explored point** for at most 180 days. On fresh map visits the point snaps to a 70 km virtual zone; it is not a persistent server search history or saved polygon.
- Guest favorites and discarded IDs may exist before login; the backend provides `POST /account/import-guest-state` for authenticated transition.

Refer to [Map lifecycle](navigation-and-maps.md) before editing navigation: ordinary in-app Back after a listing can retain exact camera while a fresh page load intentionally re-fits the remembered 70 km circle.

## Performance and accessibility

Use route-level lazy chunks, query cancellation, debounced map idle requests, bounded marker pages, and image variants. Avoid N×17 point-in-polygon work for mock region counts; the current mobile picker groups each listing once. Use keyboard-focusable controls, explicit labels, `aria-live` for suggestions, visible focus states and i18n keys. Responsive/visual regression tests are required, not cosmetic baselines generated without review.

Run `npm run lint && npm run typecheck && npm run build` and the appropriate Playwright suites. [Testing](testing.md), [Performance](performance/mobile-entry.md), [Troubleshooting](troubleshooting.md).
