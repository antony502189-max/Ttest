"""Spain autonomous-community geographies (2014 click_that_hood, MIT).

Geographic polygons are shipped locally with the application: no geocoder or
external network call is needed to scope search or count published listings.
The same simplified source JSON is imported by the frontend location selector.
Source: Code for America / codeforgermany click_that_hood; MIT license.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from geoalchemy2 import Geography
from sqlalchemy import cast, func


@lru_cache(maxsize=1)
def community_geometries() -> dict[str, dict]:
    source = json.loads(Path(__file__).with_name("spain_communities.json").read_text(encoding="utf-8"))
    return {item["id"]: {"type": "MultiPolygon", "coordinates": item["polygons"]}
            for item in source["features"]}

def community_contains_location(region_id: str, location):
    shape = community_geometries().get(region_id)
    if shape is None:
        raise ValueError("Unknown Spanish autonomous community")
    geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(shape, separators=(",", ":"))), 4326)
    return func.ST_Intersects(location, cast(geometry, Geography("MULTIPOLYGON", srid=4326)))
