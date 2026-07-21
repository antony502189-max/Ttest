# Screenshot-locked current route index

Baseline commit: `e38bc3524f0ea05074e0888d50089ce52b0a9e2b` (`main`)

The worktree contains pre-existing uncommitted changes in `src/components/map-view.tsx`, `src/contexts/i18n-context.tsx`, `src/index.css`, `tests/visual-parity.spec.ts`, and a deleted `tests/i18n-completeness.spec.ts`. These are treated as user-owned baseline state and are not reverted.

## Target-to-route map

| Target frames | Target state | Current route/state used for BEFORE-LIVE |
|---|---|---|
| 019, 024, 032, 112, 114 | Home and saved-search states | `/#/` (long and tourist tabs; saved-search state where available) |
| 035 | Location entry screen | `/#/`, then activate the full location control |
| 037, 042, 043, 045 | Map draw instruction, drawing, selected polygon, selected-zone list | `/#/buscar?q=Tenerife&vista=mapa` plus `dibujar=1` and polygon interactions |
| 046, 049, 053, 055 | Filter top, price/date/gender, middle, lower fields | `/#/buscar?q=Tenerife`, then open `Todos los filtros` and scroll |
| 057, 060, 063, 066, 068 | Results list, overview map, selected zone, marker, selected preview | `/#/buscar?q=Tenerife` and `/#/buscar?q=Tenerife&vista=mapa` |
| 069, 073, 076, 080, 083, 084, 086 | Listing first image, content, comments, favorite state | `/#/habitacion/arme%C3%B1ime-luminosa-01` and gallery/contact states |
| 090, 092, 096 | Home return, saved search, menu | `/#/` and `/#/menu` |
| 100, 105, 109 | Edit form and owner listings | `/#/mis-anuncios`, `/#/mis-anuncios/:id/editar`, and `/#/publicar` with the host demo session |
| Supporting product routes | Profile and local messages | `/#/perfil` and `/#/mensajes` |

## Required BEFORE-LIVE matrix

- Mobile: 320x568, 360x800, 375x812, 390x844, 412x915.
- Landscape: 667x375 and 844x390 for map states.
- Tablet/desktop: 768x1024, 1024x768, 1440x900 for representative responsive checks.
- Unmasked screenshots are stored under `artifacts/screenshot-locked/before-live/`.

## Reference gaps and adaptations

- Target frames show Idealista property categories, Spain-wide labels, and Russian UI. The implementation keeps the screenshot geometry and interaction hierarchy while adapting content to rooms, Tenerife-only geography, and the existing ES/EN/RU system as required by the pack.
- The target does not contain native 112233.es screenshots for local-only comment storage, account isolation, or messages. Those behaviors are compared to the nearest comment/detail/menu frames and verified functionally.
- The existing ten-step publish wizard is retained per the contract; its cover/restriction preview is mapped to the dense owner edit/list frames rather than replacing the workflow.
