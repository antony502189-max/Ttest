"""Anonymous, public-page adapters for supported small rental units."""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import logging
import re
from abc import ABC
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from typing import Any, cast
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx

from .core.browser_network import (
    configure_public_browser_context,
    hostname_matches_domain,
    validate_public_browser_url,
)
from .core.config import get_settings
from .core.media_limits import MAX_LISTING_PHOTOS
from .rental_classification import bedroom_count, property_type, rental_price
from .services.rental_price_limit import exact_euro_amount, long_term_price_allowed
from .spain_provinces import canonical_province, coordinates_in_spain, scope_province, spain_country

logger = logging.getLogger(__name__)


class SourceBlocked(RuntimeError):
    """A public source showed an access challenge; never treat this as missing listings."""


@dataclass
class DiscoveryResult:
    urls: set[str] = field(default_factory=set)
    complete: bool = False
    visited_pages: int = 0
    expected_total: int | None = None
    failed_pages: list[str] = field(default_factory=list)
    reached_last_page: bool = False
    blocked: bool = False
    roots: dict[str, dict[str, Any]] = field(default_factory=dict)
    continuation: dict[str, Any] | None = None

    def __iter__(self):
        return iter(self.urls)

    def __len__(self) -> int:
        return len(self.urls)

SPACE = re.compile(r"\s+")
TAG = re.compile(r"<[^>]+>")
LINK = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)
PHONE = re.compile(r"(?:\+?34[ .-]?)?(?:[6789]\d[ .-]?){4}\d")
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
POSITIVE = ("habitacion", "habitación", "cuarto", "room for rent", "alquiler de habitacion", "alquiler de habitación")
NEGATIVE = (
    "piso completo",
    "piso entero",
    "vivienda completa",
    "vivienda entera",
    "apartamento completo",
    "apartamento entero",
    "casa entera",
    "casa completa",
    "villa entera",
    "chalet entero",
    "estudio",
    "venta",
    "comprar",
    "se vende",
    "for sale",
    "busco habitacion",
    "busco habitación",
    "busco cuarto",
    "buscando habitacion",
    "buscando habitación",
    "necesito habitacion",
    "necesito habitación",
    "busco piso",
    "busco alojamiento",
    "se busca habitacion",
    "se busca habitación",
    "garaje",
    "oficina",
    "local comercial",
    "parcela",
    "terreno",
    "cama en habitacion",
    "cama en habitación",
    "plaza en habitacion",
    "plaza en habitación",
)
SANTA_CRUZ = (
    "santa cruz de tenerife",
    "tenerife",
    "la palma",
    "la gomera",
    "el hierro",
    "adeje",
    "agulo",
    "alajero",
    "alajeró",
    "arafo",
    "arico",
    "arona",
    "barlovento",
    "brena alta",
    "breña alta",
    "brena baja",
    "breña baja",
    "buenavista del norte",
    "candelaria",
    "el paso",
    "el pinar de el hierro",
    "el rosario",
    "el sauzal",
    "el tanque",
    "fasnia",
    "fuencaliente",
    "garachico",
    "garafia",
    "garafía",
    "granadilla de abona",
    "la frontera",
    "la guancha",
    "la laguna",
    "la matanza de acentejo",
    "la orotava",
    "la victoria de acentejo",
    "los llanos de aridane",
    "los realejos",
    "los silos",
    "puerto de la cruz",
    "puntagorda",
    "puntallana",
    "san andres y sauces",
    "san andrés y sauces",
    "san cristobal de la laguna",
    "san cristóbal de la laguna",
    "san juan de la rambla",
    "san miguel de abona",
    "san sebastian de la gomera",
    "san sebastián de la gomera",
    "santa cruz de la palma",
    "santa ursula",
    "santa úrsula",
    "santiago del teide",
    "tacoronte",
    "tazacorte",
    "tegueste",
    "tijarafe",
    "valle gran rey",
    "vallehermoso",
    "valverde",
    "vilaflor de chasna",
)
LAS_PALMAS = ("las palmas", "gran canaria", "lanzarote", "fuerteventura")
PROVINCE_ONLY = {"tenerife", "la palma", "la gomera", "el hierro"}
TARGET_COORDINATE_BOUNDS = (
    # Tenerife, La Palma, La Gomera, and El Hierro; Las Palmas lies outside all four boxes.
    (27.90, 28.62, -16.98, -16.02),
    (28.38, 28.92, -18.12, -17.60),
    (27.94, 28.28, -17.42, -16.94),
    (27.58, 28.02, -18.22, -17.78),
)


def clean(value: Any) -> str:
    return SPACE.sub(" ", html.unescape(TAG.sub(" ", str(value or "")))).strip()


def public_mapping(value: Any) -> dict[str, Any]:
    """Return structured public data only when the source actually supplies a mapping."""
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def public_coordinate_pair(value: Any) -> tuple[float, float] | None:
    """Parse a public latitude/longitude pair without inventing a location."""
    decoded = unquote(html.unescape(str(value or ""))).strip()
    decimal_comma = re.fullmatch(r"\s*(-?\d+),(\d+),(-?\d+),(\d+)\s*", decoded)
    if decimal_comma:
        latitude = float(f"{decimal_comma.group(1)}.{decimal_comma.group(2)}")
        longitude = float(f"{decimal_comma.group(3)}.{decimal_comma.group(4)}")
    else:
        decimal_point = re.fullmatch(
            r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*",
            decoded,
        )
        if not decimal_point:
            return None
        latitude, longitude = map(float, decimal_point.groups())
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


def public_map_coordinates(document: str) -> tuple[float, float] | None:
    """Extract coordinates explicitly published by a source detail page."""
    normalized = html.unescape(document).replace("\\/", "/")

    # Real-estate templates commonly expose map coordinates in public JS
    # payloads as lat/lng, lat/long, or WordPress property_* meta names.
    key_pair = re.search(
        r"""["'](?:property_)?(?:latitude|lat)["']\s*[:=]\s*["']?\s*(-?\d+(?:\.\d+)?)\s*["']?
            [\s\S]{0,1000}?
            ["'](?:property_)?(?:longitude|lng|lon|long)["']\s*[:=]\s*["']?\s*(-?\d+(?:\.\d+)?)\s*["']?""",
        normalized,
        re.IGNORECASE | re.VERBOSE,
    )
    if key_pair:
        return public_coordinate_pair(",".join(key_pair.groups()))
    reverse_key_pair = re.search(
        r"""["'](?:property_)?(?:longitude|lng|lon|long)["']\s*[:=]\s*["']?\s*(-?\d+(?:\.\d+)?)\s*["']?
            [\s\S]{0,1000}?
            ["'](?:property_)?(?:latitude|lat)["']\s*[:=]\s*["']?\s*(-?\d+(?:\.\d+)?)\s*["']?""",
        normalized,
        re.IGNORECASE | re.VERBOSE,
    )
    if reverse_key_pair:
        longitude, latitude = reverse_key_pair.groups()
        return public_coordinate_pair(f"{latitude},{longitude}")

    property_latitude = re.search(
        r"""(?:name|id)=["'](?:_)?property_latitude["'][^>]{0,500}?value=["']\s*(-?\d+(?:\.\d+)?)\s*["']""",
        normalized,
        re.IGNORECASE,
    )
    property_longitude = re.search(
        r"""(?:name|id)=["'](?:_)?property_longitude["'][^>]{0,500}?value=["']\s*(-?\d+(?:\.\d+)?)\s*["']""",
        normalized,
        re.IGNORECASE,
    )
    if property_latitude and property_longitude:
        return public_coordinate_pair(f"{property_latitude.group(1)},{property_longitude.group(1)}")

    for tag in re.findall(r"<[^>]{1,12000}>", normalized):
        tag_latitude = re.search(
            r"""\b(?:data-)?(?:latitude|lat)\s*=\s*["']\s*(-?\d+(?:\.\d+)?)\s*["']""",
            tag,
            re.IGNORECASE,
        )
        tag_longitude = re.search(
            r"""\b(?:data-)?(?:longitude|lng|lon|long)\s*=\s*["']\s*(-?\d+(?:\.\d+)?)\s*["']""",
            tag,
            re.IGNORECASE,
        )
        if tag_latitude and tag_longitude:
            return public_coordinate_pair(f"{tag_latitude.group(1)},{tag_longitude.group(1)}")

    bare_pair = re.search(
        r"""\b(?:latitude|lat)\s*=\s*["']?\s*(-?\d+(?:\.\d+)?)\s*["']?
            [\s\S]{0,1000}?
            \b(?:longitude|lng|lon|long)\s*=\s*["']?\s*(-?\d+(?:\.\d+)?)\s*["']?""",
        normalized,
        re.IGNORECASE | re.VERBOSE,
    )
    if bare_pair:
        return public_coordinate_pair(",".join(bare_pair.groups()))
    reverse_bare_pair = re.search(
        r"""\b(?:longitude|lng|lon|long)\s*=\s*["']?\s*(-?\d+(?:\.\d+)?)\s*["']?
            [\s\S]{0,1000}?
            \b(?:latitude|lat)\s*=\s*["']?\s*(-?\d+(?:\.\d+)?)\s*["']?""",
        normalized,
        re.IGNORECASE | re.VERBOSE,
    )
    if reverse_bare_pair:
        longitude, latitude = reverse_bare_pair.groups()
        return public_coordinate_pair(f"{latitude},{longitude}")

    for raw_url in re.findall(r"""https?://[^"'<>\s\\]+""", normalized, re.IGNORECASE):
        parsed = urlparse(raw_url.rstrip("),.;"))
        query = parse_qs(parsed.query)
        # A map viewport/route URL (for example center=..., q=..., ll=... or
        # Google Maps @lat,lng) is not proof that the advertised dwelling is
        # located at that point. Only explicit latitude/longitude parameters
        # are accepted here; source-specific adapters may opt in to stronger
        # coordinate signals when their public contract proves those signals.
        query_latitude = next((query.get(key, [None])[0] for key in ("latitude", "lat") if query.get(key)), None)
        query_longitude = next(
            (query.get(key, [None])[0] for key in ("longitude", "lng", "lon", "long") if query.get(key)),
            None,
        )
        if query_latitude is not None and query_longitude is not None:
            coordinates = public_coordinate_pair(f"{query_latitude},{query_longitude}")
            if coordinates is not None:
                return coordinates

    pair = re.search(
        r"""data-(?:latitude|lat)=["']\s*(-?\d+(?:\.\d+)?)\s*["'][^>]{0,500}
            data-(?:longitude|lng|lon|long)=["']\s*(-?\d+(?:\.\d+)?)\s*["']""",
        normalized,
        re.IGNORECASE | re.VERBOSE | re.DOTALL,
    )
    if pair:
        return public_coordinate_pair(",".join(pair.groups()))
    reverse_pair = re.search(
        r"""data-(?:longitude|lng|lon|long)=["']\s*(-?\d+(?:\.\d+)?)\s*["'][^>]{0,500}
            data-(?:latitude|lat)=["']\s*(-?\d+(?:\.\d+)?)\s*["']""",
        normalized,
        re.IGNORECASE | re.VERBOSE | re.DOTALL,
    )
    if reverse_pair:
        longitude, latitude = reverse_pair.groups()
        return public_coordinate_pair(f"{latitude},{longitude}")
    return None


def strict_check(data: dict[str, Any]) -> bool:
    corpus = clean(
        " ".join(str(data.get(key, "")) for key in ("title", "description", "category", "breadcrumbs", "url"))
    ).casefold()
    return (
        any(term in corpus for term in POSITIVE)
        and not any(term in corpus for term in NEGATIVE)
        and ("alquiler" in corpus or "rent" in corpus)
        and "venta" not in corpus
        and not any(term in corpus for term in LAS_PALMAS)
        and any(term in corpus for term in SANTA_CRUZ)
    )


def is_room_offer(data: dict[str, Any]) -> bool:
    title = clean(data.get("title")).casefold()
    description = clean(data.get("description")).casefold()
    identity = clean(
        " ".join(
            str(data.get(key, ""))
            for key in ("title", "category", "breadcrumbs", "url")
        )
    ).casefold()
    corpus = clean(f"{identity} {description}").casefold()
    if not any(term in corpus for term in POSITIVE):
        return False

    wanted_terms = (
        "busco habitacion",
        "busco habitación",
        "busco cuarto",
        "buscando habitacion",
        "buscando habitación",
        "necesito habitacion",
        "necesito habitación",
        "busco piso",
        "busco alojamiento",
        "se busca habitacion",
        "se busca habitación",
    )
    hard_negative_terms = tuple(term for term in NEGATIVE if term not in wanted_terms)
    if any(term in identity for term in hard_negative_terms):
        return False
    if any(term in clean(f"{title} {data.get('category', '')}").casefold() for term in wanted_terms):
        return False

    opening = description[:500]
    offer_markers = ("se alquila", "alquilo", "ofrezco", "disponible", "para alquilar", "en alquiler")
    return not (
        any(term in opening for term in wanted_terms)
        and not any(marker in opening for marker in offer_markers)
    )


def is_rental(data: dict[str, Any]) -> bool:
    corpus = clean(
        " ".join(
            str(data.get(key, "")) for key in ("title", "description", "category", "breadcrumbs", "url", "price_text")
        )
    ).casefold()
    return (
        any(term in corpus for term in ("alquiler", "se alquila", "alquilo", "arrendamiento", "rent"))
        and "venta" not in corpus
        and "comprar" not in corpus
    )


def is_in_target_province(data: dict[str, Any]) -> bool:
    try:
        latitude, longitude = float(str(data.get("latitude"))), float(str(data.get("longitude")))
        if coordinates_in_target_province(latitude, longitude):
            return True
    except (TypeError, ValueError):
        pass
    explicit_location = clean(
        " ".join(
            str(data.get(key, ""))
            for key in ("province", "city", "municipality", "address", "breadcrumbs", "postcode")
        )
    ).casefold()
    if any(term in explicit_location for term in LAS_PALMAS):
        return False
    if any(term in explicit_location for term in SANTA_CRUZ):
        return True

    # Listing title and description are a safe fallback when a source omits
    # structured address data. Never use arbitrary whole-page text here:
    # global navigation can mention other islands and property operations.
    listing_copy = clean(
        " ".join(str(data.get(key, "")) for key in ("title", "description"))
    ).casefold()
    return not any(term in listing_copy for term in LAS_PALMAS) and any(
        term in listing_copy for term in SANTA_CRUZ
    )


def is_in_import_scope(data: dict[str, Any], scope_key: str) -> bool:
    """Conservative province admission for opt-in geographic slices.

    The legacy Santa Cruz adapter retains its established location policy.
    New provinces require an explicit structured province from the source;
    title, page chrome and broad coordinate boxes are insufficient proof.
    """
    if scope_key == "santa_cruz":
        province = canonical_province(data.get("province"))
        return (spain_country(data.get("country")) and province in {None, 'Santa Cruz de Tenerife'}
                and (province == 'Santa Cruz de Tenerife' or is_in_target_province(data)))
    if not scope_key.startswith("province:"):
        return False
    expected = scope_province(scope_key)
    province = canonical_province(data.get("province"))
    return bool(expected and province == expected and spain_country(data.get("country")))


def coordinates_in_target_province(latitude: float, longitude: float) -> bool:
    return any(
        min_lat <= latitude <= max_lat and min_lng <= longitude <= max_lng
        for min_lat, max_lat, min_lng, max_lng in TARGET_COORDINATE_BOUNDS
    )


def parse_price(value: str) -> tuple[int | None, str | None, str | None, bool]:
    value = clean(value)
    # Use the same verified decimal interpretation as the import admission
    # guard. The older regex could misread "1 200 €" as 200 EUR.
    precise = exact_euro_amount(value)
    amount = int(precise) if precise is not None else None
    lower = re.sub(r'/\\s+', '/', value.casefold())
    period = (
        "month"
        if any(x in lower for x in ("/mes", " al mes", "por mes", "mensual", "/month", "per month", "monthly"))
        else "night"
        if any(x in lower for x in ("/noche", "por noche", "/night", "per night", "nightly", "/día", "/dia"))
        else "week"
        if any(x in lower for x in ("/semana", "/sem", "por semana", "/week", "per week"))
        else None
    )
    return amount, "EUR" if precise is not None else None, period, lower.startswith("desde")

def json_ld(document: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', document, re.IGNORECASE | re.DOTALL
    ):
        try:
            # Public templates sometimes emit literal newlines inside JSON
            # descriptions. Do not HTML-unescape before decoding: &quot; can
            # otherwise corrupt the JSON string boundaries.
            loaded = json.loads(raw, strict=False)
            values = (
                loaded
                if isinstance(loaded, list)
                else loaded.get("@graph", [loaded])
                if isinstance(loaded, dict)
                else []
            )
            result.extend(item for item in values if isinstance(item, dict))
        except json.JSONDecodeError:
            pass
    return result


def embedded_json(document: str) -> list[dict[str, Any]]:
    """Return public application-state objects without relying on a site-specific selector."""
    result: list[dict[str, Any]] = []
    scripts = re.findall(
        r'<script[^>]+(?:id=["\']__NEXT_DATA__["\']|type=["\']application/json["\'])[^>]*>(.*?)</script>',
        document,
        re.IGNORECASE | re.DOTALL,
    )
    scripts.extend(
        re.findall(r"(?:__INITIAL_STATE__|__PRELOADED_STATE__)\s*=\s*({.*?})\s*;</script", document, re.DOTALL)
    )
    for raw in scripts:
        try:
            loaded = json.loads(html.unescape(raw))
        except json.JSONDecodeError:
            continue

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                result.append(value)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(loaded)
    return result


def embedded_link_values(document: str) -> list[str]:
    """Return public application-state string values that may contain URLs.

    Modern result pages can hydrate listing cards from ``__NEXT_DATA__`` while
    leaving only a small subset of card links in server-rendered markup.
    ``embedded_json`` already visits every object, so reading direct scalar
    values covers nested card objects without repeated recursive walks.
    """
    values: list[str] = []
    for item in embedded_json(document):
        for value in item.values():
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, list):
                values.extend(entry for entry in value if isinstance(entry, str))
    return values


def first_text(item: dict[str, Any], *keys: str) -> str:
    return next((clean(item.get(key)) for key in keys if clean(item.get(key))), "")


def structured_classification(structured_items: list[dict[str, Any]]) -> tuple[str, str]:
    """Extract only explicit listing taxonomy and breadcrumb metadata.

    Whole-page text is intentionally excluded: global navigation commonly contains
    sale actions such as ``Comprar`` or ``Pisos en venta`` and must not classify
    an otherwise valid room-rental detail page.
    """
    categories: list[str] = []
    breadcrumbs: list[str] = []

    def add(values: list[str], value: Any) -> None:
        if isinstance(value, dict):
            value = value.get("name") or value.get("label") or value.get("title")
        if isinstance(value, list):
            for child in value:
                add(values, child)
            return
        text = clean(value)[:300]
        if text and text not in values:
            values.append(text)

    category_keys = (
        "category",
        "propertyType",
        "property_type",
        "listingType",
        "offerType",
        "businessType",
        "transactionType",
        "operation",
        "typology",
    )
    for item in structured_items:
        raw_types = item.get("@type", [])
        item_types = {clean(value).casefold() for value in (raw_types if isinstance(raw_types, list) else [raw_types])}
        if item_types & {"organization", "website", "person"}:
            continue
        if "breadcrumblist" in item_types:
            add(categories, item.get("category"))
            for element in item.get("itemListElement", []):
                add(breadcrumbs, element)
            continue
        for key in category_keys:
            add(categories, item.get(key))

    return " | ".join(categories)[:1200], " | ".join(breadcrumbs)[:1800]


def html_breadcrumbs(document: str) -> str:
    """Return text from actual breadcrumb containers, never arbitrary page chrome."""
    values: list[str] = []
    pattern = re.compile(
        r'<(?P<tag>nav|ol|ul|div)\b(?=[^>]*(?:class|id|aria-label)=["\'][^"\']*(?:breadcrumb|migas)[^"\']*["\'])[^>]*>'
        r'(?P<body>.*?)</(?P=tag)>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(document):
        text = clean(match.group("body"))[:600]
        if text and text not in values:
            values.append(text)
    return " | ".join(values)[:1800]


def detail_document_has_listing_signals(document: str) -> bool:
    """Return whether a detail response contains usable public listing data.

    A 200 response can be only an application shell. In that case the caller
    may use the existing anonymous Chromium fallback, without interacting with
    challenges or authentication.
    """
    title = meta_content(document, "og:title")
    if not title:
        heading = re.search(r"<h1[^>]*>(.*?)</h1>", document, re.IGNORECASE | re.DOTALL)
        title = clean(heading.group(1)) if heading else ""
    if not title:
        structured = json_ld(document) + embedded_json(document)
        title = next(
            (
                first_text(item, "name", "title", "headline")
                for item in structured
                if first_text(item, "name", "title", "headline")
            ),
            "",
        )
    corpus = clean(document).casefold()
    has_price = bool(re.search(r"[\d.]+(?:,\d+)?\s*€", corpus))
    has_room = any(term in corpus for term in POSITIVE)
    return bool(title and has_price and has_room)


def meta_content(document: str, name: str) -> str:
    pattern = rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']'
    match = re.search(pattern, document, re.IGNORECASE)
    if not match:
        pattern = rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']'
        match = re.search(pattern, document, re.IGNORECASE)
    return clean(match.group(1)) if match else ""


def parse_optional_date(value: Any) -> date | None:
    text = clean(value)
    for pattern in (r"\d{4}-\d{2}-\d{2}", r"\d{2}/\d{2}/\d{4}"):
        match = re.search(pattern, text)
        if match:
            try:
                return date.fromisoformat(match.group(0)) if "-" in match.group(0) else datetime.strptime(
                    match.group(0), "%d/%m/%Y"
                ).replace(tzinfo=UTC).date()
            except ValueError:
                return None
    return None


def parse_optional_datetime(value: Any) -> datetime | None:
    text = clean(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed_date = parse_optional_date(text)
        return datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC) if parsed_date else None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC)


def explicit_bool(corpus: str, positive: tuple[str, ...], negative: tuple[str, ...]) -> bool | None:
    if any(value in corpus for value in negative):
        return False
    if any(value in corpus for value in positive):
        return True
    return None


def public_detail_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Conservative extraction of optional public room facts; missing remains None."""
    corpus = clean(" ".join(str(data.get(key, "")) for key in ("title", "description", "category", "breadcrumbs"))).casefold()
    result: dict[str, Any] = {"amenities": []}
    stay = re.search(r"(?:estancia|alquiler)\s+m[ií]nima\s*(?:de)?\s*(\d+)\s*(mes(?:es)?|noche(?:s)?)", corpus)
    if stay:
        result["minimum_stay_months" if stay.group(2).startswith("mes") else "minimum_nights"] = int(stay.group(1))
    deposit = re.search(r"(?:fianza|dep[oó]sito)\s*(?:de|:)??\s*([\d.]+(?:,\d+)?)\s*€", corpus)
    if deposit:
        result["deposit_amount"] = int(float(deposit.group(1).replace(".", "").replace(",", ".")))
        result["deposit_text"] = deposit.group(0)
    bills = re.search(r"(?:gastos|suministros|facturas)[^.]{0,80}", corpus)
    if bills:
        result["bills_text"] = bills.group(0).strip()
    result["bills_included"] = explicit_bool(corpus, ("gastos incluidos", "suministros incluidos"), ("gastos no incluidos", "gastos aparte", "suministros aparte"))
    result["furnished"] = explicit_bool(corpus, ("amueblado", "amueblada", "con muebles"), ("sin amueblar", "no amueblado"))
    result["pets_allowed"] = explicit_bool(corpus, ("mascotas permitidas", "se aceptan mascotas"), ("no mascotas", "mascotas no", "no se admiten mascotas"))
    result["children_allowed"] = explicit_bool(corpus, ("niños permitidos", "se aceptan niños"), ("sin niños", "no niños", "no se admiten niños"))
    result["smoking_allowed"] = explicit_bool(corpus, ("se permite fumar", "fumadores permitidos"), ("no fumar", "no fumadores", "prohibido fumar"))
    result["empadronamiento_allowed"] = explicit_bool(corpus, ("empadronamiento permitido", "se permite empadronamiento"), ("sin empadronamiento", "no empadronamiento"))
    size = re.search(r"(\d{1,3})\s*m(?:²|2)\b", corpus)
    if size:
        result["room_size_m2"] = int(size.group(1))
    capacity = re.search(r"(?:hasta|para)\s*(\d+)\s*personas", corpus)
    if capacity:
        result["room_capacity"] = int(capacity.group(1))
    # Keep this compatible with the persisted/API enum.  Student-only is a
    # restriction, not a gender enum value.
    result["tenant_requirement"] = (
        "single-woman" if "solo mujeres" in corpus else "single-man" if "solo hombres" in corpus else None
    )
    result["bathroom"] = "Baño privado" if "baño privado" in corpus else "Baño compartido" if "baño compartido" in corpus else None
    result["kitchen"] = "Cocina compartida" if "cocina compartida" in corpus else "Cocina privada" if "cocina privada" in corpus else None
    amenities = {"wifi": "wifi", "internet": "internet", "aire acondicionado": "aire acondicionado", "ascensor": "ascensor", "terraza": "terraza", "parking": "parking"}
    result["amenities"] = [label for token, label in amenities.items() if token in corpus]
    result["restrictions"] = []
    if "solo estudiantes" in corpus:
        result["restrictions"].append("Solo estudiantes")
    result["available_from"] = parse_optional_date(data.get("available_from") or data.get("availableFrom") or data.get("availability"))
    result["published_at"] = parse_optional_datetime(data.get("datePublished") or data.get("published_at"))
    result["advertiser_name"] = clean(data.get("advertiser_name") or data.get("seller") or data.get("author")) or None
    result["advertiser_type"] = clean(data.get("advertiser_type") or data.get("seller_type")) or None
    return result


def bounded_photo_urls(values: list[str] | tuple[str, ...]) -> list[str]:
    """Keep one public URL per exact source image and enforce the product gallery ceiling."""
    result: list[str] = []
    for value in values:
        candidate = html.unescape(str(value)).strip()
        if not candidate.startswith(("http://", "https://")) or candidate in result:
            continue
        result.append(candidate)
        if len(result) >= MAX_LISTING_PHOTOS:
            break
    return result


@dataclass
class NormalizedListing:
    source_name: str
    external_id: str
    source_url: str
    title: str
    description: str
    city: str
    area: str
    rental_mode: str
    source_price_text: str
    price_amount: int
    price_currency: str | None
    price_period: str | None
    price_is_from: bool
    room_type: str = "Habitación individual"
    latitude: float | None = None
    longitude: float | None = None
    photos: list[str] = field(default_factory=list)
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    minimum_stay_months: int | None = None
    minimum_nights: int | None = None
    deposit_amount: int | None = None
    deposit_text: str | None = None
    bills_included: bool | None = None
    bills_text: str | None = None
    furnished: bool | None = None
    bathroom: str | None = None
    kitchen: str | None = None
    room_size_m2: int | None = None
    room_capacity: int | None = None
    tenant_requirement: str | None = None
    pets_allowed: bool | None = None
    children_allowed: bool | None = None
    smoking_allowed: bool | None = None
    empadronamiento_allowed: bool | None = None
    amenities: list[str] = field(default_factory=list)
    restrictions: list[str] = field(default_factory=list)
    advertiser_name: str | None = None
    advertiser_type: str | None = None
    available_from: date | None = None
    published_at: datetime | None = None
    public_address: str | None = None
    bedroom_count: int | None = None
    province: str | None = None
    country: str | None = None
    weekly_price_amount: int | None = None

    def __post_init__(self) -> None:
        self.photos = bounded_photo_urls(self.photos)

    @property
    def photos_complete(self) -> bool:
        # Keep snapshot shape compatible with previous releases. The existing
        # raw-payload mapping carries additive provider evidence.
        return self.raw_payload.get("photos_complete", True) is True

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(
            "|".join(
                (
                    self.source_name,
                    self.external_id,
                    self.title,
                    self.description,
                    self.city,
                    self.area,
                    self.public_address or "",
                    self.source_price_text,
                    self.room_type,
                    self.rental_mode,
                    str(self.bedroom_count),
                    self.province or "",
                    self.price_period or "",
                    str(self.latitude or ""),
                    str(self.longitude or ""),
                    "|".join(self.photos),
                    self.phone or "",
                    self.whatsapp or "",
                    self.email or "",
                    str(self.minimum_stay_months or ""),
                    str(self.minimum_nights or ""),
                    str(self.deposit_amount or ""),
                    self.deposit_text or "",
                    self.bills_text or "",
                    "|".join(self.amenities),
                    "|".join(self.restrictions),
                    *(() if self.photos_complete else ("partial_gallery",)),
                )
            ).encode()
        ).hexdigest()


class ExternalListingSource(ABC):
    name: str
    scope_key: str = "santa_cruz"
    discovery_urls: tuple[str, ...]
    domain: str
    url_tokens: tuple[str, ...]
    listing_url_pattern: re.Pattern[str]
    discovery_selectors: tuple[str, ...] = ()
    max_discovery_pages = 30
    render_incomplete_detail = False
    removed_markers: tuple[str, ...] = (
        "anuncio eliminado", "ya no está disponible", "ya no esta disponible", "ya no disponible", "anuncio caducado",
        "property unavailable", "listing unavailable", "anuncio no disponible",
    )

    def __init__(self) -> None:
        settings = get_settings()
        self.client = httpx.AsyncClient(
            timeout=settings.external_import_request_timeout_seconds,
            headers={"User-Agent": settings.external_import_user_agent, "Accept-Language": "es-ES,es;q=0.9"},
            follow_redirects=True,
            event_hooks={"request": [self._validate_provider_request]},
        )
        self.not_found_urls: set[str] = set()
        # A 410 or explicit removed page proves removal. A bare redirect to
        # a catalogue does not; retaining the reason supports diagnostics.
        self.removed_urls: set[str] = set()
        self.discovery_diagnostics: dict[str, dict[str, Any]] = {}
        self.blocked_diagnostic: dict[str, Any] | None = None
        self.discovery_checkpoint: dict[str, Any] | None = None
        self.resumable_discovery = False
        self._playwright: Any = None
        self._browser: Any = None
        self._browser_context: Any = None
        self._browser_lock = asyncio.Lock()

    async def _validate_provider_request(self, request: httpx.Request) -> None:
        # The global public-network guard also checks every redirect's DNS
        # and peer address. This additional guard keeps navigation on-provider.
        if not hostname_matches_domain(str(request.url), self.domain) or request.url.username or request.url.password:
            raise httpx.InvalidURL("External source request escaped its provider")

    async def close(self) -> None:
        await self.client.aclose()
        if self._browser_context:
            await self._browser_context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser_context = self._browser = self._playwright = None

    def _record_page(
        self, url: str, document: str | None, *, status: int | None, final_url: str | None, method: str = "GET"
    ) -> None:
        links = LINK.findall(document or "")
        title_match = re.search(r"<title[^>]*>(.*?)</title>", document or "", re.IGNORECASE | re.DOTALL)
        self.discovery_diagnostics[url] = {
            "method": method,
            "url": url,
            "status": status,
            "final_url": final_url or url,
            "title": clean(title_match.group(1)) if title_match else "",
            "body_preview": clean(document or "")[:3000],
            "anchor_count": len(links),
            "hrefs": [html.unescape(link) for link in links[:50]],
            "selectors": list(self.discovery_selectors),
        }

    def _save_discovery_artifacts(self, url: str, document: str | None, screenshot: bytes | None = None) -> dict[str, str]:
        """Persist anonymous error evidence outside the database for operator inspection."""
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        directory = get_settings().media_root / "external-import-errors" / self.name.casefold()
        directory.mkdir(parents=True, exist_ok=True)
        paths: dict[str, str] = {}
        if document is not None:
            html_path = directory / f"{digest}.html"
            html_path.write_text(document, encoding="utf-8")
            paths["html"] = str(html_path)
        if screenshot is not None:
            screenshot_path = directory / f"{digest}.png"
            screenshot_path.write_bytes(screenshot)
            paths["screenshot"] = str(screenshot_path)
        return paths

    def _challenge_type(self, document: str) -> str | None:
        """A CAPTCHA script/contact-widget reference is not an access challenge.

        Only explicit challenge pages or strong anti-bot responses should block
        anonymous parsing. A page with ambiguous content remains subject to the
        normal detail/discovery contract; it is never evidence for deletion.
        """
        body = document.casefold()
        if any(marker in body for marker in (
            "geetest", "pardon our interruption", "cf-chl-", "verify you are human",
        )):
            return "access_challenge"
        if "captcha" not in body:
            return None
        # A contact-form CAPTCHA prompt is not a page-level access gate when
        # the actual rental detail is already available anonymously.
        if self.has_current_detail(document):
            return None
        if re.search(
            r"<(?:title|h1|h2)\b[^>]*>[^<]{0,160}\b(?:captcha|recaptcha)\b",
            document,
            re.IGNORECASE,
        ):
            return "captcha_gate"
        visible = re.sub(
            r"<(?:script|style)\b[^>]*>.*?</(?:script|style)\s*>",
            " ",
            document,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if re.search(
            r"\b(?:solve|complete|enter|introduce|resuelve|completa)\s+"
            r"(?:(?:the|el|un)\s+)?(?:captcha|recaptcha)\b",
            clean(visible),
            re.IGNORECASE,
        ):
            return "captcha_gate"
        return None

    def _raise_if_challenged(self, url: str, document: str) -> None:
        challenge_type = self._challenge_type(document)
        if challenge_type:
            diagnostic = self.discovery_diagnostics.get(url, {})
            self.blocked_diagnostic = {
                "challenge_type": challenge_type,
                **diagnostic,
                "paths": self._save_discovery_artifacts(url, document),
            }
            raise SourceBlocked("public source access challenge")

    async def request(self, url: str) -> str | None:
        for attempt in range(3):
            try:
                response = await self.client.get(url)
                self._record_page(url, response.text, status=response.status_code, final_url=str(response.url))
                if response.status_code == 202 and not response.text.strip():
                    self.blocked_diagnostic = {"challenge_type": "empty_http_202", **self.discovery_diagnostics[url]}
                    raise SourceBlocked("public source returned no anonymous content (HTTP 202)")
                if self._challenge_type(response.text):
                    # Capture the equivalent public Chromium response and screenshot once;
                    # do not attempt to solve or interact with the challenge.
                    if get_settings().external_import_playwright_enabled:
                        await self.render_public_page(url)
                    self._raise_if_challenged(url, response.text)
                logger.info(
                    "external_source_http", extra={"source": self.name, "method": "GET", "url": url,
                                                   "status": response.status_code, "final_url": str(response.url)}
                )
                if response.status_code == 404:
                    self.not_found_urls.add(url)
                    return None
                if response.status_code == 410:
                    self.removed_urls.add(url)
                    return None
                if response.status_code in {403, 405, 429} or response.status_code >= 500:
                    if response.status_code in {403, 405} and get_settings().external_import_playwright_enabled:
                        rendered = await self.render_public_page(url)
                        if rendered:
                            return rendered
                    if response.status_code == 403 and attempt == 2:
                        diagnostic = self.discovery_diagnostics.get(url, {})
                        self.blocked_diagnostic = {
                            "challenge_type": "http_403",
                            **diagnostic,
                            "paths": self._save_discovery_artifacts(url, response.text),
                        }
                        raise SourceBlocked("public source denied anonymous access")
                    if attempt == 2:
                        raise RuntimeError(f"HTTP {response.status_code}")
                    await asyncio.sleep(2**attempt)
                    continue
                if self.is_listing_url(url) and 200 <= response.status_code < 300:
                    corpus = clean(response.text).casefold()
                    if not self.has_current_detail(response.text) and (
                        any(marker in corpus for marker in self.removed_markers) or "listing expired" in corpus
                    ):
                        self.removed_urls.add(url)
                        return None
                    if not self.is_listing_url(str(response.url)):
                        return None
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as exc:
                logger.info("external_source_http_error", extra={"source": self.name, "method": "GET", "url": url,
                                                                   "error": type(exc).__name__})
                if get_settings().external_import_playwright_enabled:
                    rendered = await self.render_public_page(url)
                    if rendered:
                        return rendered
                if attempt == 2:
                    raise
                await asyncio.sleep(2**attempt)
        return None

    async def render_public_page(self, url: str) -> str | None:
        """Optional anonymous rendering fallback; never solves challenges or uses cookies."""
        try:
            from playwright.async_api import Error as PlaywrightError
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError:
            return None
        try:
            if not hostname_matches_domain(url, self.domain):
                return None
            await validate_public_browser_url(url)
            async with self._browser_lock:
                if not self._browser_context:
                    self._playwright = await async_playwright().start()
                    self._browser = await self._playwright.chromium.launch(headless=True)
                    settings = get_settings()
                    context_options: dict[str, Any] = {
                        "locale": "es-ES",
                        "service_workers": "block",
                        "accept_downloads": False,
                    }
                    if settings.external_import_user_agent.startswith("Mozilla/"):
                        context_options["user_agent"] = settings.external_import_user_agent
                    self._browser_context = await self._browser.new_context(**context_options)
                    await configure_public_browser_context(self._browser_context)
                page = await self._browser_context.new_page()
                try:
                    response = await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=get_settings().external_import_request_timeout_seconds * 1000,
                    )
                    # Pages are allowed to hydrate after DOMContentLoaded, but a hung network must not hold a run.
                    await page.wait_for_timeout(750)
                    document: str | None = await page.content()
                    status = response.status if response else None
                    final_url = page.url
                    await validate_public_browser_url(final_url)
                    if not hostname_matches_domain(final_url, self.domain):
                        return None
                    self._record_page(url, document, status=status, final_url=final_url, method="BROWSER_GET")
                    logger.info("external_source_browser", extra={"source": self.name, "method": "BROWSER_GET", "url": url,
                                                                   "status": status, "final_url": final_url})
                    if status is not None and status >= 400:
                        paths = self._save_discovery_artifacts(url, document, await page.screenshot(full_page=True))
                        if document and ("geetest" in document.casefold() or "pardon our interruption" in document.casefold()):
                            self.blocked_diagnostic = {"challenge_type": "geetest", **self.discovery_diagnostics[url], "paths": paths}
                            raise SourceBlocked("public source access challenge")
                        document = None
                    return document
                finally:
                    await page.close()
        except (OSError, httpx.HTTPError, PlaywrightError, PlaywrightTimeoutError, ValueError):
            diagnostic = self.discovery_diagnostics.get(url, {})
            self._save_discovery_artifacts(url, diagnostic.get("html"))
            return None

    def is_listing_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return (
            parsed.scheme in {"http", "https"}
            and hostname_matches_domain(url, self.domain)
            and url.rstrip("/") not in {discovery.rstrip("/") for discovery in self.discovery_urls}
            and bool(self.listing_url_pattern.search(parsed.path))
        )

    def accepts_location(self, data: dict[str, Any]) -> bool:
        return is_in_import_scope(data, self.scope_key)

    def accepts_coordinates(self, latitude: float, longitude: float) -> bool:
        check = coordinates_in_target_province if self.scope_key == "santa_cruz" else coordinates_in_spain
        return check(latitude, longitude)

    def is_pagination_url(self, url: str) -> bool:
        parsed = urlparse(url)
        location = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        return parsed.scheme in {"http", "https"} and hostname_matches_domain(url, self.domain) and bool(
            re.search(
                r"(?:[?&](?:pagina|page)=\d+|/pagina(?:-|/)\d+(?:\.html?)?/?|/\d+/?$)",
                location,
                re.IGNORECASE,
            )
        )

    def visible_result_count(self, document: str) -> int | None:
        match = re.search(r"\b([1-9]\d*)\s+(?:anuncios|resultados|viviendas|habitaciones|properties)\b", clean(document), re.IGNORECASE)
        return int(match.group(1)) if match else None

    async def discover_listing_urls(self) -> DiscoveryResult:
        seen: set[str] = set()
        visited: set[tuple[str, str]] = set()
        queue = [(url, url) for url in dict.fromkeys(self.discovery_urls)]
        checkpoint = self.discovery_checkpoint if self.resumable_discovery else None
        resumed = bool(checkpoint)
        if checkpoint:
            if checkpoint.get("routes") != list(self.discovery_urls) or checkpoint.get("version") != 1:
                raise ValueError("Scope routes changed; review and clear the discovery checkpoint")
            for key in ("pending", "visited"):
                entries = checkpoint.get(key)
                if not isinstance(entries, list) or len(entries) > 10_000:
                    raise ValueError("Invalid bounded discovery checkpoint")
                for entry in entries:
                    if not isinstance(entry, list) or len(entry) != 2:
                        raise ValueError("Invalid discovery checkpoint page")
                    page, root = entry
                    parsed = urlparse(page)
                    if (root not in self.discovery_urls or parsed.scheme != "https"
                            or parsed.hostname not in {self.domain, "www." + self.domain}
                            or parsed.username or parsed.password or parsed.port not in {None, 443}
                            or (page != root and not self.is_pagination_url(page))):
                        raise ValueError("Discovery checkpoint escaped its published provider routes")
            queue = [(entry[0], entry[1]) for entry in checkpoint["pending"]]
            visited = {(entry[0], entry[1]) for entry in checkpoint["visited"]}
        visited_this_run = 0
        failed_pages: list[str] = []
        retry_pages: list[tuple[str, str]] = []
        blocked = False
        roots: dict[str, dict[str, Any]] = {
            root: {"urls": set(), "signatures": set(), "expected_total": None, "visited_pages": 0,
                   "failed_pages": [], "budget_limited": False}
            for root in self.discovery_urls
        }
        previous_signatures = checkpoint.get("signatures", {}) if checkpoint else {}
        if not isinstance(previous_signatures, dict):
            raise TypeError("Invalid discovery checkpoint signatures")
        for root, state in roots.items():
            signatures = previous_signatures.get(root, [])
            if (not isinstance(signatures, list) or len(signatures) > 10_000
                    or any(not isinstance(s, str) or not re.fullmatch(r"[a-f0-9]{64}", s) for s in signatures)):
                raise ValueError("Invalid bounded discovery signatures")
            state["signatures"].update(signatures)
        while queue and visited_this_run < self.max_discovery_pages:
            page, root = queue.pop(0)
            state = roots[root]
            if (page, root) in visited:
                continue
            visited.add((page, root))
            visited_this_run += 1
            state["visited_pages"] += 1
            try:
                document = await self.request(page)
            except SourceBlocked:
                retry_pages.append((page, root))
                blocked = True
                state["failed_pages"].append(page)
                failed_pages.append(page)
                break
            except (httpx.HTTPError, RuntimeError):
                retry_pages.append((page, root))
                state["failed_pages"].append(page)
                failed_pages.append(page)
                continue
            if not document:
                retry_pages.append((page, root))
                state["failed_pages"].append(page)
                failed_pages.append(page)
                continue
            if state["expected_total"] is None:
                state["expected_total"] = self.visible_result_count(document)
            static_links = LINK.findall(document)
            embedded_links = embedded_link_values(document)
            has_listing_link = any(
                self.is_listing_url(urljoin(page, html.unescape(href))) for href in [*static_links, *embedded_links]
            )
            if not has_listing_link and get_settings().external_import_playwright_enabled:
                rendered = await self.render_public_page(page)
                if rendered:
                    static_links = LINK.findall(rendered)
                    embedded_links = embedded_link_values(rendered)
            page_urls: set[str] = set()
            for href in [*static_links, *embedded_links]:
                url = urljoin(page, html.unescape(href).split("#", 1)[0])
                if self.is_listing_url(url):
                    # Gallery/map variants on a card are the same public listing.
                    page_urls.add(url.split("?", 1)[0])
            signature = hashlib.sha256("\n".join(sorted(page_urls)).encode()).hexdigest() if page_urls else ""
            if signature and signature in state["signatures"] and page != root:
                state["failed_pages"].append(page)
                failed_pages.append(page)
                continue
            state["signatures"].add(signature)
            state["urls"].update(page_urls)
            seen.update(page_urls)
            for href in static_links:
                url = urljoin(page, html.unescape(href).split("#", 1)[0])
                if (not self.is_listing_url(url) and self.is_pagination_url(url)
                        and (url, root) not in visited and (url, root) not in queue):
                    if len(queue) < (10_000 if self.resumable_discovery else self.max_discovery_pages):
                        queue.append((url, root))
                    else:
                        state["budget_limited"] = True
            if not state["urls"] and not has_listing_link and re.search(
                r"\b[1-9]\d*\s+(?:anuncios|resultados|viviendas|habitaciones)\b", document, re.IGNORECASE
            ):
                self._save_discovery_artifacts(page, document)
                retry_pages.append((page, root))
                state["failed_pages"].append(page)
                failed_pages.append(page)
        reached_last_page = not queue and not any(state["budget_limited"] for state in roots.values())
        evidence = {}
        for root, state in roots.items():
            last_page = bool(state["visited_pages"]) and not state["budget_limited"] and not any(r == root for _, r in queue)
            expected = state["expected_total"]
            evidence[root] = {
                "visited_pages": state["visited_pages"], "expected_total": expected,
                "seen": len(state["urls"]), "failed_pages": state["failed_pages"], "reached_last_page": last_page,
                "complete": last_page and not state["failed_pages"] and (expected is None or len(state["urls"]) >= expected),
            }
        complete = bool(evidence) and not blocked and not failed_pages and all(r["complete"] for r in evidence.values())
        continuation = None
        if self.resumable_discovery:
            for retry in retry_pages:
                visited.discard(retry)
            pending = list(dict.fromkeys([*queue, *retry_pages]))
            if len(visited) + len(pending) > 10_000 or any(s["budget_limited"] for s in roots.values()):
                raise ValueError("Discovery checkpoint capacity reached; operator review required")
            if pending:
                continuation = {
                    "version": 1, "routes": list(self.discovery_urls),
                    "pending": [list(entry) for entry in pending],
                    "visited": [list(entry) for entry in sorted(visited)],
                    "signatures": {root: sorted(state["signatures"]) for root, state in roots.items()},
                }
            # Each continued window contains only part of the catalogue. Even
            # the final window cannot reconcile unseen rows as absent.
            complete = complete and not resumed
            if resumed:
                failed_pages.append("continued_discovery_window")
        # Totals from overlapping roots are not a unique inventory count.
        expected_total = next(iter(evidence.values()))["expected_total"] if len(evidence) == 1 else None
        return DiscoveryResult(seen, complete, visited_this_run, expected_total, failed_pages,
                               reached_last_page, blocked, evidence, continuation)

    @staticmethod
    def has_current_detail(document: str) -> bool:
        return detail_document_has_listing_signals(document) or bool(
            re.search(r"<h1\b[^>]*>.+?</h1>", document, re.IGNORECASE | re.DOTALL)
            and re.search(r"\d[\d.,]*\s*€", clean(document))
        )

    async def check_listing_state(self, source_url: str) -> str:
        """Check a missing detail URL without treating access errors as removal."""
        try:
            response = await self.client.get(source_url)
        except httpx.TimeoutException:
            return "temporary_error"
        except httpx.HTTPError:
            return "temporary_error"
        document = response.text
        if response.status_code == 403 or (response.status_code == 202 and not document.strip()) or self._challenge_type(document):
            return "blocked"
        if response.status_code == 404:
            return "not_found"
        if response.status_code == 410:
            return "removed"
        if response.status_code == 429 or response.status_code >= 500:
            return "temporary_error"
        if response.status_code >= 400:
            return "unknown"
        final_url = str(response.url)
        corpus = clean(document).casefold()
        if 200 <= response.status_code < 300 and self.is_listing_url(final_url) and self.has_current_detail(document):
            return "active"
        if "anuncio caducado" in corpus or "listing expired" in corpus:
            return "expired"
        if any(marker in corpus for marker in self.removed_markers):
            return "removed"
        return "unknown"

    async def fetch_listing(self, url: str) -> str | None:
        document = await self.request(url)
        if not self.render_incomplete_detail or not document or detail_document_has_listing_signals(document):
            return document
        if get_settings().external_import_playwright_enabled:
            rendered = await self.render_public_page(url)
            if rendered:
                return rendered
        return document

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        ld = json_ld(document)
        state = embedded_json(document)
        all_structured_items = [item for item in ld + state if isinstance(item, dict)]
        structured_items = []
        for candidate in all_structured_items:
            raw_types = candidate.get("@type", [])
            candidate_types = raw_types if isinstance(raw_types, list) else [raw_types]
            if not any(clean(value).casefold() in {"organization", "website", "breadcrumblist", "person"}
                       for value in candidate_types):
                structured_items.append(candidate)
        item = next(
            (
                x
                for x in structured_items
                if first_text(x, "name", "title", "headline") and first_text(x, "description", "body")
            ),
            {},
        )
        title_match = re.search(r"<title[^>]*>(.*?)</title>", document, re.IGNORECASE | re.DOTALL)
        body = clean(document)
        images: list[str] = []
        for structured in structured_items:
            for key in ("image", "images", "photos", "photo"):
                values = structured.get(key) or []
                if not isinstance(values, list):
                    values = [values]
                for value in values:
                    image_url = (
                        value.get("contentUrl") or value.get("url") or value.get("image")
                        if isinstance(value, dict)
                        else value
                    )
                    if isinstance(image_url, str) and image_url.startswith("http") and image_url not in images:
                        images.append(image_url)
        if not images and meta_content(document, "og:image"):
            images = [meta_content(document, "og:image")]
        price_match = re.search(
            r"(?:Desde\s*)?[\d.]+(?:,\d+)?\s*\u20ac(?:\s*(?:/\s*|al\s+|por\s+)(?:mes|noche|semana)|\s*mensual)?",
            body,
            re.IGNORECASE,
        )
        raw_geo = item.get("geo") or item.get("coordinates") or next(
            (
                structured.get("geo") or structured.get("coordinates")
                for structured in structured_items
                if isinstance(structured.get("geo") or structured.get("coordinates"), dict)
            ),
            item.get("geo") or item.get("coordinates"),
        )
        geo: dict[str, Any] = raw_geo if isinstance(raw_geo, dict) else {}
        raw_address = item.get("address") or next(
            (structured.get("address") for structured in structured_items if isinstance(structured.get("address"), dict)),
            item.get("address"),
        )
        address: dict[str, Any] = raw_address if isinstance(raw_address, dict) else {}
        latitude = geo.get("latitude") or geo.get("lat") or item.get("latitude") or item.get("lat")
        longitude = geo.get("longitude") or geo.get("lng") or item.get("longitude") or item.get("lng")
        if latitude is None or longitude is None:
            coordinate_match = re.search(
                r'"(?:latitude|lat)"\s*:\s*([-\d.]+).*?"(?:longitude|lng)"\s*:\s*([-\d.]+)',
                document,
                re.IGNORECASE | re.DOTALL,
            )
            if coordinate_match:
                latitude, longitude = coordinate_match.groups()
        if latitude is None or longitude is None:
            map_coordinates = public_map_coordinates(document)
            if map_coordinates is not None:
                latitude, longitude = map_coordinates
        area = first_text(
            address,
            "addressSubLocality",
            "addressDistrict",
            "neighborhood",
            "district",
            "suburb",
            "area",
        )
        if not area:
            area = next(
                (
                    first_text(
                        structured,
                        "addressSubLocality",
                        "addressDistrict",
                        "neighborhood",
                        "district",
                        "suburb",
                        "area",
                    )
                    for structured in structured_items
                    if first_text(
                        structured,
                        "addressSubLocality",
                        "addressDistrict",
                        "neighborhood",
                        "district",
                        "suburb",
                        "area",
                    )
                ),
                "",
            )
        structured_category, structured_breadcrumbs = structured_classification(all_structured_items)
        breadcrumbs = " | ".join(
            value for value in (structured_breadcrumbs, html_breadcrumbs(document)) if value
        )[:1800]
        return {
            "title": first_text(item, "name", "title", "headline")
            or meta_content(document, "og:title")
            or clean(title_match.group(1) if title_match else ""),
            "description": first_text(item, "description", "body", "text")
            or meta_content(document, "og:description")
            or meta_content(document, "description"),
            "category": structured_category,
            "breadcrumbs": breadcrumbs,
            "url": url,
            "price_text": price_match.group(0) if price_match else "",
            "images": images,
            "city": clean(address.get("addressLocality")),
            "municipality": clean(address.get("addressLocality")),
            "province": clean(address.get("addressRegion")),
            "country": address.get("addressCountry"),
            "property_type": item.get("propertyType") or item.get("property_type"),
            "bedroom_count": item.get("numberOfBedrooms") if item.get("numberOfBedrooms") is not None else item.get("bedrooms"),
            "rental_category": item.get("rentalCategory") or item.get("rental_mode"),
            "operation": item.get("transactionType") or item.get("operation"),
            "area": area,
            "address": clean(address.get("streetAddress")),
            "postcode": clean(address.get("postalCode")),
            "phone": next(
                (first_text(structured, "telephone", "phone", "contactPhone") for structured in structured_items
                 if first_text(structured, "telephone", "phone", "contactPhone")),
                (PHONE.findall(body) or [None])[0],
            ),
            "whatsapp": next(
                (first_text(structured, "whatsapp", "contactWhatsapp", "whatsApp") for structured in structured_items
                 if first_text(structured, "whatsapp", "contactWhatsapp", "whatsApp")),
                None,
            ),
            "email": next(
                (first_text(structured, "email", "contactEmail") for structured in structured_items
                 if first_text(structured, "email", "contactEmail")),
                (EMAIL.findall(body) or [None])[0],
            ),
            "latitude": latitude,
            "longitude": longitude,
            "raw": {"jsonLd": ld, "embeddedJson": state, "html": document[:200000]},
        }

    def normalize_listing(self, data: dict[str, Any], url: str) -> NormalizedListing | None:
        data = {**data, "url": url.split("#", 1)[0].split("?", 1)[0]}
        url = data["url"]
        if data.get("deleted") or clean(data.get("status")).casefold() in {"deleted", "removed", "not found"}:
            return None
        title = clean(data.get("title"))
        target_type = property_type(data, self.name)
        if not title or target_type is None or not self.accepts_location(data):
            return None
        amount, currency, period, price_is_from = parse_price(str(data.get("price_text", "")))
        corpus = clean(
            " ".join(str(data.get(x, "")) for x in ("title", "description", "category", "breadcrumbs", "url"))
        ).casefold()
        price = rental_price(data, self.name, amount, period)
        if price is None or currency != "EUR":
            return None
        if not long_term_price_allowed(price.mode, price.amount) or (
            price.mode == "long"
            and not long_term_price_allowed("long", exact_euro_amount(str(data.get("price_text", ""))))
        ):
            return None
        if self.scope_key.endswith(":holiday") and price.mode != "holiday":
            return None
        if self.scope_key.endswith(":holiday") and target_type == "Habitación compartida":
            return None
        supplied_city = clean(data.get("city") or data.get("municipality"))
        city = supplied_city or next(
            (
                municipality.title()
                for municipality in sorted(SANTA_CRUZ, key=len, reverse=True)
                if municipality not in PROVINCE_ONLY and municipality in corpus
            ),
            "",
        )
        if not city:
            return None
        area = clean(
            data.get("area")
            or data.get("neighborhood")
            or data.get("district")
            or data.get("suburb")
        ) or city
        public_address = clean(data.get("public_address") or data.get("address")) or area
        found = re.search(r"(?:inmueble|anuncio|ad|id)[=/_-](\d+)", url, re.IGNORECASE) or re.search(r"(\d{5,})", url)
        external_id = found.group(1) if found else hashlib.sha256(url.encode()).hexdigest()[:24]
        photos = [str(x) for x in data.get("images", []) if isinstance(x, str) and x.startswith("http")]
        latitude, longitude = data.get("latitude"), data.get("longitude")
        try:
            latitude, longitude = float(str(latitude)), float(str(longitude))
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                latitude = longitude = None
        except (TypeError, ValueError):
            latitude = longitude = None
        if latitude is not None and longitude is not None and not self.accepts_coordinates(latitude, longitude):
            return None
        details = public_detail_fields(data)
        return NormalizedListing(
            self.name,
            external_id,
            url,
            title[:240],
            clean(data.get("description")),
            city,
            area,
            price.mode,
            clean(data.get("price_text")),
            price.amount,
            currency,
            price.period,
            price_is_from,
            target_type,
            latitude,
            longitude,
            photos,
            data.get("phone"),
            data.get("whatsapp"),
            data.get("email"),
            {**data.get("raw", data), "photos_complete": data.get("photos_complete", True) is True},
            public_address=public_address,
            bedroom_count=bedroom_count(data) if target_type == "Apartamento de 1 dormitorio" else 0 if target_type == "Estudio" else None,
            province=canonical_province(data.get("province")),
            country="ES",
            weekly_price_amount=price.weekly_amount,
            **details,
        )


class IdealistaSource(ExternalListingSource):
    name = "Idealista"
    domain = "idealista.com"
    url_tokens = ("/inmueble/",)
    listing_url_pattern = re.compile(r"/inmueble/\d+/?$", re.IGNORECASE)
    discovery_selectors = ('a[href*="/inmueble/"]',)
    discovery_urls = ("https://www.idealista.com/alquiler-habitacion/santa-cruz-de-tenerife-provincia/",)
    removed_markers = ExternalListingSource.removed_markers + ("este anuncio ya no existe", "inmueble no disponible")

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        data = super().parse_listing(document, url)
        data["category"] = f"alquiler habitación idealista {data['category']}"
        return data


class FotocasaSource(ExternalListingSource):
    name = "Fotocasa"
    render_incomplete_detail = True
    domain = "fotocasa.es"
    url_tokens = ("/es/compartir/vivienda/",)
    listing_url_pattern = re.compile(r"/es/compartir/vivienda/.+/\d+/d/?$", re.IGNORECASE)
    discovery_selectors = ('a[href*="/es/compartir/vivienda/"][href$="/d"]', 'a[href*="/es/compartir/vivienda/"]')
    discovery_urls = (
        "https://www.fotocasa.es/es/compartir/viviendas/santa-cruz-de-tenerife-provincia/todas-las-zonas/1-habitacion/l",
    )
    removed_markers = ExternalListingSource.removed_markers + ("esta vivienda ya no esta disponible", "inmueble retirado")

    def is_pagination_url(self, url: str) -> bool:
        """Stay in the selected Spanish result set rather than crawling locale switcher links."""
        return urlparse(url).path.startswith("/es/compartir/viviendas/") and super().is_pagination_url(url)

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        """Extract Fotocasa's public shared-home fields before generic fallbacks."""
        data = super().parse_listing(document, url)
        state = embedded_json(document)
        candidates = [
            item
            for item in state
            if first_text(item, "title", "headline", "name")
            and (
                first_text(item, "description", "detail", "body")
                or first_text(item, "priceText", "price", "displayPrice")
            )
        ]
        candidate = max(
            candidates,
            key=lambda item: sum(
                bool(first_text(item, key))
                for key in (
                    "title",
                    "headline",
                    "description",
                    "detail",
                    "priceText",
                    "price",
                    "displayPrice",
                    "location",
                    "municipality",
                    "city",
                )
            ),
            default={},
        )
        heading = re.search(r'<h1[^>]*>(.*?)</h1>', document, re.IGNORECASE | re.DOTALL)
        description = re.search(r'<(?:div|section)[^>]*(?:description|property-description)[^>]*>(.*?)</(?:div|section)>', document, re.IGNORECASE | re.DOTALL)
        price = re.search(r'"(?:price|priceValue|amount)"\s*:\s*"?([\d.]+(?:,\d+)?)"?', document, re.IGNORECASE)
        image_urls = re.findall(r'"(?:image|imageUrl|url)"\s*:\s*"(https?[^"\\]+)"', document, re.IGNORECASE)
        data.update({
            "title": first_text(candidate, "title", "headline") or (clean(heading.group(1)) if heading else data["title"]),
            "description": first_text(candidate, "description", "detail", "body") or (clean(description.group(1)) if description else data["description"]),
            "price_text": first_text(candidate, "priceText", "price", "displayPrice") or (f"{price.group(1)} € /mes" if price else data["price_text"]),
            "images": list(dict.fromkeys([*data["images"], *[html.unescape(value) for value in image_urls]])),
            "city": first_text(candidate, "location", "municipality", "city", "address") or data["city"],
            "area": first_text(candidate, "neighborhood", "district", "zone", "area") or data.get("area"),
            "advertiser_name": first_text(candidate, "agencyName", "advertiserName", "contactName") or data.get("advertiser_name"),
            "advertiser_type": first_text(candidate, "advertiserType", "agencyType") or data.get("advertiser_type"),
            "available_from": candidate.get("availableFrom") or data.get("available_from"),
            "published_at": candidate.get("publishedAt") or data.get("published_at"),
        })
        data["category"] = f"compartir vivienda alquiler habitación {data['category']}"
        return data


class MilanunciosSource(ExternalListingSource):
    """Small rental inventory on the five Canary islands shown in the product map.

    Scope: Tenerife, La Palma, La Gomera, El Hierro and Gran Canaria.
    """

    name = "Milanuncios"
    domain = "milanuncios.com"
    url_tokens = (
        "/pisos-compartidos-",
        "/alquiler-de-estudios-",
        "/alquiler-de-pisos-",
        "/alquiler-de-apartamentos-",
    )
    listing_url_pattern = re.compile(
        r"^/(?:pisos-compartidos|alquiler-de-estudios|alquiler-de-pisos|alquiler-de-apartamentos)-"
        r"[^?#]+-\d+\.htm$",
        re.IGNORECASE,
    )
    discovery_selectors = (
        'a[href*="/pisos-compartidos-"][href*=".htm"]',
        'a[href*="/alquiler-de-estudios-"][href*=".htm"]',
        'a[href*="/alquiler-de-pisos-"][href*=".htm"]',
        'a[href*="/alquiler-de-apartamentos-"][href*=".htm"]',
    )
    discovery_urls = (
        "https://www.milanuncios.com/pisos-compartidos-en-canarias/",
        "https://www.milanuncios.com/alquiler-de-estudios-en-canarias/",
        "https://www.milanuncios.com/alquiler-de-pisos-en-canarias/",
        "https://www.milanuncios.com/alquiler-de-apartamentos-en-canarias/",
    )
    # Four Canarias-wide catalogues share the pagination budget. The detail
    # classifier below narrows the resulting inventory to the five target
    # islands, so small-island adverts are not lost merely because their
    # municipality has too few results for a dedicated discovery route.
    max_discovery_pages = 120
    removed_markers = ExternalListingSource.removed_markers + ("este anuncio ha caducado", "anuncio retirado")

    _target_places = (
        # Tenerife
        "tenerife",
        "adeje",
        "arafo",
        "arico",
        "arona",
        "buenavista del norte",
        "candelaria",
        "el rosario",
        "el sauzal",
        "el tanque",
        "fasnia",
        "garachico",
        "granadilla de abona",
        "guía de isora",
        "guia de isora",
        "güímar",
        "guimar",
        "icod de los vinos",
        "la guancha",
        "la matanza de acentejo",
        "la orotava",
        "la victoria de acentejo",
        "los realejos",
        "los silos",
        "puerto de la cruz",
        "san cristóbal de la laguna",
        "san cristobal de la laguna",
        "la laguna",
        "san juan de la rambla",
        "san miguel de abona",
        "santa cruz de tenerife",
        "santa úrsula",
        "santa ursula",
        "santiago del teide",
        "tacoronte",
        "tegueste",
        "vilaflor de chasna",
        # La Palma
        "la palma",
        "santa cruz de la palma",
        "los llanos de aridane",
        "barlovento",
        "breña alta",
        "brena alta",
        "breña baja",
        "brena baja",
        "el paso",
        "fuencaliente de la palma",
        "garafía",
        "garafia",
        "mazo",
        "puntagorda",
        "puntallana",
        "san andrés y sauces",
        "san andres y sauces",
        "tazacorte",
        "tijarafe",
        # La Gomera
        "la gomera",
        "san sebastián de la gomera",
        "san sebastian de la gomera",
        "agulo",
        "alajeró",
        "alajero",
        "hermigua",
        "valle gran rey",
        "vallehermoso",
        # El Hierro
        "el hierro",
        "valverde",
        "la frontera",
        "frontera",
        "el pinar de el hierro",
        # Gran Canaria
        "gran canaria",
        "las palmas de gran canaria",
        "agaete",
        "agüimes",
        "aguimes",
        "artenara",
        "arucas",
        "firgas",
        "gáldar",
        "galdar",
        "ingenio",
        "mogán",
        "mogan",
        "moya",
        "san bartolomé de tirajana",
        "san bartolome de tirajana",
        "san mateo",
        "santa brígida",
        "santa brigida",
        "santa lucía de tirajana",
        "santa lucia de tirajana",
        "santa maría de guía",
        "santa maria de guia",
        "tejeda",
        "telde",
        "teror",
        "valleseco",
        "valsequillo",
        "vega de san mateo",
    )
    _target_island_bounds = (
        # Tenerife
        (27.90, 28.62, -16.98, -16.02),
        # La Palma
        (28.38, 28.92, -18.12, -17.60),
        # La Gomera
        (27.94, 28.28, -17.42, -16.94),
        # El Hierro
        (27.58, 28.02, -18.22, -17.78),
        # Gran Canaria
        (27.70, 28.22, -15.85, -15.30),
    )

    _excluded_islands = (
        "lanzarote",
        "fuerteventura",
        "la graciosa",
    )

    @classmethod
    def _is_target_island_listing(cls, data: dict[str, Any]) -> bool:
        latitude, longitude = data.get("latitude"), data.get("longitude")
        lat: float | None
        lng: float | None
        try:
            lat, lng = float(str(latitude)), float(str(longitude))
        except (TypeError, ValueError):
            lat = lng = None
        if lat is not None and lng is not None:
            return any(
                min_lat <= lat <= max_lat and min_lng <= lng <= max_lng
                for min_lat, max_lat, min_lng, max_lng in cls._target_island_bounds
            )

        explicit = clean(
            " ".join(
                str(data.get(key, ""))
                for key in ("province", "city", "municipality", "address", "breadcrumbs", "postcode", "url")
            )
        ).casefold()
        if any(island in explicit for island in cls._excluded_islands):
            return False
        if any(place in explicit for place in cls._target_places):
            return True

        listing_copy = clean(f"{data.get('title', '')} {data.get('description', '')}").casefold()
        return (
            not any(island in listing_copy for island in cls._excluded_islands)
            and any(place in listing_copy for place in cls._target_places)
        )

    def is_pagination_url(self, url: str) -> bool:
        path = unquote(urlparse(url).path).casefold()
        if not any(
            path.startswith(prefix)
            for prefix in (
                "/pisos-compartidos-en-canarias",
                "/alquiler-de-estudios-en-canarias",
                "/alquiler-de-pisos-en-canarias",
                "/alquiler-de-apartamentos-en-canarias",
            )
        ):
            return False
        return super().is_pagination_url(url)

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        data = super().parse_listing(document, url)
        path = unquote(urlparse(url).path).casefold()
        if path.startswith("/pisos-compartidos-"):
            source_category = "pisos compartidos alquiler habitación"
        elif path.startswith("/alquiler-de-estudios-"):
            source_category = "alquiler estudio"
        elif path.startswith("/alquiler-de-apartamentos-"):
            source_category = "alquiler apartamento"
        else:
            source_category = "alquiler piso"
        data["category"] = f"{source_category} {data['category']}"
        return data

    def accepts_location(self, data: dict[str, Any]) -> bool:
        if self.scope_key != "santa_cruz":
            return super().accepts_location(data)
        return spain_country(data.get("country")) and self._is_target_island_listing(data)

    def accepts_coordinates(self, latitude: float, longitude: float) -> bool:
        if self.scope_key != "santa_cruz":
            return coordinates_in_spain(latitude, longitude)
        return any(min_lat <= latitude <= max_lat and min_lng <= longitude <= max_lng
                   for min_lat, max_lat, min_lng, max_lng in self._target_island_bounds)

    def normalize_listing(self, data: dict[str, Any], url: str) -> NormalizedListing | None:
        normalized = dict(data)
        if not normalized.get("city"):
            corpus = clean(f"{data.get('title', '')} {data.get('description', '')}").casefold()
            normalized["city"] = next((place.title() for place in sorted(self._target_places, key=len, reverse=True)
                                       if place in corpus and place not in {"tenerife", "la palma", "la gomera", "el hierro", "gran canaria"}), "")
        return super().normalize_listing(normalized, url)


class PisoCompartidoSource(ExternalListingSource):
    name = "PisoCompartido"
    domain = "pisocompartido.com"
    url_tokens = ("/habitacion/", "/alquiler-habitacion/")
    listing_url_pattern = re.compile(r"/habitacion/\d+/?$", re.IGNORECASE)
    discovery_selectors = ('a[href^="/habitacion/"]', 'a[href*="pisocompartido.com/habitacion/"]')
    discovery_urls = ("https://www.pisocompartido.com/habitaciones-santa_cruz_de_tenerife/",)
    removed_markers = ExternalListingSource.removed_markers + ("habitacion no disponible", "anuncio desactivado")

    def is_pagination_url(self, url: str) -> bool:
        """Do not treat locale-switcher detail links ending in an ID as pages."""
        path = urlparse(url).path
        return any(path.startswith(urlparse(root).path.rstrip('/') + '/') for root in self.discovery_urls) and super().is_pagination_url(url)

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        """Extract PisoCompartido's server-rendered detail fields independently."""
        data = super().parse_listing(document, url)
        heading = re.search(r'<h1[^>]*>(.*?)</h1>', document, re.IGNORECASE | re.DOTALL)
        description = re.search(r'<(?:div|section)[^>]*(?:descripcion|description)[^>]*>(.*?)</(?:div|section)>', document, re.IGNORECASE | re.DOTALL)
        price = re.search(r'(?:precio|alquiler)[^0-9€]{0,40}([\d.]+(?:,\d+)?\s*€(?:\s*(?:/|al|por)\s*\w+)?)', document, re.IGNORECASE)
        # The generic parser already reads the advert's structured gallery
        # (JSON-LD / embedded public state). Prefer it and never append page
        # chrome to a real advert gallery. Some legacy/public variants expose
        # no structured images at all, so only in that case keep the bounded
        # server-rendered <img> fallback for backwards compatibility.
        gallery_images = bounded_photo_urls(list(data["images"]))
        if not gallery_images:
            gallery_images = bounded_photo_urls(
                re.findall(
                    r'<img[^>]+(?:src|data-src)=["\\\'](https?[^"\\\']+)["\\\']',
                    document,
                    re.IGNORECASE,
                )
            )
        source_gallery_count = re.search(r"\bVer\s+(\d{1,2})\s+fotos?\b", clean(document), re.IGNORECASE)
        if source_gallery_count:
            gallery_images = gallery_images[: min(int(source_gallery_count.group(1)), MAX_LISTING_PHOTOS)]
        advertiser = re.search(r'(?:anunciante|propietario)[^<]{0,80}</[^>]+>\s*<[^>]+>([^<]+)', document, re.IGNORECASE)
        availability = re.search(r'(?:disponible(?:\s+desde)?|fecha disponible)\s*[:\-]?\s*([^<\n]{4,40})', clean(document), re.IGNORECASE)
        data.update({
            "title": clean(heading.group(1)) if heading else data["title"],
            "description": clean(description.group(1)) if description else data["description"],
            "price_text": clean(price.group(1)) if price else data["price_text"],
            "images": gallery_images,
            "advertiser_name": clean(advertiser.group(1)) if advertiser else data.get("advertiser_name"),
            "available_from": availability.group(1) if availability else data.get("available_from"),
        })
        data["category"] = f"pisocompartido alquiler habitación {data['category']}"
        return data


class _PisosGalleryParser(HTMLParser):
    """Read only the primary detail gallery, in its published order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.div_classes: list[set[str]] = []
        self.photos: dict[str, str] = {}
        self.published_entries = 0

    @staticmethod
    def image_identity(url: str) -> str | None:
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.hostname != "fotos.imghs.net"
                or parsed.username or parsed.password or parsed.port not in {None, 443}):
            return None
        match = re.fullmatch(
            r"/(?:xl|apps(?:wm)?|fchm?)-wp/(.+\.(?:jpg|jpeg|webp|png))", parsed.path, re.IGNORECASE
        )
        return match.group(1) if match else None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "div":
            self.div_classes.append(set((attributes.get("class") or "").split()))
        if tag != "img":
            return
        classes = set().union(*self.div_classes) if self.div_classes else set()
        if not {"details__col-left", "masonry__list", "media-thumbnail"} <= classes:
            return
        url = attributes.get("data-src") or attributes.get("src") or ""
        identity = self.image_identity(url)
        if identity is not None:
            self.published_entries += 1
            self.photos.setdefault(identity, url)

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self.div_classes:
            self.div_classes.pop()

    def published_photos(self, cover: str) -> list[str]:
        # Prefer the published high-resolution cover only when it is the same
        # image as a primary-gallery member. Never manufacture resized URLs.
        identity = self.image_identity(cover)
        if identity in self.photos and urlparse(cover).path.startswith("/xl-wp/"):
            self.photos[identity] = cover
        return bounded_photo_urls(list(self.photos.values()))


class PisosSource(ExternalListingSource):
    """Public Pisos room, studio and one-bedroom routes."""

    name = "Pisos"
    domain = "pisos.com"
    url_tokens = ("/alquilar/habitacion-", "/alquilar/piso-", "/alquilar/estudio-", "/alquilar/apartamento-")
    listing_url_pattern = re.compile(r"/alquilar/(?:habitacion|piso|estudio|apartamento)-[^/?#]+/?$", re.IGNORECASE)
    discovery_selectors = ('a[href*="/alquilar/"]',)
    discovery_urls = (
        "https://www.pisos.com/alquiler/habitaciones-tenerife/",
        "https://www.pisos.com/alquiler/habitaciones-santa_cruz_de_tenerife/",
    )

    def is_listing_url(self, url: str) -> bool:
        if super().is_listing_url(url):
            return True
        parsed = urlparse(url)
        return (
            self.scope_key.endswith(':holiday')
            and parsed.scheme == 'https'
            and hostname_matches_domain(url, self.domain)
            and bool(re.fullmatch(r'/alquilar/atico-[^/?#]+/?', parsed.path, re.IGNORECASE))
        )

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        data = super().parse_listing(document, url)
        gallery = _PisosGalleryParser()
        gallery.feed(document)
        gallery.close()
        if gallery.photos:
            data["images"] = gallery.published_photos(meta_content(document, "og:image"))
        counter = re.search(
            r'<span\b[^>]*class=["\'][^"\']*js-photosCounter[^"\']*["\'][^>]*>\s*\d+\s*</span>\s*/\s*(\d+)',
            document, re.IGNORECASE,
        )
        expected = int(counter.group(1)) if counter else None
        # An absent gallery or fewer photos than explicitly advertised is a
        # partial response, not evidence that existing photos were removed.
        data["photos_complete"] = bool(data["images"]) and (
            len(data["images"]) >= min(expected, MAX_LISTING_PHOTOS)
            or (
                gallery.published_entries >= expected
                and len(gallery.photos) >= max(1, expected - 1)
            )
            if expected is not None else bool(gallery.photos) or len(data["images"]) != 1
        )
        path = urlparse(url).path
        label = "habitacion" if path.startswith('/alquilar/habitacion-') else "vivienda"
        data["category"] = f"pisos.com alquiler {label} {data['category']}"
        # Public detail fields, not card summaries or global navigation.
        price = re.search(r'<div[^>]*class=["\'][^"\']*jsPriceValue[^"\']*["\'][^>]*>(.*?)</div>', document, re.IGNORECASE | re.DOTALL)
        if price:
            data['price_text'] = clean(price.group(1))
        selector = re.search(
            r'<select\b[^>]*class=["\'][^"\']*jsPriceSelector[^"\']*["\'][^>]*>(.*?)</select>',
            document, re.IGNORECASE | re.DOTALL,
        )
        if selector and parse_price(data['price_text'])[2] is None:
            for attributes, label in re.findall(r'<option\b([^>]*)>(.*?)</option>', selector.group(1), re.DOTALL | re.IGNORECASE):
                selected = re.search(r'(?:^|\s)selected(?:\s*=|\s|$)', attributes, re.IGNORECASE)
                value = re.search(r'''\bdata-value=["']([^"']+)["']''', attributes, re.IGNORECASE)
                if not selected or not value:
                    continue
                candidate = f"{clean(value.group(1))}/{clean(label)}"
                amount, currency, period, _ = parse_price(candidate)
                primary_amount, primary_currency, _, _ = parse_price(data['price_text'])
                if amount == primary_amount and currency == primary_currency == "EUR" and period is not None:
                    data['raw']['price_cadence_evidence'] = {
                        'primary_text': data['price_text'], 'selected_option': candidate,
                    }
                    data['price_text'] = candidate
                break
        facts = re.search(r'''<span\b[^>]*\bid=["']vtmExtraVars["'][^>]*\bdata-var=(?P<quote>["'])(?P<value>.*?)(?P=quote)''', document, re.IGNORECASE | re.DOTALL)
        if facts:
            try:
                metadata = json.loads(html.unescape(facts.group('value')))
                data['bedroom_count'] = metadata.get('nHabitaciones')
            except (json.JSONDecodeError, AttributeError):
                pass
        if path.startswith('/alquilar/estudio-'):
            data['property_type'] = 'studio'
        elif path.startswith('/alquilar/habitacion-'):
            data['property_type'] = 'room'
        elif path.startswith(('/alquilar/piso-', '/alquilar/apartamento-')):
            data['property_type'] = data.get('property_type') or 'apartment'
        elif self.scope_key.endswith(':holiday') and path.startswith('/alquilar/atico-') and not data.get('property_type'):
            # A published penthouse apartment is eligible only through the
            # existing apartment/bedroom admission rules. Do not infer its
            # type from the headline or overwrite a structured house/hotel.
            provider_type = re.search(
                r'''<span\b[^>]*\bid=["']gaCusVar["'][^>]*\bdata-var=(?P<quote>["'])(?P<value>.*?)(?P=quote)''',
                document, re.IGNORECASE | re.DOTALL,
            )
            declared_type = any(
                item.get('propertyType') or item.get('property_type')
                for item in data['raw']['jsonLd'] + data['raw']['embeddedJson'] if isinstance(item, dict)
            )
            if not declared_type and provider_type and re.search(
                r"\btipoInmueble\s*:\s*'aticos'", html.unescape(provider_type.group('value')),
            ):
                data['property_type'] = 'apartment'
                data['raw']['property_type_evidence'] = {'provider_field': 'gaCusVar.tipoInmueble', 'value': 'aticos'}
        crumbs = re.findall(r'''<div[^>]*class=["'][^"']*breadcrumb__item[^"']*["'][^>]*>(.*?)</div>''', document, re.IGNORECASE | re.DOTALL)
        locations = []
        for crumb in crumbs:
            anchor = re.search(r'''<a\b[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>''', crumb, re.IGNORECASE | re.DOTALL)
            if anchor and re.search(r'/alquiler(?:-vacacional|-temporada)?_viviendas/', anchor.group(1)):
                locations.append(clean(anchor.group(2)))
        if locations:
            data['province'] = data.get('province') or canonical_province(locations[0])
            capital = next((location.removesuffix(' Capital') for location in locations if location.endswith(' Capital')), '')
            data['city'] = data.get('city') or capital or locations[-1]
            data['country'] = data.get('country') or 'ES'
        if 'alquiler vacacional' in clean(' '.join(crumbs)).casefold():
            data['rental_category'] = 'holiday'
        elif any('/alquiler-temporada_viviendas/' in crumb for crumb in crumbs):
            data['rental_category'] = 'temporada'
        # Pisos detail URLs carry the public municipality slug even when the
        # structured address omits it.  Treat it as source metadata, not a
        # guessed geocode.
        route = unquote(urlparse(url).path).replace("_", " ").casefold()
        municipality = next(
            (name for name in sorted(SANTA_CRUZ, key=len, reverse=True) if name not in PROVINCE_ONLY and name in route),
            "",
        )
        if municipality and not data.get("city"):
            data["city"] = municipality.title()
            data["municipality"] = municipality.title()
            data["province"] = "Santa Cruz de Tenerife"
        if municipality and not data.get("area"):
            data["area"] = municipality.title()
        return data

    def is_pagination_url(self, url: str) -> bool:
        path = urlparse(url).path
        return any(path.startswith(urlparse(root).path.rstrip('/') + '/') for root in self.discovery_urls) and super().is_pagination_url(url)


class ThinkSpainSource(ExternalListingSource):
    """Opt-in ThinkSpain long/holiday routes; never enabled from audit evidence alone."""

    name = "ThinkSpain"
    domain = "thinkspain.com"
    url_tokens = ("/property-to-rent-long-term/", "/holiday-rentals/")
    listing_url_pattern = re.compile(r"/(?:property-to-rent-long-term|holiday-rentals)/\d+/?$", re.IGNORECASE)
    discovery_selectors = ('a[href*="/property-to-rent-long-term/"]',)
    discovery_urls = ("https://www.thinkspain.com/property-to-rent-long-term/tenerife",)

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        data = super().parse_listing(document, url)
        # Do not confer room status through a category: normalize_listing's
        # strict text classifier must find an explicit room phrase.
        data["rental_category"] = "holiday" if '/holiday-rentals/' in urlparse(url).path else "long"
        data["category"] = f"thinkspain rental {data['category']}"
        corpus = clean(f"{data.get('title', '')} {data.get('description', '')} {data.get('breadcrumbs', '')}").casefold()
        municipality = next(
            (name for name in sorted(SANTA_CRUZ, key=len, reverse=True) if name not in PROVINCE_ONLY and name in corpus),
            "",
        )
        if municipality and not data.get("city"):
            data["city"] = municipality.title()
            data["municipality"] = municipality.title()
            data["province"] = "Santa Cruz de Tenerife"
        return data



class AlquilerDocenteCanariasSource(ExternalListingSource):
    """Public, sitemap-backed room adverts published by Alquiler Docente Canarias.

    The provider's general catalogue includes whole homes for every Canary
    island.  Discovery intentionally consumes only public sitemap entries
    whose URL itself identifies a Tenerife room advert, so a change to a
    general-property route cannot turn sales or whole-home rentals into room
    imports.
    """

    name = "AlquilerDocenteCanarias"
    domain = "alquilerdocentecanarias.com"
    url_tokens = ("/estate_property/habitacion",)
    listing_url_pattern = re.compile(r"^/estate_property/habitacion[^/]+/?$", re.IGNORECASE)
    discovery_urls = ("https://alquilerdocentecanarias.com/estate_property-sitemap.xml",)
    max_discovery_pages = 1
    removed_markers = ExternalListingSource.removed_markers + ("propiedad eliminada", "inmueble eliminado")

    def _target_room_sitemap_url(self, url: str) -> bool:
        path = unquote(urlparse(url).path).replace("-", " ").casefold()
        if self.scope_key != "santa_cruz":
            return ("habitacion" in path or "habitación" in path) and self.scope_key.removeprefix("province:") in path
        return (
            "habitacion" in path or "habitación" in path
        ) and any(place in path for place in SANTA_CRUZ) and not any(place in path for place in LAS_PALMAS)

    async def discover_listing_urls(self) -> DiscoveryResult:
        sitemap_url = self.discovery_urls[0]
        document = await self.request(sitemap_url)
        if not document or "<urlset" not in document.casefold():
            return DiscoveryResult(
                complete=False,
                visited_pages=1,
                failed_pages=[sitemap_url],
                reached_last_page=True,
            )
        entries = re.findall(r"<loc>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</loc>", document, re.IGNORECASE | re.DOTALL)
        urls = {
            html.unescape(value).strip()
            for value in entries
            if self.is_listing_url(html.unescape(value).strip())
            and self._target_room_sitemap_url(html.unescape(value).strip())
        }
        return DiscoveryResult(
            urls=urls,
            complete=True,
            visited_pages=1,
            expected_total=len(urls),
            reached_last_page=True,
        )

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        data = super().parse_listing(document, url)
        body = clean(document)
        heading = re.search(r"<h1[^>]*>(.*?)</h1>", document, re.IGNORECASE | re.DOTALL)
        description = re.search(
            r'<(?:div|section)[^>]*(?:description|descripcion)[^>]*>(.*?)</(?:div|section)>',
            document,
            re.IGNORECASE | re.DOTALL,
        )
        price = re.search(
            r"(?<!\d)(\d{2,4}(?:[.,]\d{3})?\s*€(?:\s*/\s*mes(?:\s*\+\s*gastos)?|\s*/\s*todo incluido|\s+al\s+mes)?)",
            body,
            re.IGNORECASE,
        )
        city = re.search(r"Ciudad:\s*(.+?)(?:C[oó]digo postal:|Pa[ií]s:|Abrir en Google Maps|ID de Inmueble:)", body, re.IGNORECASE)
        address = re.search(r"Direcci[oó]n:\s*(.+?)(?:Ciudad:|C[oó]digo postal:|Pa[ií]s:)", body, re.IGNORECASE)
        external_id = re.search(r"ID de Inmueble:\s*(\d+)", body, re.IGNORECASE)
        updated = re.search(r"Actualizado en:\s*([^\n]{3,80}?)(?:\s+\d+\s+Dormitorios|\s+Descripci[oó]n)", body, re.IGNORECASE)
        image = meta_content(document, "og:image")
        map_markup = html.unescape(document).replace("\\/", "/")
        source_latitude = re.search(
            r"""(?<![A-Za-z0-9])(?:[A-Za-z0-9]+[_-])*(?:latitude|lat)
                \s*=\s*["']\s*(-?\d+(?:\.\d+)?)\s*["']""",
            map_markup,
            re.IGNORECASE | re.VERBOSE,
        )
        source_longitude = re.search(
            r"""(?<![A-Za-z0-9])(?:[A-Za-z0-9]+[_-])*(?:longitude|lng|lon|long)
                \s*=\s*["']\s*(-?\d+(?:\.\d+)?)\s*["']""",
            map_markup,
            re.IGNORECASE | re.VERBOSE,
        )
        data.update(
            {
                "title": clean(heading.group(1)) if heading else data["title"],
                "description": clean(description.group(1)) if description else data["description"],
                "price_text": clean(price.group(1)) if price else data["price_text"],
                "city": clean(city.group(1)) if city else data["city"],
                "municipality": clean(city.group(1)) if city else data.get("municipality"),
                "area": clean(city.group(1)) if city else data.get("area"),
                "address": clean(address.group(1)) if address else data.get("address"),
                "latitude": source_latitude.group(1) if source_latitude else data.get("latitude"),
                "longitude": source_longitude.group(1) if source_longitude else data.get("longitude"),
                "category": "alquiler habitación compartido alquiler docente canarias",
                "images": [image] if image else [],
                # Keep stable source identity but do not persist contact data
                # found in public page chrome or adverts.
                "external_id": external_id.group(1) if external_id else None,
                "phone": None,
                "whatsapp": None,
                "email": None,
                "raw": {
                    "source": self.name,
                    "external_id": external_id.group(1) if external_id else None,
                    "updated_text": clean(updated.group(1)) if updated else None,
                },
            }
        )
        return data

    def normalize_listing(self, data: dict[str, Any], url: str) -> NormalizedListing | None:
        item = super().normalize_listing(data, url)
        if item and data.get("external_id"):
            item.external_id = str(data["external_id"])
        return item


class FlatioSource(ExternalListingSource):
    """Public sitemap-backed monthly room offers from Flatio.

    The global offer sitemaps also contain apartments outside the target
    province.  Discovery therefore keeps only room routes whose public
    location slug identifies a Santa Cruz de Tenerife municipality.  Detail
    parsing additionally requires the provider's structured ``InStock``
    availability flag, rather than inferring availability from a booking UI.
    """

    name = "Flatio"
    domain = "flatio.com"
    url_tokens = ("/rent/room/", "/rent/apartment/")
    listing_url_pattern = re.compile(r"^/rent/(?:room|apartment)/\d+(?:-[^/?#]+)?/?$", re.IGNORECASE)
    discovery_urls = (
        "https://www.flatio.com/cdn/export/sitemap/en/offer-listings-sitemap-1.xml",
        "https://www.flatio.com/cdn/export/sitemap/en/offer-listings-sitemap-2.xml",
    )
    max_discovery_pages = 2
    removed_markers = ExternalListingSource.removed_markers + ("offer is no longer available",)

    def _target_room_sitemap_url(self, url: str) -> bool:
        path = unquote(urlparse(url).path).replace("_", " ").replace("-", " ").casefold()
        if self.scope_key != "santa_cruz":
            # Only province-name slugs are a bounded discovery prefilter, not
            # geographic proof. Detail admission still needs addressRegion.
            province = canonical_province(self.scope_key.removeprefix("province:"))
            return bool(province and province.casefold().replace(' ', '_') in url.casefold())
        return (
            any(token in urlparse(url).path.casefold() for token in self.url_tokens)
            and not any(place in path for place in LAS_PALMAS)
            and any(place in path for place in SANTA_CRUZ)
        )

    async def discover_listing_urls(self) -> DiscoveryResult:
        urls: set[str] = set()
        failed_pages: list[str] = []
        selected_urls = self.discovery_urls[:self.max_discovery_pages]
        for sitemap_url in selected_urls:
            document = await self.request(sitemap_url)
            if not document or "<urlset" not in document.casefold():
                failed_pages.append(sitemap_url)
                continue
            entries = re.findall(r"<loc>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</loc>", document, re.IGNORECASE | re.DOTALL)
            urls.update(
                candidate
                for value in entries
                if self.is_listing_url(candidate := html.unescape(value).strip())
                and self._target_room_sitemap_url(candidate)
            )
        return DiscoveryResult(
            urls=urls,
            complete=not failed_pages and len(selected_urls) == len(self.discovery_urls),
            visited_pages=len(selected_urls),
            expected_total=len(urls) if not failed_pages else None,
            failed_pages=failed_pages,
            reached_last_page=not failed_pages and len(selected_urls) == len(self.discovery_urls),
        )

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        room: dict[str, Any] = next(
            (item for item in json_ld(document) if any(kind in str(item.get("@type", "")).casefold()
                                                     for kind in ("room", "apartment"))),
            {},
        )
        offer = public_mapping(room.get("offers"))
        price_specification = public_mapping(offer.get("priceSpecification"))
        reference_quantity = public_mapping(price_specification.get("referenceQuantity"))
        address = public_mapping(room.get("address"))
        geo = public_mapping(room.get("geo"))
        image_values: list[Any] = room.get("image") or []
        if not isinstance(image_values, list):
            image_values = [image_values]
        external_id_match = re.search(r"/rent/(?:room|apartment)/(\d+)(?:-|/|$)", url, re.IGNORECASE)
        price = offer.get("price") or price_specification.get("price")
        currency = clean(offer.get("priceCurrency") or price_specification.get("priceCurrency")).upper()
        monthly_price = price is not None and currency == "EUR" and reference_quantity.get("unitCode") == "MON"
        title = clean(room.get("name"))
        data = super().parse_listing(document, url)
        data.update(
            {
                "title": title or data["title"],
                "description": clean(room.get("description")) or data["description"],
                # Flatio exposes a monthly reference quantity in its public
                # structured offer.  Keep a canonical text form for the
                # shared price parser instead of guessing from page chrome.
                "price_text": f"{price} €/mes" if monthly_price else "",
                "category": "flatio monthly residential rental",
                "property_type": "room" if '/rent/room/' in url else "studio" if clean(room.get('accommodationCategory')).casefold() == 'studio' else "apartment",
                # Flatio labels sleeping space as a bedroom even for public
                # accommodationCategory=Studio. The unit category is primary.
                "bedroom_count": 0 if clean(room.get('accommodationCategory')).casefold() == 'studio' else room.get('numberOfBedrooms'),
                "rental_category": "long",
                "city": clean(address.get("addressLocality")) or data["city"],
                "municipality": clean(address.get("addressLocality")) or data.get("municipality"),
                "province": clean(address.get("addressRegion")) or data.get("province"),
                "country": address.get("addressCountry"),
                "area": first_text(address, "addressSubLocality", "addressDistrict", "neighborhood", "district", "suburb", "area") or data.get("area"),
                "address": clean(address.get("streetAddress")) or data.get("address"),
                "latitude": geo.get("latitude") or data.get("latitude"),
                "longitude": geo.get("longitude") or data.get("longitude"),
                "images": [value for value in image_values if isinstance(value, str) and value.startswith("http")],
                "availability": clean(offer.get("availability")).casefold(),
                "monthly_price_confirmed": monthly_price,
                "external_id": external_id_match.group(1) if external_id_match else None,
                # Do not persist public contact data that may appear in the
                # seller object or in the document chrome.
                "phone": None,
                "whatsapp": None,
                "email": None,
                "raw": {
                    "source": self.name,
                    "external_id": external_id_match.group(1) if external_id_match else None,
                    "availability": clean(offer.get("availability")) or None,
                },
            }
        )
        return data

    def normalize_listing(self, data: dict[str, Any], url: str) -> NormalizedListing | None:
        # The sitemap is an index, not an availability guarantee.  Import
        # only the provider's explicit structured in-stock state.
        if not data.get("monthly_price_confirmed") or not str(data.get("availability", "")).endswith("instock"):
            return None
        item = super().normalize_listing(data, url)
        if item and data.get("external_id"):
            item.external_id = str(data["external_id"])
        return item


def configured_sources() -> list[ExternalListingSource]:
    enabled = {x.strip().casefold() for x in get_settings().external_import_sources.split(",")}
    source_types = (
        IdealistaSource,
        FotocasaSource,
        MilanunciosSource,
        PisoCompartidoSource,
        PisosSource,
        ThinkSpainSource,
        AlquilerDocenteCanariasSource,
        FlatioSource,
    )
    return [source_type() for source_type in source_types if source_type.name.casefold() in enabled]


def retired_source_names(enabled_names: set[str]) -> set[str]:
    """Return deliberately retired provider identities absent from this crawl."""
    retired = {"Idealista", "Milanuncios", "ThinkSpain"}
    return {name for name in retired if name.casefold() not in enabled_names}
