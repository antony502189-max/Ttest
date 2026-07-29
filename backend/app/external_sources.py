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
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from .core.config import get_settings

logger = logging.getLogger(__name__)

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
    corpus = clean(
        " ".join(str(data.get(key, "")) for key in ("title", "description", "category", "breadcrumbs", "url"))
    ).casefold()
    return any(term in corpus for term in POSITIVE) and not any(term in corpus for term in NEGATIVE)


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
    corpus = clean(
        " ".join(
            str(data.get(key, "")) for key in ("province", "city", "municipality", "address", "breadcrumbs", "postcode")
        )
    ).casefold()
    return not any(term in corpus for term in LAS_PALMAS) and any(term in corpus for term in SANTA_CRUZ)


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


def first_text(item: dict[str, Any], *keys: str) -> str:
    return next((clean(item.get(key)) for key in keys if clean(item.get(key))), "")


def meta_content(document: str, name: str) -> str:
    pattern = rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']'
    match = re.search(pattern, document, re.IGNORECASE)
    if not match:
        pattern = rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']'
        match = re.search(pattern, document, re.IGNORECASE)
    return clean(match.group(1)) if match else ""


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
                    self.phone or "",
                    self.email or "",
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

    def __init__(self) -> None:
        settings = get_settings()
        self.client = httpx.AsyncClient(
            timeout=settings.external_import_request_timeout_seconds,
            headers={"User-Agent": settings.external_import_user_agent, "Accept-Language": "es-ES,es;q=0.9"},
            follow_redirects=True,
        )
        self.not_found_urls: set[str] = set()
        self.discovery_diagnostics: dict[str, dict[str, Any]] = {}

    async def close(self) -> None:
        await self.client.aclose()

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

    def _save_discovery_artifacts(self, url: str, document: str | None, screenshot: bytes | None = None) -> None:
        """Persist anonymous error evidence outside the database for operator inspection."""
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        directory = get_settings().media_root / "external-import-errors" / self.name.casefold()
        directory.mkdir(parents=True, exist_ok=True)
        if document is not None:
            (directory / f"{digest}.html").write_text(document, encoding="utf-8")
        if screenshot is not None:
            (directory / f"{digest}.png").write_bytes(screenshot)

    async def request(self, url: str) -> str | None:
        for attempt in range(3):
            try:
                response = await self.client.get(url)
                self._record_page(url, response.text, status=response.status_code, final_url=str(response.url))
                logger.info(
                    "external_source_http", extra={"source": self.name, "method": "GET", "url": url,
                                                   "status": response.status_code, "final_url": str(response.url)}
                )
                if response.status_code == 404:
                    self.not_found_urls.add(url)
                    return None
                if response.status_code in {403, 405, 429} or response.status_code >= 500:
                    if response.status_code in {403, 405} and get_settings().external_import_playwright_enabled:
                        rendered = await self.render_public_page(url)
                        if rendered:
                            return rendered
                    if attempt == 2:
                        raise RuntimeError(f"HTTP {response.status_code}")
                    await asyncio.sleep(2**attempt)
                    continue
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
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=get_settings().external_import_user_agent)
                page = await context.new_page()
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
                self._record_page(url, document, status=status, final_url=final_url, method="BROWSER_GET")
                logger.info("external_source_browser", extra={"source": self.name, "method": "BROWSER_GET", "url": url,
                                                               "status": status, "final_url": final_url})
                if status is not None and status >= 400:
                    self._save_discovery_artifacts(url, document, await page.screenshot(full_page=True))
                    document = None
                await context.close()
                await browser.close()
                return document
        except (OSError, PlaywrightError, PlaywrightTimeoutError):
            diagnostic = self.discovery_diagnostics.get(url, {})
            self._save_discovery_artifacts(url, diagnostic.get("html"))
            return None

    def is_listing_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return (
            parsed.netloc.endswith(self.domain)
            and url.rstrip("/") not in {discovery.rstrip("/") for discovery in self.discovery_urls}
            and bool(self.listing_url_pattern.search(parsed.path))
        )

    def is_pagination_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc.endswith(self.domain) and bool(
            re.search(
                r"(?:[?&](?:pagina|page)=\d+|/pagina/\d+|/\d+/?$)",
                f"{parsed.path}?{parsed.query}",
                re.IGNORECASE,
            )
        )

    async def discover_listing_urls(self) -> list[str]:
        seen: set[str] = set()
        visited: set[str] = set()
        queue = list(self.discovery_urls)
        while queue and len(visited) < self.max_discovery_pages:
            page = queue.pop(0)
            if page in visited:
                continue
            visited.add(page)
            document = await self.request(page)
            if not document:
                continue
            static_links = LINK.findall(document)
            has_listing_link = any(self.is_listing_url(urljoin(page, html.unescape(href))) for href in static_links)
            if not has_listing_link and get_settings().external_import_playwright_enabled:
                rendered = await self.render_public_page(page)
                if rendered:
                    static_links = LINK.findall(rendered)
            for href in static_links:
                url = urljoin(page, html.unescape(href).split("#", 1)[0])
                if self.is_listing_url(url):
                    # Gallery/map variants on a card are the same public listing.
                    seen.add(url.split("?", 1)[0])
                elif self.is_pagination_url(url):
                    queue.append(url)
            diagnostics = self.discovery_diagnostics.get(page, {})
            if not has_listing_link and re.search(
                r"\b[1-9]\d*\s+(?:anuncios|resultados|viviendas|habitaciones)\b", document, re.IGNORECASE
            ):
                self._save_discovery_artifacts(page, document)
                raise RuntimeError(f"discovery returned zero URLs despite visible results: {json.dumps(diagnostics)}")
        return list(seen)

    async def fetch_listing(self, url: str) -> str | None:
        return await self.request(url)

    def parse_listing(self, document: str, url: str) -> dict[str, Any]:
        ld = json_ld(document)
        state = embedded_json(document)
        item = next(
            (
                x
                for x in ld + state
                if first_text(x, "name", "title", "headline") and first_text(x, "description", "body")
            ),
            {},
        )
        title_match = re.search(r"<title[^>]*>(.*?)</title>", document, re.IGNORECASE | re.DOTALL)
        body = clean(document)
        images = item.get("image") or item.get("images") or item.get("photos") or []
        images = [images] if isinstance(images, str) else images
        if not images and meta_content(document, "og:image"):
            images = [meta_content(document, "og:image")]
        price_match = re.search(
            r"(?:Desde\s*)?[\d.]+(?:,\d+)?\s*\u20ac(?:\s*(?:/\s*|al\s+|por\s+)(?:mes|noche|semana)|\s*mensual)?",
            body,
            re.IGNORECASE,
        )
        raw_geo = item.get("geo") or item.get("coordinates")
        geo: dict[str, Any] = raw_geo if isinstance(raw_geo, dict) else {}
        raw_address = item.get("address")
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
        return {
            "title": first_text(item, "name", "title", "headline")
            or meta_content(document, "og:title")
            or clean(title_match.group(1) if title_match else ""),
            "description": first_text(item, "description", "body", "text")
            or meta_content(document, "og:description")
            or meta_content(document, "description"),
            "category": body[:1200],
            "breadcrumbs": body[:1800],
            "url": url,
            "price_text": price_match.group(0) if price_match else "",
            "images": images,
            "city": clean(address.get("addressLocality")),
            "municipality": clean(address.get("addressLocality")),
            "province": clean(address.get("addressRegion")),
            "address": clean(address.get("streetAddress")),
            "postcode": clean(address.get("postalCode")),
            "phone": first_text(item, "telephone", "phone", "contactPhone") or (PHONE.findall(body) or [None])[0],
            "whatsapp": first_text(item, "whatsapp", "contactWhatsapp", "whatsApp") or None,
            "email": first_text(item, "email", "contactEmail") or (EMAIL.findall(body) or [None])[0],
            "latitude": latitude,
            "longitude": longitude,
            "raw": {"jsonLd": ld, "embeddedJson": state, "html": document[:200000]},
        }

    def normalize_listing(self, data: dict[str, Any], url: str) -> NormalizedListing | None:
        if data.get("deleted") or clean(data.get("status")).casefold() in {"deleted", "removed", "not found"}:
            return None
        if not (is_room_offer(data) and is_rental(data) and is_in_target_province(data)):
            return None
        amount, currency, period, price_is_from = parse_price(str(data.get("price_text", "")))
        mode = "holiday" if period in {"night", "week"} else "long" if period == "month" else None
        if amount is None or mode is None:
            return None
        corpus = clean(
            " ".join(str(data.get(x, "")) for x in ("title", "description", "category", "breadcrumbs"))
        ).casefold()
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
        return NormalizedListing(
            self.name,
            external_id,
            url,
            clean(data.get("title"))[:240],
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
        )


class IdealistaSource(ExternalListingSource):
    name = "Idealista"
    domain = "idealista.com"
    url_tokens = ("/inmueble/",)
    listing_url_pattern = re.compile(r"/inmueble/\d+/?$", re.IGNORECASE)
    discovery_selectors = ('a[href*="/inmueble/"]',)
    discovery_urls = ("https://www.idealista.com/alquiler-habitacion/santa-cruz-de-tenerife-provincia/",)


class FotocasaSource(ExternalListingSource):
    name = "Fotocasa"
    domain = "fotocasa.es"
    url_tokens = ("/es/compartir/vivienda/",)
    listing_url_pattern = re.compile(r"/es/compartir/vivienda/.+/\d+/d/?$", re.IGNORECASE)
    discovery_selectors = ('a[href*="/es/compartir/vivienda/"][href$="/d"]', 'a[href*="/es/compartir/vivienda/"]')
    discovery_urls = (
        "https://www.fotocasa.es/es/compartir/viviendas/santa-cruz-de-tenerife-provincia/todas-las-zonas/1-habitacion/l",
    )


class MilanunciosSource(ExternalListingSource):
    name = "Milanuncios"
    domain = "milanuncios.com"
    url_tokens = ("/pisos-compartidos-",)
    listing_url_pattern = re.compile(r"/pisos-compartidos-[^?#]+\.htm$", re.IGNORECASE)
    discovery_selectors = ('a[href*="/pisos-compartidos-"][href$=".htm"]',)
    discovery_urls = ("https://www.milanuncios.com/pisos-compartidos-en-santa-cruz-de-tenerife-tenerife/habitacion.htm",)


class PisoCompartidoSource(ExternalListingSource):
    name = "PisoCompartido"
    domain = "pisocompartido.com"
    url_tokens = ("/habitacion/", "/alquiler-habitacion/")
    listing_url_pattern = re.compile(r"/habitacion/\d+/?$", re.IGNORECASE)
    discovery_selectors = ('a[href^="/habitacion/"]', 'a[href*="pisocompartido.com/habitacion/"]')
    discovery_urls = ("https://www.pisocompartido.com/habitaciones-santa_cruz_de_tenerife/",)


def configured_sources() -> list[ExternalListingSource]:
    enabled = {x.strip().casefold() for x in get_settings().external_import_sources.split(",")}
    source_types = (IdealistaSource, FotocasaSource, MilanunciosSource, PisoCompartidoSource)
    return [source_type() for source_type in source_types if source_type.name.casefold() in enabled]
