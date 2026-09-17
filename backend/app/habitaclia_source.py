"""Staged Habitaclia room-rental source.

Habitaclia mixes room adverts into its ordinary rental catalogue. This adapter
keeps discovery conservative: only detail URLs whose public slug itself looks
room-related are fetched, and normalization still requires explicit room-rental
wording in the listing copy.

The source is installed as a production-only supplemental adapter for its first
production observation period. A temporary layout change or zero-room cycle
therefore does not make the established configured-source requirement stricter.
"""

from __future__ import annotations

import os
import re
from urllib.parse import unquote, urlparse

from .external_sources import DiscoveryResult, ExternalListingSource, NormalizedListing, clean


class HabitacliaSource(ExternalListingSource):
    name = "Habitaclia"
    domain = "habitaclia.com"
    url_tokens = ("/alquiler-",)
    listing_url_pattern = re.compile(r"^/alquiler-[^/?#]+-i\d+\.htm$", re.IGNORECASE)
    discovery_selectors = ('a[href^="/alquiler-"][href*="-i"][href$=".htm"]',)
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
        path = unquote(urlparse(url).path).replace("_", "-").casefold()
        return any(marker in path for marker in cls._room_slug_markers)

    async def discover_listing_urls(self) -> DiscoveryResult:
        """Discover the catalogue, but fetch details only for room-like slugs."""
        discovery = await super().discover_listing_urls()
        urls = {url for url in discovery.urls if self.is_room_candidate_url(url)}
        return DiscoveryResult(
            urls=urls,
            complete=discovery.complete,
            visited_pages=discovery.visited_pages,
            expected_total=len(urls) if discovery.complete else None,
            failed_pages=list(discovery.failed_pages),
            reached_last_page=discovery.reached_last_page,
            blocked=discovery.blocked,
        )

    def parse_listing(self, document: str, url: str) -> dict[str, object]:
        data = super().parse_listing(document, url)
        heading = re.search(r"<h1[^>]*>(.*?)</h1>", document, re.IGNORECASE | re.DOTALL)
        description = re.search(
            r'<(?:div|section)[^>]*(?:description|descripcion|detail)[^>]*>(.*?)</(?:div|section)>',
            document,
            re.IGNORECASE | re.DOTALL,
        )
        external_id = re.search(r"-i(\d+)\.htm(?:$|[?#])", url, re.IGNORECASE)

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
