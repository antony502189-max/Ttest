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

## District and neighbourhood hierarchy

`tenerife-zone-hierarchy.geojson` adds real, source-backed child zones for the two
key urban municipalities requested for the search experience:

- **San Cristóbal de La Laguna:** 6 statistical district polygons from
  [ISTAC, Distritos de Canarias a 01/01/2024](https://datos.canarias.es/catalogos/estadisticas/dataset/distritos-de-canarias-a-01-01-2024),
  generalized GeoJSON in WGS84. Retrieved 2026-07-22. The
  [ISTAC reuse terms](https://www.gobiernodecanarias.org/istac/aviso_legal.html)
  permit commercial and non-commercial reuse and require the attribution
  `Fuente: Instituto Canario de Estadística (ISTAC)` plus the update date.
- **Santa Cruz de Tenerife:** 5 named district polygons from the municipal
  [Distritos GeoJSON](https://datos.gob.es/es/catalogo/l01380380-distritos1/resource/0320174e-8d5e-4bd2-95b4-c7b58bbc7599)
  and 80 neighbourhood polygons from
  [Barrios. Población año 2016](https://datos.gob.es/es/catalogo/l01380380-barrios-poblacion-ano-20161),
  both published by Ayuntamiento de Santa Cruz de Tenerife under CC BY.

Run `npm run data:zones` to download and rebuild the hierarchy. The transform
filters the ISTAC collection to La Laguna, removes demographic attributes from
the Santa Cruz neighbourhood layer, adds canonical stable IDs, parent IDs,
aliases, geometry-availability flags, and source metadata. Coordinates are not
invented or manually redrawn. These layers are search aids and are not presented
as cadastral or legally binding boundaries.
