# Final acceptance checklist V4

Status: **PASS**

Baseline: `384787e60a10fba711f23b5f1db6905992d14154`

Review date: 2026-07-22
Reference method: target-corpus review, not self-baseline approval.

## Evidence basis

- Full V4 catalog: 2,595/2,595 referenced frames present across 22 catalog sections.
- Golden states: 32/32 reviewed with the required ±2.5 s sequence and top/middle/bottom crops.
- Evidence per golden: TARGET, AFTER-V2, BEFORE-V4, AFTER-V4, alpha overlay, unmasked difference heatmap, content mask and geometry JSON.
- Global manual review surfaces: `overlay-contact-sheet.jpg` and `diff-contact-sheet.jpg`.
- `acceptance.csv`: 32/32 rows marked `manual_geometry_review=PASS` and `status=PASS` after the manual target review.
- Masks document only permitted device chrome and raster photo interiors. Geometry, controls, typography, polygons, container edges and spacing remain unmasked. RGB differences in the CSV are also unmasked.

## Preparation

- [x] Baseline SHA equals or descends from 384787e
- [x] V2 report reviewed
- [x] Repository AFTER-V2 screenshots reviewed
- [x] Full target catalog opened
- [x] Golden sequences reviewed with neighbor frames
- [x] Fresh BEFORE-V4 captured

## Home

- [x] Header geometry matches
- [x] Promoted image geometry matches
- [x] Overlay geometry matches
- [x] Lime block matches
- [x] Tabs match
- [x] Para quién matches
- [x] Location control matches
- [x] Buscar matches
- [x] Publicar CTA matches
- [x] 390×844 fold matches
- [x] Non-reference marketing sections removed/reduced

## Search list

- [x] Single compact mobile hierarchy
- [x] Toolbar matches
- [x] Result count/chips match
- [x] Card image geometry matches
- [x] Favorite/arrows/counter match
- [x] Restriction overlay matches
- [x] Price/title/facts match
- [x] Contact/menu match
- [x] Card spacing/separators match

## Filters/sort

- [x] Filter top matches
- [x] Filter middle matches
- [x] Filter bottom matches
- [x] Sticky CTA matches
- [x] Sorting sheet matches
- [x] Small-height viewport works

## Map

- [x] Overview matches
- [x] Draw instruction matches
- [x] Drawing state matches
- [x] Polygon state matches
- [x] Marker state matches
- [x] Selected preview matches
- [x] CTA matches
- [x] Landscape matches
- [x] Tenerife-only preserved

## Listing

- [x] Action bar matches
- [x] Gallery matches
- [x] Restriction overlay matches
- [x] Price/title order matches
- [x] Add comment placement matches
- [x] Advertiser comment matches
- [x] Local comments match target geometry
- [x] Contact bar matches
- [x] No overlap

## Product routes

- [x] Menu matches
- [x] Saved searches match
- [x] Favorites match
- [x] Messages consistent
- [x] Profile matches
- [x] Owner listings match
- [x] Owner edit matches
- [x] Publish room step matches
- [x] Publish restrictions step matches
- [x] Publish cover matches
- [x] Publish preview matches

## Languages

- [x] ES
- [x] EN
- [x] RU
- [x] No mixed pages
- [x] No overflow
- [x] Accessible names translated

The home tenant selector is rendered natively in each language and is asserted as `Para quién: cualquiera`, `Who is it for: anyone`, and `Для кого: любой`. Tenerife and the 11·22·33 brand are intentionally invariant proper names.

## Evidence

- [x] TARGET/AFTER-V2/BEFORE-V4/AFTER-V4 boards
- [x] Alpha overlays
- [x] Diff heatmaps
- [x] Geometry JSON
- [x] Acceptance CSV
- [x] No self-baseline approval

## Quality

- [x] typecheck — pass
- [x] lint — pass
- [x] build — pass
- [x] e2e — 112 passed, 1 V4 opt-in evidence test skipped in the default run
- [x] a11y — 28 passed, no serious/critical axe impacts
- [x] visual — 7 passed; these snapshots are regression guards only
- [x] no console errors
- [x] no page errors
- [x] no failed critical requests
- [x] no horizontal overflow
- [x] no fixed overlaps
- [x] commit main
- [x] Pages verified

Two `net::ERR_ABORTED` source/tile requests may appear in capture diagnostics when a route is deliberately replaced while a lazy module or OSM tile is still in flight. They are navigation cancellations, not failed active-state or critical requests. The dedicated diagnostics test passed.

## Documented content adaptations

- The product remains a Tenerife-only, rooms-only marketplace with the original local 11·22·33 brand, data model and implemented V2 functionality.
- Idealista trademarks, account data, listing text, phone data, exact photos and device chrome were not copied into the product. Existing repository photos and truthful local listing data are retained under the photo/content protocol.
- Copy and available form fields are adapted to rooms-only inventory. The accepted parity criterion is the target geometry, hierarchy, control count/density and interaction sequence, with these content substitutions documented separately.
