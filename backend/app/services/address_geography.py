"""Server-side Spanish address resolution against IGN/CNIG CartoCiudad.

Municipality codes are INE identifiers, never postcode prefixes. Only a
resolved portal with matching street, building and postcode is accepted.
Provider failure is a controlled error; client coordinates are not evidence.
"""
import json
import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import HTTPException

from ..core.public_http import PublicNetworkAsyncClient
from ..spain_provinces import address_province_code, coordinates_in_spain

MUNICIPALITIES = json.loads((Path(__file__).parents[1] / "data/spain-municipalities.json").read_text(encoding="utf-8"))["municipalities"]
GEOCODER_URL = "https://www.cartociudad.es/geocoder/api/geocoder/candidates"


class _PrivateAddressLogFilter(logging.Filter):
    def filter(self, record):
        # HTTPX normally logs the full GET URL at INFO. This request includes
        # a private address, which must not enter application request logs.
        return GEOCODER_URL not in record.getMessage()


logging.getLogger("httpx").addFilter(_PrivateAddressLogFilter())


def normalized(value):
    value = ''.join(c for c in unicodedata.normalize("NFKD", str(value)).casefold() if not unicodedata.combining(c))
    value = re.sub(r"[^a-z0-9 ]", " ", value)
    return " ".join(value.split())


def street_key(value):
    value = normalized(value)
    return re.sub(r"^(?:calle|c|carrer|cl|avenida|av|avda|paseo|plaza|placa|pza) +", "", value)


def distance_metres(lat, lng, other_lat, other_lng):
    a, b = math.radians(lat), math.radians(other_lat)
    h = math.sin((a-b)/2)**2 + math.cos(a)*math.cos(b)*math.sin(math.radians(lng-other_lng)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


@dataclass(frozen=True)
class VerifiedAddress:
    street: str
    postcode: str
    city: str
    municipality_code: str
    province_code: str
    latitude: float
    longitude: float
    provider_id: str

    def private_snapshot(self):
        return {"street": self.street, "postcode": self.postcode, "city": self.city,
                "municipalityCode": self.municipality_code, "provinceCode": self.province_code,
                "latitude": self.latitude, "longitude": self.longitude, "providerId": self.provider_id,
                "source": "CartoCiudad"}


async def address_candidates(street, postcode, city):
    # Fixed origin, public IP pinning, bounded response and no redirects; no
    # arbitrary URL or address-provider key is accepted from the caller.
    try:
        async with (
            PublicNetworkAsyncClient(timeout=8, follow_redirects=False) as client,
            client.stream("GET", GEOCODER_URL, params={
                "q": f"{street}, {city}", "limit": 12, "countrycodes": "es",
                "cod_postal_filter": postcode,
            }) as response,
        ):
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 65536:
                    raise ValueError("oversized geocoder response")
        result = json.loads(data)
        if not isinstance(result, list):
            raise TypeError("invalid geocoder response")
        return result
    except (httpx.HTTPError, ValueError, TypeError, OSError):
        # Avoid including a request URL containing a private address in logs.
        raise HTTPException(503, "Address verification is temporarily unavailable; please retry") from None


async def verify_address(street, postcode, city, *, latitude=None, longitude=None):
    province = address_province_code(postcode)
    if not province or not street.strip() or not city.strip() or not re.search(r"[0-9]", street):
        raise HTTPException(422, "A complete Spanish street address, building number and postcode are required")
    candidates = await address_candidates(street, postcode, city)
    matches = []
    for row in candidates:
        if not isinstance(row, dict):
            continue
        code = str(row.get("muniCode", ""))
        if (row.get("type") != "portal" or code not in MUNICIPALITIES
                or row.get("countryCode") not in {"011", "ES", "es"}
                or row.get("provinceCode") != province or code[:2] != province
                or row.get("postalCode") != postcode):
            continue
        if normalized(city) not in {normalized(row.get("muni", "")), normalized(row.get("poblacion", ""))}:
            continue
        if street_key(street) != street_key(str(row.get("address", "")).split(",")[0]):
            continue
        try:
            lat, lng = float(row["lat"]), float(row["lng"])
            if not math.isfinite(lat) or not math.isfinite(lng) or not coordinates_in_spain(lat, lng):
                continue
            if latitude is not None and longitude is not None and distance_metres(lat, lng, latitude, longitude) > 250:
                continue
        except (ValueError, TypeError, KeyError):
            continue
        matches.append(VerifiedAddress(street, postcode, str(row["muni"]), code, province, lat, lng, str(row["id"])))
    if not matches or len({row.municipality_code for row in matches}) != 1:
        raise HTTPException(422, "Address, postcode and map location must identify the same Spanish address")
    return matches[0]
