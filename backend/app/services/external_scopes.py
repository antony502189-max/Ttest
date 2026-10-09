"""Published provider routes and disabled-by-default province provisioning."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..external_sources import (
    AlquilerDocenteCanariasSource,
    ExternalListingSource,
    FlatioSource,
    FotocasaSource,
    IdealistaSource,
    MilanunciosSource,
    PisoCompartidoSource,
    PisosSource,
    ThinkSpainSource,
)
from ..habitaclia_source import HabitacliaSource
from ..models import ExternalImportScope
from ..spain_provinces import canonical_province, scope_province

SOURCE_TYPES: dict[str, type[ExternalListingSource]] = {
    source.name: source
    for source in (
        PisosSource,
        PisoCompartidoSource,
        FlatioSource,
        AlquilerDocenteCanariasSource,
        FotocasaSource,
        MilanunciosSource,
        IdealistaSource,
        ThinkSpainSource,
        HabitacliaSource,
    )
}
PUBLISHED_GEOGRAPHY = {
    "PisoCompartido": "https://www.pisocompartido.com/zonas/",
    "Pisos": "https://www.pisos.com/alquiler_viviendas/",
}
# Published province catalogue audited with two pages and three real details
# on 2026-10-07. Provisioning revalidates it live; no slug-based expansion.
AUDITED_HOLIDAY_ROUTES = {
    ("Pisos", "province:Málaga"): ("https://www.pisos.com/alquiler-vacacional/pisos-malaga/",),
}
PISOS_HOLIDAY_SEED = AUDITED_HOLIDAY_ROUTES[("Pisos", "province:Málaga")][0]
PISOS_HOLIDAY_NAVIGATION = "https://www.pisos.com/FilterGeo/GetChildren"


@dataclass(frozen=True)
class ScopeDefinition:
    source_name: str
    scope_key: str
    discovery_urls: tuple[str, ...]


def validate_scope(definition: ScopeDefinition) -> ScopeDefinition:
    if definition.scope_key.endswith(":holiday") or any(
        "/alquiler-vacacional/" in url or "/holiday-rentals" in url for url in definition.discovery_urls
    ):
        raise ValueError("Holiday import scopes are disabled by the long-term policy")
    source = SOURCE_TYPES.get(definition.source_name)
    province = scope_province(definition.scope_key)
    if source is None or not definition.scope_key.startswith("province:") or province is None:
        raise ValueError("Unknown source or Spanish province")
    if not 1 <= len(definition.discovery_urls) <= 6:
        raise ValueError("Each scope needs 1..6 provider discovery routes")
    for url in definition.discovery_urls:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {source.domain, "www." + source.domain}
            or parsed.username
            or parsed.password
            or parsed.port not in {None, 443}
            or parsed.fragment
        ):
            raise ValueError("Scope URL must use HTTPS on the exact public provider host")
        if definition.scope_key.endswith(":holiday") and not (
            definition.source_name == "Pisos" and parsed.path.startswith("/alquiler-vacacional/")
            or definition.source_name == "ThinkSpain" and parsed.path.startswith("/holiday-rentals")
        ):
            raise ValueError("Holiday scopes require a provider holiday catalogue")
    return ScopeDefinition(
        definition.source_name, "province:" + province + (":holiday" if definition.scope_key.endswith(":holiday") else ""),
        tuple(dict.fromkeys(definition.discovery_urls))
    )


def published_holiday_scope_definitions(document: str) -> list[ScopeDefinition]:
    """Read the public widget's province destinations verbatim; never build slugs."""
    payload = json.loads(document)
    rows = payload.get("SelectableGeos") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Invalid bounded provider province navigation")
    definitions = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("LevelTypeForAnalytics") != "provincia":
            continue
        province = canonical_province(row.get("Name"))
        route = row.get("DestinationUrl")
        if not province or not isinstance(route, str) or not route or not str(row.get("AdsNumber", "")).isdigit():
            continue
        if int(row["AdsNumber"]) <= 0:
            continue
        url = urljoin(PISOS_HOLIDAY_NAVIGATION, route)
        match = re.fullmatch(r"/alquiler-vacacional/pisos-([^/]+)/?", urlparse(url).path)
        if not match or canonical_province(match.group(1)) != province:
            raise ValueError("Holiday navigation destination disagrees with its province")
        definition = validate_scope(ScopeDefinition("Pisos", f"province:{province}:holiday", (url,)))
        definitions[definition.scope_key] = definition
    return sorted(definitions.values(), key=lambda value: value.scope_key)


async def discover_published_holiday_scopes(source: ExternalListingSource) -> list[ScopeDefinition]:
    raise ValueError("Holiday discovery is disabled by the long-term policy")


def published_scope_definitions(source_name: str, document: str, index_url: str) -> list[ScopeDefinition]:
    """Take URLs verbatim from the provider's geography index, never invent routes."""
    if source_name not in PUBLISHED_GEOGRAPHY or index_url != PUBLISHED_GEOGRAPHY[source_name]:
        raise ValueError("No audited geography index for this source")
    pattern = r"^/habitaciones-([^/]+)/?$" if source_name == "PisoCompartido" else r"^/alquiler/pisos-([^/]+)/?$"
    definitions: dict[str, ScopeDefinition] = {}
    for href in re.findall(r"""href=["']([^"']+)["']""", document, re.IGNORECASE):
        url = urljoin(index_url, html.unescape(href))
        match = re.fullmatch(pattern, urlparse(url).path)
        province = canonical_province(match.group(1)) if match else None
        if province:
            scope_key = "province:" + province
            definition = validate_scope(
                ScopeDefinition(
                    source_name, scope_key, (url,)
                )
            )
            definitions[definition.scope_key] = definition
    return sorted(definitions.values(), key=lambda value: value.scope_key)


async def validate_discovery_route(source: ExternalListingSource, url: str) -> dict[str, Any]:
    """Validate live access and listing destinations without importing any data."""
    document = await source.request(url)
    if not document:
        raise ValueError("Provider discovery route returned no public document")
    diagnostic = source.discovery_diagnostics.get(url, {})
    final_url = str(diagnostic.get("final_url") or url)
    validate_scope(ScopeDefinition(source.name, source.scope_key, (final_url,)))
    # Wrong redirects to homepage cannot validate a province route.
    if urlparse(final_url).path.rstrip("/") != urlparse(url).path.rstrip("/"):
        redirected = (
            published_scope_definitions(
                source.name, f'<a href="{html.escape(final_url)}">province</a>', PUBLISHED_GEOGRAPHY[source.name]
            )
            if source.name in PUBLISHED_GEOGRAPHY
            else []
        )
        if not any(value.scope_key == source.scope_key for value in redirected):
            raise ValueError("Provider redirected away from the published province")
    links = re.findall(r"""href=["']([^"']+)["']""", document, re.IGNORECASE)
    discovered = {
        urljoin(url, html.unescape(link)).split("?", 1)[0]
        for link in links
        if source.is_listing_url(urljoin(url, html.unescape(link)))
    }
    # Empty catalogues are supported only if the provider explicitly says so.
    empty = bool(
        re.search(
            r"no (?:hay |hemos encontrado )?(?:resultados|anuncios|habitaciones|viviendas)", document, re.IGNORECASE
        )
    )
    if not discovered and not empty:
        raise ValueError("No listing links or explicit empty-catalogue evidence")
    return {
        "url": url,
        "final_url": final_url,
        "status": diagnostic.get("status"),
        "discovered_sample": len(discovered),
        "empty": empty,
    }


async def provision_scopes(session: AsyncSession, definitions: list[ScopeDefinition], *, enable: bool = False) -> int:
    """Upsert on existing unique key; reruns never disable or enable implicitly."""
    validated = [validate_scope(value) for value in definitions]
    for definition in validated:
        statement = insert(ExternalImportScope).values(
            source_name=definition.source_name,
            scope_key=definition.scope_key,
            discovery_urls=list(definition.discovery_urls),
            enabled=enable,
        )
        updates: dict[str, Any] = {"discovery_urls": statement.excluded.discovery_urls}
        if enable:
            updates["enabled"] = True
        await session.execute(
            statement.on_conflict_do_update(
                constraint="uq_external_import_scope",
                set_=updates,
            )
        )
    await session.commit()
    return len(validated)
