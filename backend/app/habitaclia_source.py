"""Staged Habitaclia room-rental source.

Habitaclia mixes room adverts into its ordinary rental catalogue.  This adapter
therefore keeps discovery broad enough to see those adverts, but normalization
requires an explicit room-rental phrase before the shared conservative filters
are allowed to accept a listing.

The source is installed as a production-only supplemental adapter for its first
production observation period.  It intentionally does not participate in the
configured-source health gate yet, so a temporary layout change or a zero-room
cycle cannot make the five established providers unhealthy.
"""

from __future__ import annotations

import html
import os
import re
from urllib.parse import unquote, urlparse

from .external_sources import ExternalListingSource, NormalizedListing, clean


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

    _explicit_room_markers = (
        "se alquila habitación",
        "se alquila habitacion",
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
        "habitaciones en alquiler",
        "rooms for rent",
        "room for rent",
        "private room for rent",
    )

    def is_pagination_url(self, url: str) -> bool:
        path = unquote(urlparse(url).path).casefold()
        return path.startswith(
            "/alquiler/viviendas/santa-cruz-de-tenerife-provincia/tenerife/s"
        ) and super().is_pagination_url(url)

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

        # Do not inject the word "habitación" here.  Habitaclia's catalogue
        # contains whole homes with a bedroom count; only the listing copy may
        # prove that the advertised object is actually a room.
        data["category"] = f"habitaclia alquiler {data['category']}"
        data["external_id"] = external_id.group(1) if external_id else None

        # Contact details can appear in page chrome.  They are not needed for
        # the source identity or matching contract, so keep them out of the
        # imported payload just like the newer production adapters do.
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
    """Append Habitaclia to production crawls without changing the health gate.

    This is deliberately production-only.  Tests and development continue to
    see the versioned configured source set exactly as before, while the
    production worker gets one supplemental source.  Once production evidence
    shows stable positive room imports, the adapter can move into the normal
    configured source registry and monitoring threshold.
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
