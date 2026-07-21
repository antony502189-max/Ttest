# Final mobile delta — reference comparison

Reviewed at the primary `390×844` viewport, with supporting checks at `320×568`, `360×800`, `390×700`, `412×915`, `667×375`, and desktop widths. The supplied screenshots are used as composition and density references only; their visual identity and raster assets are not copied into the product.

## Manual findings

| Surface | Reference relationship | Current result |
| --- | --- | --- |
| Home | Promoted media → two rental modes → tenant selector → location → primary search → publish action | Same order and comparable first-fold proportions. The full search panel and publish action are visible at `390×844`; touch targets remain at least 44 px. |
| Location | App-like full-screen selection with map alternatives | Full `100dvh` flow, structured Tenerife catalog, static Tenerife market row, and working select/draw/nearby actions. |
| Search list | Compact route header and action strip before dense cards | Global header/search form removed on mobile. Result count, `Filtros / Ordenar / Mapa`, chips, and first card occupy a compact discovery stack. |
| Map | Map-dominant screen with floating tools and one result CTA | Dedicated full-screen map, no global header or bottom navigation, one back/location row, and a full-width `Mostrar N habitaciones` CTA. |
| Cards | Image, price, title, facts, concise restrictions, primary contact | Reduced vertical padding and badge weight; primary `Contactar` plus a 44×44 overflow action. |
| Detail | Single icon top bar, edge-to-edge gallery, price-first hierarchy | Redundant global header removed, action texts moved to accessible icons/overflow, gallery reaches viewport edges, and contact stays above navigation. |
| Menu/messages | Compact app header, real account identity, honest activity rows | Profile avatar resolves through the existing media layer; local message rows explicitly say `Demo local` and `No enviado por internet`. |

## Evidence sheets

Every sheet uses the required `REFERENCE | CURRENT | NOTES` structure:

- `sheets/home-reference-current-notes.png`
- `sheets/app-overview-reference-current-notes.png`
- `sheets/web-overview-reference-current-notes.png`
- `sheets/detail-1-reference-current-notes.png`
- `sheets/detail-2-reference-current-notes.png`
- `sheets/detail-3-reference-current-notes.png`
- `sheets/detail-4-reference-current-notes.png`

Permanent project snapshots mask only dynamic raster photos/map tiles. The unmasked delivery evidence is stored in `../after/`.

## Decision

Accepted for final quality-gate execution. The remaining differences are intentional 112233.es branding, typography, listing data, and photography—not structural parity defects.
