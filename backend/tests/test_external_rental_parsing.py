from __future__ import annotations

import asyncio
import re
from dataclasses import replace
from pathlib import Path

import pytest

from app.commands.bootstrap_external_spain import import_lease
from app.external_sources import (
    ExternalListingSource,
    FlatioSource,
    PisoCompartidoSource,
    PisosSource,
    is_in_import_scope,
)
from app.rental_classification import ONE_BEDROOM, ROOM, SHARED_ROOM, STUDIO, property_type, rental_price
from app.services.external_import import completed_source_contract
from app.services.external_scopes import (
    PUBLISHED_GEOGRAPHY,
    ScopeDefinition,
    published_scope_definitions,
    validate_discovery_route,
    validate_scope,
)
from app.spain_provinces import PROVINCES


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"title": "Habitación individual en alquiler"}, ROOM),
        ({"title": "Se alquila habitación compartida"}, SHARED_ROOM),
        ({"title": "Se alquila habitación en piso de 4 dormitorios"}, ROOM),
        ({"title": "Estudio en alquiler"}, STUDIO),
        ({"title": "Studio for rent"}, STUDIO),
        ({"title": "Piso completo de 1 habitación"}, ONE_BEDROOM),
        ({"title": "Apartamento en alquiler", "property_type": "apartment", "bedroom_count": 1}, ONE_BEDROOM),
        ({"title": "Piso de 2 dormitorios"}, None),
        ({"title": "Piso de 3 habitaciones"}, None),
        ({"title": "Piso de 20 dormitorios"}, None),
        ({"title": "Estudio en venta"}, None),
        ({"title": "Piso de 1 dormitorio", "operation": "sale"}, None),
        ({"title": "Busco habitación en alquiler"}, None),
        ({"title": "Busco estudio"}, None),
        ({"title": "Habitación", "description": "Busco piso para vivir"}, None),
        ({"title": "Garaje en alquiler"}, None),
        ({"title": "Oficina en alquiler"}, None),
        ({"title": "Plaza en habitación compartida"}, None),
        ({"title": "Casa de 1 dormitorio"}, None),
        ({"title": "Loft en alquiler"}, None),
        ({"title": "Loft en alquiler", "property_type": "loft", "bedroom_count": 0}, STUDIO),
        ({"title": "Habitación amueblada", "property_type": "apartment", "bedroom_count": 3}, None),
        ({"title": "Apartamento con parking", "property_type": "apartment", "bedroom_count": 1}, ONE_BEDROOM),
        (
            {
                "title": "Apartamento",
                "description": "Parking incluido",
                "property_type": "apartment",
                "bedroom_count": 1,
            },
            ONE_BEDROOM,
        ),
        ({"title": "Estudio", "property_type": "villa", "bedroom_count": 1}, None),
        ({"title": "Apartamento", "property_type": "apartment", "bedroom_count": "unknown"}, None),
    ],
)
def test_property_admission(data, expected):
    assert property_type(data, "Pisos") == expected


@pytest.mark.parametrize(
    ("data", "period", "expected"),
    [
        ({"title": "Habitación en alquiler"}, "month", "long"),
        ({"title": "Estudio en alquiler"}, "month", "long"),
        ({"title": "Apartamento de 1 dormitorio"}, "month", "long"),
        ({"title": "Habitación en alquiler"}, "night", "holiday"),
        ({"title": "Estudio vacacional"}, "night", "holiday"),
        ({"title": "Apartamento holiday rental"}, "night", "holiday"),
        ({"title": "Alquiler de temporada"}, None, None),
        ({"title": "Alquiler de temporada"}, "month", "long"),
        ({"title": "Alquiler de temporada"}, "week", None),
        ({"title": "Vacaciones"}, "week", "holiday"),
        ({"title": "Curso académico"}, "month", "long"),
        ({"title": "Estudio", "rental_category": "academic"}, None, "long"),
        ({"title": "Estudio", "description": "Holiday district", "rental_category": "residential"}, "month", "long"),
        ({"title": "Estudio vacacional"}, "month", None),
        ({"title": "Estudio", "rental_category": "long"}, "night", None),
        ({"title": "Estudio", "operation": "sale"}, "month", None),
    ],
)
def test_rental_mode_and_cadence(data, period, expected):
    price = rental_price(data, "Pisos", 700, period)
    assert (price.mode if price else None) == expected
    if price and period == "week":
        assert (price.amount, price.weekly_amount) == (100, 700)


@pytest.mark.parametrize(
    "unit",
    [
        ("Habitación individual en alquiler", ROOM),
        ("Estudio en alquiler", STUDIO),
        ("Piso de 1 dormitorio en alquiler", ONE_BEDROOM),
    ],
)
@pytest.mark.parametrize(("cadence", "mode"), [("mes", "long"), ("noche", "holiday")])
def test_all_property_mode_combinations_reach_normalizer(unit, cadence, mode):
    source = PisosSource()
    source.scope_key = "province:Madrid"
    data = {
        "title": unit[0],
        "description": "Oferta disponible.",
        "price_text": f"90 €/{cadence}",
        "city": "Madrid",
        "province": "Madrid",
        "country": "ES",
        "latitude": 40.4,
        "longitude": -3.7,
    }
    try:
        item = source.normalize_listing(data, "https://www.pisos.com/alquilar/piso-madrid-123456/")
        assert item is not None
        assert (item.room_type, item.rental_mode, item.latitude) == (unit[1], mode, 40.4)
        assert item.fingerprint != replace(item, rental_mode="holiday" if mode == "long" else "long").fingerprint
    finally:
        asyncio.run(source.close())


@pytest.mark.parametrize(
    "province", ["Madrid", "Illes Balears", "Santa Cruz de Tenerife", "Las Palmas", "Ceuta", "Melilla"]
)
def test_structured_spain_province(province):
    assert is_in_import_scope({"province": province, "country": "ES"}, "province:" + province)
    assert not is_in_import_scope({"province": province, "country": "PT"}, "province:" + province)


def test_structured_province_aliases_and_mismatch():
    assert len(PROVINCES) == len(set(PROVINCES)) == 52
    assert is_in_import_scope({"province": "Vizcaya"}, "province:Bizkaia")
    assert is_in_import_scope({"province": "Islas Baleares"}, "province:Illes Balears")
    assert is_in_import_scope({"province": "Islas Baleares - Illes Balears"}, "province:Illes Balears")
    assert not is_in_import_scope({"province": "Barcelona"}, "province:Madrid")
    assert not is_in_import_scope({"province": "unknown"}, "province:unknown")


@pytest.mark.parametrize(
    "url",
    [
        "http://www.pisos.com/alquiler/pisos-madrid/",
        "https://evil.test/alquiler/pisos-madrid/",
        "https://pisos.com.evil.test/",
        "https://user@www.pisos.com/",
        "https://www.pisos.com:9000/",
    ],
)
def test_scope_host_and_scheme_guard(url):
    with pytest.raises(ValueError):
        validate_scope(ScopeDefinition("Pisos", "province:Madrid", (url,)))


def test_published_routes_are_used_verbatim_and_foreign_routes_are_rejected():
    index = PUBLISHED_GEOGRAPHY["PisoCompartido"]
    document = (
        '<a href="/habitaciones-madrid/">Madrid</a><a href="/habitaciones-ceuta/">Ceuta</a>'
        '<a href="/habitaciones-melilla/">Melilla</a><a href="/habitaciones-andorra/">Andorra</a>'
    )
    definitions = published_scope_definitions("PisoCompartido", document, index)
    assert {value.scope_key for value in definitions} == {"province:Madrid", "province:Ceuta", "province:Melilla"}
    assert all(
        value.discovery_urls[0].startswith("https://www.pisocompartido.com/habitaciones-") for value in definitions
    )


def test_repeated_url_sets_stop_partial_and_never_fetch_details_as_pages():
    class Source(ExternalListingSource):
        name, domain = "Example", "example.test"
        discovery_urls = ("https://example.test/search",)
        listing_url_pattern = re.compile(r"/room/\d+/$")

        async def request(self, url):
            return '<a href="/room/123/">room</a><a href="/search?page=2">next</a><a href="/search?page=3">next</a>'

    async def run():
        source = Source()
        try:
            result = await source.discover_listing_urls()
            assert not result.complete
            assert result.visited_pages == 3
            assert len(result.urls) == 1
            assert all("/room/" not in page for page in result.failed_pages)
        finally:
            await source.close()

    asyncio.run(run())


def test_public_pc_newlines_preserve_postal_province_and_real_coordinates():
    source = PisoCompartidoSource()
    source.scope_key = "province:Madrid"
    url = "https://www.pisocompartido.com/habitacion/1052424/"
    document = (
        Path(__file__).with_name("fixtures").joinpath("spain_rental_pisocompartido.html").read_text(encoding="utf-8")
    )
    try:
        data = source.parse_listing(document, url)
        item = source.normalize_listing(data, url)
        assert item and item.city == "Alcalá de Henares" and item.province == "Madrid"
        assert item.latitude == 40.4871246
        source.discovery_urls = ("https://www.pisocompartido.com/habitaciones-madrid/",)
        assert source.is_pagination_url("https://www.pisocompartido.com/habitaciones-madrid/2")
        assert not source.is_pagination_url("https://www.pisocompartido.com/habitaciones-barcelona/2")
    finally:
        asyncio.run(source.close())


def test_flatio_apartment_metadata_never_uses_company_address_or_calls_monthly_holiday():
    source = FlatioSource()
    source.scope_key = "province:Granada"
    url = "https://www.flatio.com/rent/apartment/133393-granada"
    document = Path(__file__).with_name("fixtures").joinpath("spain_rental_flatio.html").read_text(encoding="utf-8")
    try:
        parsed = source.parse_listing(document, url)
        item = source.normalize_listing(parsed, url)
        assert item and (item.room_type, item.rental_mode, item.city, item.price_amount) == (
            STUDIO,
            "long",
            "Granada",
            750,
        )
        parsed["province"] = ""
        assert source.normalize_listing(parsed, url) is None
        parsed["province"] = "Granada"
        parsed["country"] = "CZ"
        assert source.normalize_listing(parsed, url) is None
    finally:
        asyncio.run(source.close())


def test_health_still_requires_publishable_valid_detail_for_whole_units():
    counters = {"discovered_urls": 1, "fetched_details": 1, "accepted_rentals": 1, "accepted_rooms": 0, "imported": 1}
    assert completed_source_contract(counters)
    assert not completed_source_contract({**counters, "imported": 0})


def test_bootstrap_without_redis_requires_explicit_worker_pause(monkeypatch):
    from types import SimpleNamespace

    from app.commands import bootstrap_external_spain as command

    monkeypatch.setattr(command, "get_settings", lambda: SimpleNamespace(redis_url=""))

    async def run():
        with pytest.raises(RuntimeError, match="worker-paused"):
            async with import_lease(worker_paused=False):
                pass

    asyncio.run(run())


def test_pisos_real_holiday_detail_uses_primary_price_unit_and_structured_breadcrumbs():
    source = PisosSource()
    source.scope_key = "province:Málaga"
    url = "https://www.pisos.com/alquilar/estudio-arenas_de_velez-60841572995_109300/"
    document = (
        Path(__file__).with_name("fixtures").joinpath("spain_rental_pisos_holiday.html").read_text(encoding="utf-8")
    )
    try:
        parsed = source.parse_listing(document, url)
        item = source.normalize_listing(parsed, url)
        assert item and (item.province, item.city, item.price_amount, item.rental_mode) == (
            "Málaga",
            "Arenas",
            40,
            "holiday",
        )
        assert item.bedroom_count == 0 and item.price_period == "night"
    finally:
        asyncio.run(source.close())


def test_invalid_structured_studio_bedrooms_fail_closed():
    assert property_type({"property_type": "studio", "bedroom_count": "unknown", "title": "Estudio"}, "Pisos") is None


def test_residential_text_prohibiting_tourist_use_is_not_holiday():
    price = rental_price(
        {"title": "Estudio de temporada", "description": "No alquiler vacacional"}, "Pisos", 800, "month"
    )
    assert price and price.mode == "long"


def test_one_bedroom_with_garage_amenity_remains_an_apartment():
    assert (
        property_type({"title": "Apartamento con garaje", "property_type": "flat", "bedroom_count": 1}, "Habitaclia")
        == ONE_BEDROOM
    )


@pytest.mark.parametrize("redirect,accepted", [("vizcaya", True), ("madrid", False)])
def test_provider_alias_redirect_must_keep_the_same_province(redirect, accepted):
    class Source(PisoCompartidoSource):
        async def request(self, url):
            self.discovery_diagnostics[url] = {
                "final_url": f"https://www.pisocompartido.com/habitaciones-{redirect}/",
                "status": 200,
            }
            return '<a href="/habitacion/123456/">room</a>'

    async def run():
        source = Source()
        source.scope_key = "province:Bizkaia"
        try:
            if accepted:
                assert (await validate_discovery_route(source, "https://www.pisocompartido.com/habitaciones-bizkaia/"))[
                    "status"
                ] == 200
            else:
                with pytest.raises(ValueError, match="redirected"):
                    await validate_discovery_route(source, "https://www.pisocompartido.com/habitaciones-bizkaia/")
        finally:
            await source.close()

    asyncio.run(run())
