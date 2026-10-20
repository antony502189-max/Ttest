"""Provider fixture for the isolated full-stack HTTP audit; never packaged in app."""
import os

from app.core.config import get_settings
from app.services import address_geography

if os.environ.get("FULLSTACK_TEST_HARNESS") != "1" or get_settings().app_env == "production":
    raise RuntimeError("Full-stack provider fixtures require the explicit non-production harness")


async def address_candidates(street, postcode, city):
    if (street, postcode, city) != ("Calle Prueba 1", "38001", "Santa Cruz de Tenerife"):
        return []
    return [{"id": "fullstack-fixed-portal", "type": "portal", "countryCode": "011",
             "muniCode": "38038", "provinceCode": "38", "postalCode": "38001",
             "muni": "Santa Cruz de Tenerife", "poblacion": "Santa Cruz de Tenerife",
             "address": "Calle Prueba 1, Santa Cruz de Tenerife", "lat": 28.464, "lng": -16.2514}]


address_geography.address_candidates = address_candidates
from app.main import app  # noqa: F401
