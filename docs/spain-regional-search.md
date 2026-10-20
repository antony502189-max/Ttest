# Spain autonomous-community search — implementation contract

The province picker and provincial TOP rules now supersede the picker flow below.
See [Province search and TOP capacity](province-search-and-top.md). Existing
`comunidad` routes and their spatial filtering remain supported for compatibility.

**As of 2026-10-11 (PR #321):** the product location picker covers the 17 Spanish autonomous communities. It is **not** a country → province → city drill-down. A city typed into the input is used to **suggest its autonomous community**; the resulting list is scoped to the whole selected community, not necessarily to the city itself.

## User journey

1. The mobile Home location field is initially unselected (no hard-coded Tenerife).
2. Tap the location field to open the existing "Where are you searching?" screen. It has a search input and the supported actions: **draw your zone**, **search on map**, **nearby search**. The old fixed "Search in Tenerife / Change" banner was removed.
3. Focus or enter text: **same-screen inline** autocomplete opens, with the 17 communities, a listing count, and a right arrow. Do not navigate to a separate suggestions screen.
4. Text can be a community name, its capital, a known city, or a municipality. "Barcelona" or "barce" ranks **Cataluña** first; "Madrid" gives **Comunidad de Madrid**; "Tenerife" gives **Canarias**. Ambiguous prefixes can return multiple rows: the user selects the correct one.
5. Select a row: route becomes `/#/buscar?q=<region-name>&comunidad=<id>&alquiler=<mode>`, opening scrolling **cards**, with the number of matches and localized community name in the upper-left header.
6. Switching to map view, sorting, and filter navigation keep the selected `comunidad`. The first map camera for a named community can fit its geographic bounds rather than using the last explored anonymous map zone.

## Exact region IDs

IDs match the `cod_ccaa` values in the bundled polygon data; **do not replace with array indices** or localized display labels.

| ID | Español (app) | Русский | Example city |
| --- | --- | --- | --- |
| 01 | Andalucía | Андалусия | Sevilla |
| 02 | Aragón | Арагон | Zaragoza |
| 03 | Asturias | Астурия | Oviedo |
| 04 | Illes Balears | Балеарские острова | Palma |
| 05 | Canarias | Канарские острова | Santa Cruz de Tenerife / Las Palmas |
| 06 | Cantabria | Кантабрия | Santander |
| 07 | Castilla y León | Кастилия-и-Леон | Valladolid |
| 08 | Castilla-La Mancha | Кастилия-Ла-Манча | Toledo / Cuenca |
| 09 | Cataluña | Каталония | Barcelona |
| 10 | Comunitat Valenciana | Валенсия | València / Alicante |
| 11 | Extremadura | Эстремадура | Mérida |
| 12 | Galicia | Галисия | Santiago de Compostela |
| 13 | Comunidad de Madrid | Мадрид | Madrid |
| 14 | Región de Murcia | Мурсия | Murcia |
| 15 | Navarra | Наварра | Pamplona |
| 16 | País Vasco | Страна Басков | Vitoria-Gasteiz |
| 17 | La Rioja | Ла-Риоха | Logroño |

The picker intentionally follows the specified **17 communities**: Ceuta and Melilla are not entries in this UI. This is separate from generic Spain-scale map support, which must not be described as limited to the 17 UI choices.

## Code/data ownership

- UI copy, picker and count loading: `src/components/mobile-app-v2.tsx`, `LocationScreen`.
- Region catalog, translations, municipality matching, rank and local point-in-polygon for mock mode: `src/lib/spain-communities.ts`.
- The frontend bundles `src/data/spain-communities.json` (boundary polygons) and `src/data/spanish-municipalities.json` (~8,130 INE municipalities across 17 communities). Region names also include aliases for common local variants.
- Backend reads its equivalent region boundaries from `backend/app/spain_communities.json` via `backend/app/spain_communities.py`; `community_contains_location` builds the PostGIS predicate on `Listing.location`. The frontend's point-in-polygon is a **mock-mode convenience only**, not a replacement for server authorization.
- Origins: simplified polygons from [click_that_hood](https://github.com/codeforgermany/click_that_hood) (MIT license stored as `backend/app/spain_communities_LICENSE.txt`); municipality names from [codeforspain/ds-organizacion-administrativa](https://github.com/codeforspain/ds-organizacion-administrativa) (INE dataset). Geography simplification may affect boundary-edge accuracy; inspect sampled boundaries when changing them.
- Existing local `src/lib/tenerife.ts` remains for legacy city and named-location routes. Do not use it as a general Spain-area constraint.

## API semantics

`POST /api/v1/listings/regions/counts` receives a `ListingSearchRequest` body (for example `{"rentalMode":"long","maxPrice":1000}`) and returns:

```json
{
  "items": [
    {"id":"01","count":0,"cities":[]},
    {"id":"09","count":0,"cities":["Barcelona"]},
    {"id":"13","count":0,"cities":["Madrid"]}
  ]
}
```

Example numbers above are **illustrative only**, not production counts. The real response always provides **17** entries, with counts derived from current published/visible listings and the active applicable search filters. The endpoint removes `query` and `autonomousCommunity` from the incoming filters while grouping, so it can return counts for **all** communities at once. `cities` are distinct observed listing-city names, used for autocomplete augmentation.

For actual results the browser includes `autonomousCommunity:"09"` in `POST /listings/search/cards` and, on map view, in `POST /listings/map`. The DB applies `ST_Intersects` against the selected MultiPolygon (geography SRID 4326). It does **not** search `Listing.city ILIKE '%Cataluña%'`; such a text filter would miss Barcelona listings. Published listing visibility, mode and price rules still apply.

An invalid community ID fails request-schema validation; `autonomousCommunity` is a two-character string matching `01` through `17`. Results may legitimately be zero. Imported records without usable map points cannot pass a spatial community filter: this is preferable to guessing their region from an ambiguous city name.

## Counts, alias ranking and limitations

- Region-name matches rank before recognized capital/major-city matches, which rank before exact/partial municipality matches. `barce` can also match Barceo; the intended behavior is for **Cataluña** to rank before less relevant regions.
- Counts change when publication, moderation, rental-mode or price filters change. No count should be presented as a fixed property of the municipality dictionary.
- The picker selects an **autonomous community**, not a city radius or a saved custom polygon. Custom-drawn searches and "near me" are separate workflows.
- Production cache and source freshness affect what listings are available. A green CI test cannot establish current population or count values in production.
- The separate `POST /listings/search/cards` request validates sort/cursor restrictions; never assume the count response is also a full listing page.

## Regression and operational acceptance

- `tests/spain-community-search.spec.ts`: 17 entries, no default Tenerife banner, inline suggestions, Barcelona/Cataluña, Madrid/Canarias, geographical city samples and municipality aliases.
- `backend/tests/integration/test_autonomous_communities.py`: published/hidden/price cap behavior, multiple islands, and equality of grouped region counts with card-search totals.
- `tests/mobile-location-map.spec.ts`: home/location actions and retained old deep-link behavior.
- Verify **after an authorized production release** that the endpoint responds and counts match a regional card search under the same filters. Treat any mismatch as a backend query/visibility incident, not a styling problem.

See [API](api.md), [Frontend](frontend.md), [Maps](navigation-and-maps.md), [Testing](testing.md).
