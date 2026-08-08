"""Anonymous, public-page adapters for room offers."""

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
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import httpx

from .core.browser_network import (
    configure_public_browser_context,
    hostname_matches_domain,
    validate_public_browser_url,
)
from .core.config import get_settings

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


def coordinates_in_target_province(latitude: float, longitude: float) -> bool:
    return any(
        min_lat <= latitude <= max_lat and min_lng <= longitude <= max_lng
        for min_lat, max_lat, min_lng, max_lng in TARGET_COORDINATE_BOUNDS
    )


def parse_price(value: str) -> tuple[int | None, str | None, str | None, bool]:
    value = clean(value)
    found = re.search(r"(?:desde\s*)?([\d.]+(?:,\d{1,2})?)\s*€", value, re.IGNORECASE)
    amount = int(float(found.group(1).replace(".", "").replace(",", "."))) if found else None
    lower = value.casefold()
    period = (
        "month"
        if any(x in lower for x in ("/mes", " al mes", "por mes", "mensual"))
        else "night"
        if any(x in lower for x in ("/noche", "por noche"))
        else "week"
        if any(x in lower for x in ("/semana", "por semana"))
        else None
    )
    return amount, "EUR" if "€" in value else None, period, lower.startswith("desde")


def json_ld(document: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', document, re.IGNORECASE | re.DOTALL
    ):
        try:
            loaded = json.loads(html.unescape(raw))
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
        for key in category_keys:
            add(categories, item.get(key))
        item_type = clean(item.get("@type")).casefold()
        if item_type == "breadcrumblist":
            for element in item.get("itemListElement", []):
                add(breadcrumbs, element)

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

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(
            "|".join(
                (
                    self.source_name,
                    self.external_id,
                    self.title,
                    self.description,
                    self.source_price_text,
                    self.room_type,
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
                )
            ).encode()
        ).hexdigest()


class ExternalListingSource(ABC):
    name: str
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
        )
        self.not_found_urls: set[str] = set()
        # A 410 or a detail URL redirected to a non-detail page is a
        # confirmed removal just like a 404, but keeping the reason lets the
        # lifecycle record a useful diagnostic.
        self.removed_urls: set[str] = set()
        self.discovery_diagnostics: dict[str, dict[str, Any]] = {}
        self.blocked_diagnostic: dict[str, Any] | None = None
        self._playwright: Any = None
        self._browser: Any = None
        self._browser_context: Any = None
        self._browser_lock = asyncio.Lock()

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

    def _raise_if_challenged(self, url: str, document: str) -> None:
        challenge = "geetest" in document.casefold() or "pardon our interruption" in document.casefold()
        if challenge:
            diagnostic = self.discovery_diagnostics.get(url, {})
            self.blocked_diagnostic = {"challenge_type": "geetest", **diagnostic, "paths": self._save_discovery_artifacts(url, document)}
            raise SourceBlocked("public source access challenge")

    async def request(self, url: str) -> str | None:
        for attempt in range(3):
            try:
                response = await self.client.get(url)
                self._record_page(url, response.text, status=response.status_code, final_url=str(response.url))
                if "geetest" in response.text.casefold() or "pardon our interruption" in response.text.casefold():
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
                if self.is_listing_url(url) and not self.is_listing_url(str(response.url)):
                    self.removed_urls.add(url)
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
        visited: set[str] = set()
        queue = list(self.discovery_urls)
        failed_pages: list[str] = []
        expected_total: int | None = None
        blocked = False
        while queue and len(visited) < self.max_discovery_pages:
            page = queue.pop(0)
            if page in visited:
                continue
            visited.add(page)
            try:
                document = await self.request(page)
            except SourceBlocked:
                blocked = True
                failed_pages.append(page)
                break
            except (httpx.HTTPError, RuntimeError):
                failed_pages.append(page)
                continue
            if not document:
                failed_pages.append(page)
                continue
            if expected_total is None:
                expected_total = self.visible_result_count(document)
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
            for href in [*static_links, *embedded_links]:
                url = urljoin(page, html.unescape(href).split("#", 1)[0])
                if self.is_listing_url(url):
                    # Gallery/map variants on a card are the same public listing.
                    seen.add(url.split("?", 1)[0])
            for href in static_links:
                url = urljoin(page, html.unescape(href).split("#", 1)[0])
                if self.is_pagination_url(url):
                    queue.append(url)
            if not seen and not has_listing_link and re.search(
                r"\b[1-9]\d*\s+(?:anuncios|resultados|viviendas|habitaciones)\b", document, re.IGNORECASE
            ):
                self._save_discovery_artifacts(page, document)
                failed_pages.append(page)
                self._save_discovery_artifacts(page, document)
        reached_last_page = not queue
        complete = not blocked and not failed_pages and reached_last_page
        if expected_total is not None and len(seen) < expected_total:
            complete = False
        return DiscoveryResult(seen, complete, len(visited), expected_total, failed_pages, reached_last_page, blocked)

    async def check_listing_state(self, source_url: str) -> str:
        """Check a missing detail URL without treating access errors as removal."""
        try:
            response = await self.client.get(source_url)
        except httpx.TimeoutException:
            return "temporary_error"
        except httpx.HTTPError:
            return "temporary_error"
        document = response.text
        self._record_page(source_url, document, status=response.status_code, final_url=str(response.url))
        if "geetest" in document.casefold() or "pardon our interruption" in document.casefold():
            return "blocked"
        if response.status_code == 404:
            return "not_found"
        if response.status_code == 410:
            return "removed"
        if response.status_code in {403, 429} or response.status_code >= 500:
            return "temporary_error"
        if response.status_code >= 400:
            return "unknown"
        final_url = str(response.url)
        if final_url.rstrip("/") != source_url.rstrip("/") and not self.is_listing_url(final_url):
            return "removed"
        corpus = clean(document).casefold()
        if any(marker in corpus for marker in self.removed_markers):
            return "removed"
        return "active" if self.is_listing_url(final_url) else "unknown"

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
        structured_items = [item for item in ld + state if isinstance(item, dict)]
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
        raw_geo = next(
            (
                structured.get("geo") or structured.get("coordinates")
                for structured in structured_items
                if isinstance(structured.get("geo") or structured.get("coordinates"), dict)
            ),
            item.get("geo") or item.get("coordinates"),
        )
        geo: dict[str, Any] = raw_geo if isinstance(raw_geo, dict) else {}
        raw_address = next(
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
        structured_category, structured_breadcrumbs = structured_classification(structured_items)
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
        if data.get("deleted") or clean(data.get("status")).casefold() in {"deleted", "removed", "not found"}:
            return None
        title = clean(data.get("title"))
        if not title or not (is_room_offer(data) and is_rental(data) and is_in_target_province(data)):
            return None
        amount, currency, period, price_is_from = parse_price(str(data.get("price_text", "")))
        corpus = clean(
            " ".join(str(data.get(x, "")) for x in ("title", "description", "category", "breadcrumbs", "url"))
        ).casefold()
        long_hint = any(value in corpus for value in ("alquiler", "se alquila", "mensual", "al mes", "/compartir/"))
        mode = "holiday" if period in {"night", "week"} else "long" if period == "month" or long_hint else None
        # A source category can prove a long-room offer when it omits `/mes`,
        # but it must not turn an obvious whole-property sale price into rent.
        if amount is None or amount <= 0 or mode is None or (period is None and amount > 5_000):
            return None
        room_type = (
            "Habitación compartida"
            if any(term in corpus for term in ("habitación compartida", "habitacion compartida", "shared room"))
            else "Habitación individual"
        )
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
        if latitude is not None and longitude is not None and not coordinates_in_target_province(latitude, longitude):
            return None
        details = public_detail_fields(data)
        return NormalizedListing(
            self.name,
            external_id,
            url,
            title[:240],
            clean(data.get("description")),
            city,
            city,
            mode,
            clean(data.get("price_text")),
            amount,
            currency,
            period,
            price_is_from,
            room_type,
            latitude,
            longitude,
            photos,
            data.get("phone"),
            data.get("whatsapp"),
            data.get("email"),
            data.get("raw", data),
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
            "advertiser_name": first_text(candidate, "agencyName", "advertiserName", "contactName") or data.get("advertiser_name"),
            "advertiser_type": first_text(candidate, "advertiserType", "agencyType") or data.get("advertiser_type"),
            "available_from": candidate.get("availableFrom") or data.get("available_from"),
            "published_at": candidate.get("publishedAt") or data.get("published_at"),
        })
        data["category"] = f"compartir vivienda alquiler habitación {data['category']}"
        return data


class MilanunciosSource(ExternalListingSource):
    name = "Milanuncios"
    domain = "milanuncios.com"
    url_tokens = ("/pisos-compartidos-",)
    listing_url_pattern = re.compile(r"/pisos-compartidos-[^?#]+\.htm$", re.IGNORECASE)
    discovery_selectors = ('a[href*="/pisos-compartidos-"][href$=".htm"]',)
    discovery_urls = ("https://www.milanuncios.com/pisos-compartidos-en-santa-cruz-de-tenerife-tenerife/habitacion.htm",)
    removed_markers = ExternalListingSource.removed_markers + ("este anuncio ha caducado", "anuncio retirado")

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        data = super().parse_listing(document, url)
        data["category"] = f"pisos compartidos alquiler habitación {data['category']}"
        return data


class PisoCompartidoSource(ExternalListingSource):
    name = "PisoCompartido"
    domain = "pisocompartido.com"
    url_tokens = ("/habitacion/", "/alquiler-habitacion/")
    listing_url_pattern = re.compile(r"/habitacion/\d+/?$", re.IGNORECASE)
    discovery_selectors = ('a[href^="/habitacion/"]', 'a[href*="pisocompartido.com/habitacion/"]')
    discovery_urls = ("https://www.pisocompartido.com/habitaciones-santa_cruz_de_tenerife/",)
    removed_markers = ExternalListingSource.removed_markers + ("habitacion no disponible", "anuncio desactivado")

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        """Extract PisoCompartido's server-rendered detail fields independently."""
        data = super().parse_listing(document, url)
        heading = re.search(r'<h1[^>]*>(.*?)</h1>', document, re.IGNORECASE | re.DOTALL)
        description = re.search(r'<(?:div|section)[^>]*(?:descripcion|description)[^>]*>(.*?)</(?:div|section)>', document, re.IGNORECASE | re.DOTALL)
        price = re.search(r'(?:precio|alquiler)[^0-9€]{0,40}([\d.]+(?:,\d+)?\s*€(?:\s*(?:/|al|por)\s*\w+)?)', document, re.IGNORECASE)
        images = re.findall(r'<img[^>]+(?:src|data-src)=["\'](https?[^"\']+)["\']', document, re.IGNORECASE)
        advertiser = re.search(r'(?:anunciante|propietario)[^<]{0,80}</[^>]+>\s*<[^>]+>([^<]+)', document, re.IGNORECASE)
        availability = re.search(r'(?:disponible(?:\s+desde)?|fecha disponible)\s*[:\-]?\s*([^<\n]{4,40})', clean(document), re.IGNORECASE)
        data.update({
            "title": clean(heading.group(1)) if heading else data["title"],
            "description": clean(description.group(1)) if description else data["description"],
            "price_text": clean(price.group(1)) if price else data["price_text"],
            "images": list(dict.fromkeys([*data["images"], *images])),
            "advertiser_name": clean(advertiser.group(1)) if advertiser else data.get("advertiser_name"),
            "available_from": availability.group(1) if availability else data.get("available_from"),
        })
        data["category"] = f"pisocompartido alquiler habitación {data['category']}"
        return data


class PisosSource(ExternalListingSource):
    """Public Pisos.com room routes, kept independent from the other adapters."""

    name = "Pisos"
    domain = "pisos.com"
    url_tokens = ("/alquilar/habitacion-",)
    listing_url_pattern = re.compile(r"/alquilar/habitacion-[^/?#]+/?$", re.IGNORECASE)
    discovery_selectors = ('a[href*="/alquilar/habitacion-"]',)
    discovery_urls = (
        "https://www.pisos.com/alquiler/habitaciones-tenerife/",
        "https://www.pisos.com/alquiler_habitaciones/santa_cruz_de_tenerife",
    )

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        data = super().parse_listing(document, url)
        data["category"] = f"pisos.com alquiler habitacion {data['category']}"
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
        return data


class ThinkSpainSource(ExternalListingSource):
    """ThinkSpain has no room search category: the detail classifier stays strict."""

    name = "ThinkSpain"
    domain = "thinkspain.com"
    url_tokens = ("/property-to-rent-long-term/",)
    listing_url_pattern = re.compile(r"/property-to-rent-long-term/\d+/?$", re.IGNORECASE)
    discovery_selectors = ('a[href*="/property-to-rent-long-term/"]',)
    discovery_urls = ("https://www.thinkspain.com/property-to-rent-long-term/tenerife",)

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        data = super().parse_listing(document, url)
        # Do not confer room status through a category: normalize_listing's
        # strict text classifier must find an explicit room phrase.
        data["category"] = f"thinkspain long term rental {data['category']}"
        corpus = clean(f"{data.get('title', '')} {data.get('description', '')} {document}").casefold()
        municipality = next(
            (name for name in sorted(SANTA_CRUZ, key=len, reverse=True) if name not in PROVINCE_ONLY and name in corpus),
            "",
        )
        if municipality and not data.get("city"):
            data["city"] = municipality.title()
            data["municipality"] = municipality.title()
            data["province"] = "Santa Cruz de Tenerife"
        return data

    def normalize_listing(self, data: dict[str, Any], url: str) -> NormalizedListing | None:
        corpus = clean(" ".join(str(data.get(key, "")) for key in ("title", "description", "category", "breadcrumbs"))).casefold()
        explicit_room = (
            "private room" in corpus
            or "rooms available for rent" in corpus
            or "room for rent" in corpus
            or "habitación privada" in corpus
            or "habitacion privada" in corpus
            or "alquiler de habitación" in corpus
            or "alquiler de habitacion" in corpus
        )
        return super().normalize_listing(data, url) if explicit_room else None


def configured_sources() -> list[ExternalListingSource]:
    enabled = {x.strip().casefold() for x in get_settings().external_import_sources.split(",")}
    source_types = (IdealistaSource, FotocasaSource, MilanunciosSource, PisoCompartidoSource, PisosSource, ThinkSpainSource)
    return [source_type() for source_type in source_types if source_type.name.casefold() in enabled]
