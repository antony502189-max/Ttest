# Final mobile parity delta verification

## Scope and provenance

- Repository: `antony502189-max/Ttest`, branch `main`.
- Required baseline: `bc4803083790dbf4df50f8aaaa592ffbe29aaceb`.
- Main implementation commit: `b77f53753052cec67682a172fb57ffbfbecfae0b` (`Complete final Tenerife mobile parity`).
- CI stabilisation commit: `d8a7dd6590ba4277397039940cad78b27ef37e4c`.
- The existing mobile parity pass was retained; this change set implements only the remaining `MASTER_PROMPT_FINAL_MOBILE_DELTA.md` work.
- Baseline captures are in `before/`, final captures in `after/`, selected image diffs in `diff/`, and annotated reference comparisons in `reference-comparison/`.

## Delivered delta

- Centralised Tenerife geography in `src/lib/tenerife.ts`: island bounds, centre, zoom, municipalities, areas, aliases, query resolution, history sanitisation, listing matching, and coordinate validation.
- Tenerife-only search now rejects unsupported locations instead of silently returning island inventory. Valid municipalities and areas resolve to truthful filtered result sets.
- The whole location control opens one fullscreen flow. It includes structured Tenerife selection, search history, `Para quién` in both entry modes, `Dibujar tu zona`, and `Buscar alrededor de ti`.
- `Dibujar tu zona` and geolocation execute real map/search state transitions. Coordinates outside Tenerife are explicitly rejected.
- Mobile map view is a dedicated `100dvh` screen with no global header or bottom navigation, map controls, visible listing markers, back/location actions, and a result CTA.
- Results, property cards, and listing detail were compacted without removing core information or actions. Detail gallery and primary contact flow remain intact.
- Message threads are stored per local demo user and are labelled honestly as local demo behaviour; no backend delivery is implied.
- Menu/profile avatar media, filter draft/reset semantics, URL state commits, and ES/EN/RU strings for the new states were completed.

## Preserved behaviour

- Existing desktop marketplace layouts and completed mobile parity routes.
- Authentication/demo-session switching, favourites, menu/profile navigation, publishing wizard, image management, gallery, contact dialog, and existing listing data.
- HashRouter deployment compatibility for GitHub Pages.

## CSS and component cleanup

- Consolidated mobile density, card/detail spacing, fullscreen map layout, location rows, and interactive states in the existing design system.
- Removed superseded mobile screenshot baselines and replaced them with the required responsive/state matrix.
- Reused existing shadcn/Radix primitives and tokens; no parallel component system or one-off visual identity was introduced.

## Visual and reference QA

- Responsive evidence covers 320×568, 360×800, 390×844, 412×915, 667×375, and 1440×900 where applicable.
- Visual snapshots cover home, Tenerife location flow, list, filters, sort, dedicated map, listing, gallery, contact, menu, empty/filled messages, profile, publish steps, and Russian home/search states.
- Annotated side-by-side sheets compare the current build against the supplied customer target, Idealista app references, and mobile-web detail references.
- CI uses a bounded 4% raster tolerance for Windows-versus-Ubuntu Chromium text/SVG antialiasing. Async property/publish images are either awaited or masked so the UI itself remains a meaningful visual regression gate.

## Quality gates

- `npm run typecheck`: pass.
- `npm run lint`: pass.
- `npm run build`: pass.
- `npm run test:e2e`: 108/108 pass locally; GitHub Actions pass.
- `npm run test:a11y`: 28/28 pass locally; GitHub Actions pass.
- `npm run test:visual`: 7/7 suites pass locally; GitHub Actions pass.
- Targeted responsive diagnostics: no document overflow at the required viewport matrix.
- Targeted console/network diagnostics: no application console errors, page errors, or failed first-party requests on critical routes.
- shadcn project inspection: pass.

## CI and publication

- Frontend checks: https://github.com/antony502189-max/Ttest/actions/runs/29850306415 — success.
- GitHub Pages deployment: https://github.com/antony502189-max/Ttest/actions/runs/29851080720 — success.
- Published site: https://antony502189-max.github.io/Ttest/
- Verified live route: `/#/buscar?q=Tenerife&vista=mapa` returned HTTP 200, rendered the dedicated map, displayed `Mostrar 23 habitaciones`, and produced no console, page, or failed first-party request diagnostics.

## Intentionally remaining backend scope

- Server-side inventory/search, persisted polygons, production geospatial services, real user accounts, and real message delivery require backend contracts and infrastructure outside this frontend delta.
- The implemented frontend does not fabricate those services: local/demo-only behaviour is explicitly scoped and labelled.
