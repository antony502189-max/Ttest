# Tenerife municipality boundaries

`tenerife-municipalities.geojson` contains the 31 municipal polygons used by `ZoneSelectionMap`.

- Source: **Cabildo de Tenerife, Servicio Técnico de Sistemas de Información Geográfica** — [Límites municipales de Tenerife](https://datos.tenerife.es/datos/conjuntos-de-datos/limites-municipales-de-tenerife)
- Distribution: `Límites Municipales de Tenerife - polígonos`, GeoJSON, EPSG:4326
- Source data date: November 2015
- Retrieved: 2026-07-22
- License: [Creative Commons Attribution (CC BY)](https://opendefinition.org/licenses/cc-by/)
- Required attribution: `Límites Municipales de Tenerife, Cabildo de Tenerife, CC BY`

The source notes that the coastline comes from the 1:5,000 Topographic Map and that the internal lines have not been made official by the Cabildo. The UI therefore labels this layer as a municipal-boundary search aid, not as a legal cadastral boundary.

## Transformation

Run `node scripts/fetch-tenerife-municipalities.mjs` to rebuild the file. The script:

1. downloads the official polygon GeoJSON;
2. dissolves the source fragments and offshore rocks into one `MultiPolygon` feature per municipality;
3. keeps the original geometry and national municipality code;
4. adds stable `id`, `label`, and `kind: "municipality"` properties;
5. normalizes five labels to the current names already used by the application.

No district or neighbourhood polygons are included because this source only provides municipalities. Existing neighbourhood names remain available as text filters and listing metadata.
