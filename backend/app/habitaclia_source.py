"""Staged Habitaclia source for small Tenerife rental units.

Habitaclia mixes room adverts, studios and ordinary homes into the same rental
catalogue. Current result pages expose card destinations and summaries in
hydrated application data using ``navigationUrl`` values such as
``/i123456789.htm?from=list``. This adapter keeps only the target inventory for
this product: individual rooms, studios/lofts and whole homes with exactly one
bedroom. Multi-bedroom whole homes remain excluded.
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
_SINGLE_BEDROOM = re.compile(
    r"\b(?:1|un|una)\s+(?:habitaci[oó]n|hab|dormitorio)\b",
    re.IGNORECASE,
)
_MULTI_BEDROOM = re.compile(
    r"\b(?:[2-9]|1\d|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+"
    r"(?:habitaciones?|hab|dormitorios?)\b",
    re.IGNORECASE,
)
_STUDIO_HOME = re.compile(r"\b(?:estudio|tipo\s+estudio|studio|loft)\b", re.IGNORECASE)


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

    # Strong room wording proves that the advertised object itself is a room.
    # Keep the weak "habitación en alquiler" wording separate: it also occurs
    # naturally in a whole "piso de una habitación en alquiler" advert.
    _strong_room_markers = (
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
    _weak_room_markers = (
        "habitación en alquiler",
        "habitacion en alquiler",
    )
    _target_slug_markers = (
        "habitacion",
        "habitaciones",
        "room",
        "compartir",
        "compartido",
        "estudio",
        "studio",
        "loft",
        "1-habitacion",
        "una-habitacion",
        "1-dormitorio",
        "un-dormitorio",
    )

    def is_pagination_url(self, url: str) -> bool:
        path = unquote(urlparse(url).path).rstrip("/").casefold()
        base = "/alquiler/viviendas/santa-cruz-de-tenerife-provincia/tenerife/s"
        return bool(re.fullmatch(rf"{re.escape(base)}/\d+", path)) and super().is_pagination_url(url)

    @classmethod
    def is_room_candidate_url(cls, url: str) -> bool:
        """Legacy semantic-slug hint for any supported target unit."""
        path = unquote(urlparse(url).path).replace("_", "-").casefold()
        return any(marker in path for marker in cls._target_slug_markers)

    @staticmethod
    def _decode_hydration(document: str) -> str:
        normalized = html.unescape(document.replace("\\/", "/"))
        for _ in range(3):
            updated = normalized.replace('\\"', '"')
            if updated == normalized:
                break
            normalized = updated
        normalized = _UNICODE_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), normalized)
        return normalized.replace("\\n", " ").replace("\\r", " ")

    @classmethod
    def _target_unit_type(cls, value: str) -> str | None:
        """Classify rooms, studios and exactly-one-bedroom whole homes."""
        corpus = re.sub(r"\s+", " ", value).casefold()

        # A strong room phrase may describe one available room inside a larger
        # shared apartment, so it intentionally wins over the home's bedroom
        # count (for example: "4 habitaciones; se alquila habitación").
        if any(marker in corpus for marker in cls._strong_room_markers):
            return (
                "Habitación compartida"
                if any(marker in corpus for marker in ("habitación compartida", "habitacion compartida", "shared room"))
                else "Habitación individual"
            )

        # Without a strong room offer, 2+ bedrooms means the advertised object
        # is outside this marketplace's target whole-unit scope.
        if _MULTI_BEDROOM.search(corpus):
            return None
        if _STUDIO_HOME.search(corpus):
            return "Estudio"
        if _SINGLE_BEDROOM.search(corpus):
            return "Apartamento de 1 dormitorio"

        # Weak room wording is safe only after whole-home bedroom counts have
        # been classified above.
        if any(marker in corpus for marker in cls._weak_room_markers):
            return "Habitación individual"
        return None

    @classmethod
    def _room_text_is_explicit(cls, value: str) -> bool:
        # Historical name retained because the live audit and regression suite
        # already call this method. It now means "supported target unit".
        return cls._target_unit_type(value) is not None

    @classmethod
    def _is_room_card(cls, value: str) -> bool:
        return cls._target_unit_type(value) is not None

    @staticmethod
    def _canonical_detail_url(page: str, value: str) -> str:
        absolute = urljoin(page, value)
        parsed = urlparse(absolute)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _extract_page_listings(self, document: str, page: str) -> tuple[set[str], set[str]]:
        normalized = self._decode_hydration(document)
        all_urls: set[str] = set()
        target_urls: set[str] = set()

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
                target_urls.add(canonical)

        for match in _LEGACY_LISTING_VALUE.finditer(normalized):
            canonical = self._canonical_detail_url(page, match.group("url"))
            if not self.is_listing_url(canonical):
                continue
            all_urls.add(canonical)
            if self.is_room_candidate_url(canonical):
                target_urls.add(canonical)

        return all_urls, target_urls

    def _page_links(self, document: str, page: str) -> set[str]:
        return {
            absolute
            for href in _HREF.findall(document)
            if self.is_pagination_url(absolute := urljoin(page, html.unescape(href)))
        }

    async def discover_listing_urls(self) -> DiscoveryResult:
        queue = list(self.discovery_urls)
        visited: set[str] = set()
        target_urls: set[str] = set()
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

            page_urls, page_targets = self._extract_page_listings(document, page)
            if not page_urls:
                rendered = await self.render_public_page(page)
                if rendered:
                    document = rendered
                    page_urls, page_targets = self._extract_page_listings(document, page)

            for next_page in sorted(self._page_links(document, page)):
                if next_page not in visited and next_page not in queue:
                    queue.append(next_page)

            if not page_urls:
                failed_pages.append(page)
                continue
            target_urls.update(page_targets)

        complete = not blocked and not failed_pages and not queue
        return DiscoveryResult(
            urls=target_urls,
            complete=complete,
            visited_pages=len(visited),
            expected_total=len(target_urls) if complete else None,
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

        data["category"] = f"habitaclia alquiler {data['category']}"
        data["external_id"] = external_id.group(1) if external_id else None
        data["phone"] = None
        data["whatsapp"] = None
        data["email"] = None
        data["raw"] = {"source": self.name, "external_id": data["external_id"]}
        return data

    def normalize_listing(self, data: dict[str, object], url: str) -> NormalizedListing | None:
        corpus = clean(
            " ".join(
                str(data.get(key, ""))
                for key in ("title", "description", "category", "breadcrumbs")
            )
        ).casefold()
        target_type = self._target_unit_type(corpus)
        if target_type is None:
            return None

        # The shared external-source normalizer predates whole-unit support and
        # intentionally rejects ``estudio`` plus non-room homes. Feed it a
        # classification-only proxy identity so its existing rental, price,
        # province, city and coordinate checks can still be reused. Restore the
        # real public identity immediately afterwards.
        normalized_data = dict(data)
        if target_type in {"Estudio", "Apartamento de 1 dormitorio"}:
            normalized_data["title"] = "Habitación en alquiler"
            normalized_data["category"] = "alquiler habitación"
            normalized_data["breadcrumbs"] = ""

        item = super().normalize_listing(normalized_data, url)
        if item is None:
            return None

        item.title = clean(data.get("title"))
        item.description = clean(data.get("description"))
        item.room_type = target_type
        if data.get("external_id"):
            item.external_id = str(data["external_id"])
        return item


_installed = False


def install_habitaclia_source() -> None:
    """Append Habitaclia to production crawls without raising the health gate."""
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
