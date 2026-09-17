"""Staged Habitaclia room-rental source.

Habitaclia mixes room adverts into its ordinary rental catalogue. Current result
pages expose card destinations and summaries in hydrated application data using
``navigationUrl`` values such as ``/i123456789.htm?from=list``. This adapter
shortlists only cards whose own public summary explicitly describes a room
rental, then performs the stricter detail normalization before import.

The source is installed as a production-only supplemental adapter for its first
production observation period. A temporary layout change or zero-room cycle
therefore does not make the established configured-source requirement stricter.
"""

from __future__ import annotations

import html
import os
import re
from urllib.parse import unquote, urljoin, urlparse

import httpx

from .external_sources import (
    DiscoveryResult,
    ExternalListingSource,
    NormalizedListing,
    SourceBlocked,
    clean,
)

_HREF = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)
_LEGACY_LISTING_VALUE = re.compile(
    r"(?P<url>(?:https?://(?:www\.)?habitaclia\.com)?/alquiler-[^\"'< >\\]+-i\d+\.htm(?:\?[^\"'< >\\]*)?)",
    re.IGNORECASE,
)
_NAVIGATION_VALUE = re.compile(
    r'"navigationUrl"\s*:\s*"(?P<url>/i\d+(?:\.htm)?(?:\?[^"< >]*)?)"',
    re.IGNORECASE,
)
_UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


class HabitacliaSource(ExternalListingSource):
    name = "Habitaclia"
    domain = "habitaclia.com"
    url_tokens = ("/i", "/alquiler-")
    listing_url_pattern = re.compile(
        r"^/(?:i\d+(?:\.htm)?|alquiler-[^/?#]+-i\d+\.htm)$",
        re.IGNORECASE,
    )
    discovery_selectors = (
        'a[href^="/i"]',
        '[data-href^="/i"]',
        '[data-url^="/i"]',
        'a[href*="-i"][href$=".htm"]',
    )
    discovery_urls = (
        "https://www.habitaclia.com/alquiler/viviendas/santa-cruz-de-tenerife-provincia/tenerife/s",
    )
    removed_markers = ExternalListingSource.removed_markers + (
        "anuncio no disponible",
        "inmueble no disponible",
        "este anuncio ya no está disponible",
        "este anuncio ya no esta disponible",
    )

    # These phrases describe the advertised unit as a room. Generic phrases
    # such as "3 habitaciones" or "habitaciones en alquiler" are deliberately
    # excluded because they also occur on whole-home adverts.
    _explicit_room_markers = (
        "se alquila habitación",
        "se alquila habitacion",
        "se alquilan habitaciones",
        "alquilo habitación",
        "alquilo habitacion",
        "alquiler de habitación",
        "alquiler de habitacion",
        "alquiler habitación",
        "alquiler habitacion",
        "habitación para alquilar",
        "habitacion para alquilar",
        "habitación en alquiler",
        "habitacion en alquiler",
        "habitación en piso compartido",
        "habitacion en piso compartido",
        "habitación para estudiante",
        "habitacion para estudiante",
        "habitación solo chica",
        "habitacion solo chica",
        "habitación solo chico",
        "habitacion solo chico",
        "rooms for rent",
        "room for rent",
        "private room for rent",
    )
    _room_slug_markers = (
        "habitacion",
        "habitaciones",
        "room",
        "compartir",
        "compartido",
    )

    def is_pagination_url(self, url: str) -> bool:
        path = unquote(urlparse(url).path).rstrip("/").casefold()
        base = "/alquiler/viviendas/santa-cruz-de-tenerife-provincia/tenerife/s"
        return bool(re.fullmatch(rf"{re.escape(base)}/\d+", path)) and super().is_pagination_url(url)

    @classmethod
    def is_room_candidate_url(cls, url: str) -> bool:
        """Legacy slug hint; modern ``/i<ID>`` routes have no semantic slug."""
        path = unquote(urlparse(url).path).replace("_", "-").casefold()
        return any(marker in path for marker in cls._room_slug_markers)

    @staticmethod
    def _decode_hydration(document: str) -> str:
        """Make public escaped application-state strings regex-readable.

        Habitaclia serializes result cards inside framework hydration strings.
        Decode only the escaping needed for route/text classification rather
        than executing or interpreting the embedded JavaScript.
        """
        normalized = html.unescape(document.replace("\\/", "/"))
        for _ in range(3):
            updated = normalized.replace('\\"', '"')
            if updated == normalized:
                break
            normalized = updated
        normalized = _UNICODE_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), normalized)
        return normalized.replace("\\n", " ").replace("\\r", " ")

    @classmethod
    def _is_room_card(cls, value: str) -> bool:
        corpus = re.sub(r"\s+", " ", value).casefold()
        return any(marker in corpus for marker in cls._explicit_room_markers)

    @staticmethod
    def _canonical_detail_url(page: str, value: str) -> str:
        absolute = urljoin(page, value)
        parsed = urlparse(absolute)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _extract_page_listings(self, document: str, page: str) -> tuple[set[str], set[str]]:
        """Return all card detail URLs and the explicit-room subset.

        Modern cards are paired by ``navigationUrl`` boundaries, so the room
        decision is based on that card's own serialized summary instead of
        nearby text from an adjacent result. Legacy semantic slugs remain a
        fallback for older server-rendered pages.
        """
        normalized = self._decode_hydration(document)
        all_urls: set[str] = set()
        room_urls: set[str] = set()

        navigation_matches = list(_NAVIGATION_VALUE.finditer(normalized))
        for index, match in enumerate(navigation_matches):
            canonical = self._canonical_detail_url(page, match.group("url"))
            if not self.is_listing_url(canonical):
                continue
            all_urls.add(canonical)
            next_start = (
                navigation_matches[index + 1].start()
                if index + 1 < len(navigation_matches)
                else len(normalized)
            )
            card_state = normalized[match.end() : min(next_start, match.end() + 20000)]
            if self._is_room_card(card_state):
                room_urls.add(canonical)

        for match in _LEGACY_LISTING_VALUE.finditer(normalized):
            canonical = self._canonical_detail_url(page, match.group("url"))
            if not self.is_listing_url(canonical):
                continue
            all_urls.add(canonical)
            if self.is_room_candidate_url(canonical):
                room_urls.add(canonical)

        return all_urls, room_urls

    def _page_links(self, document: str, page: str) -> set[str]:
        return {
            absolute
            for href in _HREF.findall(document)
            if self.is_pagination_url(absolute := urljoin(page, html.unescape(href)))
        }

    async def discover_listing_urls(self) -> DiscoveryResult:
        """Walk the Tenerife catalogue and retain only explicit room cards."""
        queue = list(self.discovery_urls)
        visited: set[str] = set()
        room_urls: set[str] = set()
        failed_pages: list[str] = []
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

            page_urls, page_rooms = self._extract_page_listings(document, page)
            if not page_urls:
                rendered = await self.render_public_page(page)
                if rendered:
                    document = rendered
                    page_urls, page_rooms = self._extract_page_listings(document, page)

            pagination = self._page_links(document, page)
            for next_page in sorted(pagination):
                if next_page not in visited and next_page not in queue:
                    queue.append(next_page)

            if not page_urls:
                failed_pages.append(page)
                continue
            room_urls.update(page_rooms)

        complete = not blocked and not failed_pages and not queue
        return DiscoveryResult(
            urls=room_urls,
            complete=complete,
            visited_pages=len(visited),
            expected_total=len(room_urls) if complete else None,
            failed_pages=failed_pages,
            reached_last_page=complete,
            blocked=blocked,
        )

    def parse_listing(self, document: str, url: str) -> dict[str, object]:
        data = super().parse_listing(document, url)
        heading = re.search(r"<h1[^>]*>(.*?)</h1>", document, re.IGNORECASE | re.DOTALL)
        description = re.search(
            r'<(?:div|section)[^>]*(?:description|descripcion|detail)[^>]*>(.*?)</(?:div|section)>',
            document,
            re.IGNORECASE | re.DOTALL,
        )
        external_id = re.search(r"(?:-i|/i)(\d+)(?:\.htm)?(?:$|[?#])", url, re.IGNORECASE)

        if heading:
            data["title"] = clean(heading.group(1)) or data["title"]
        if description:
            data["description"] = clean(description.group(1)) or data["description"]

        # Do not inject the word "habitación" here. Habitaclia's catalogue
        # contains whole homes with a bedroom count; only the listing copy may
        # prove that the advertised object is actually a room.
        data["category"] = f"habitaclia alquiler {data['category']}"
        data["external_id"] = external_id.group(1) if external_id else None

        # Contact details can appear in page chrome. They are not needed for
        # source identity or matching, so keep them out of the imported payload.
        data["phone"] = None
        data["whatsapp"] = None
        data["email"] = None
        data["raw"] = {
            "source": self.name,
            "external_id": data["external_id"],
        }
        return data

    def normalize_listing(self, data: dict[str, object], url: str) -> NormalizedListing | None:
        corpus = clean(
            " ".join(
                str(data.get(key, ""))
                for key in ("title", "description", "category", "breadcrumbs")
            )
        ).casefold()
        if not any(marker in corpus for marker in self._explicit_room_markers):
            return None

        item = super().normalize_listing(data, url)
        if item and data.get("external_id"):
            item.external_id = str(data["external_id"])
        return item


_installed = False


def install_habitaclia_source() -> None:
    """Append Habitaclia to production crawls without raising the configured threshold.

    This is deliberately production-only. Tests and development continue to
    see the versioned configured source set exactly as before, while the
    production worker gets one supplemental source. Once production evidence
    shows stable positive room imports, the adapter can move into the normal
    configured source registry and monitoring contract.
    """

    global _installed
    if _installed or os.getenv("APP_ENV", "development").casefold() != "production":
        return

    from . import external_sources

    configured = external_sources.configured_sources

    def configured_with_habitaclia() -> list[ExternalListingSource]:
        sources = configured()
        if not any(source.name.casefold() == "habitaclia" for source in sources):
            sources.append(HabitacliaSource())
        return sources

    external_sources.configured_sources = configured_with_habitaclia
    _installed = True
