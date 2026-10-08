from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.external_sources import PisosSource, is_in_import_scope
from app.services.external_scopes import (
    ScopeDefinition,
    discover_published_holiday_scopes,
    published_holiday_scope_definitions,
    validate_scope,
)

FIXTURE = Path(__file__).with_name("fixtures") / "pisos_holiday_provinces.json"


def test_real_provider_navigation_covers_all_productive_spain_provinces_without_guessed_slugs():
    definitions = published_holiday_scope_definitions(FIXTURE.read_text(encoding="utf-8-sig"))
    rows = {d.scope_key: d.discovery_urls for d in definitions}
    assert len(rows) == 27
    assert rows["province:Alicante:holiday"] == ("https://www.pisos.com/alquiler-vacacional/pisos-alicante/",)
    assert "province:Santa Cruz de Tenerife:holiday" in rows
    assert "province:Illes Balears:holiday" in rows
    assert "province:A Coruña:holiday" in rows
    assert not any("Andorra" in key or "Frances" in key for key in rows)
    assert "province:Ceuta:holiday" not in rows  # Published zero, with no route.


@pytest.mark.parametrize("route", ["https://evil.test/alquiler-vacacional/pisos-madrid/",
                                   "/alquiler/pisos-madrid/", "/alquiler-vacacional/pisos-barcelona/"])
def test_navigation_rejects_foreign_hosts_residential_routes_and_province_mismatches(route):
    payload = {"SelectableGeos": [{"Name": "Madrid", "DestinationUrl": route,
                                   "AdsNumber": "7", "LevelTypeForAnalytics": "provincia"}]}
    with pytest.raises(ValueError):
        published_holiday_scope_definitions(json.dumps(payload))


def test_holiday_scope_requires_holiday_catalogue_and_strict_province():
    assert is_in_import_scope({"province": "Alicante", "country": "ES"}, "province:Alicante:holiday")
    assert not is_in_import_scope({"province": "Murcia", "country": "ES"}, "province:Alicante:holiday")
    assert not is_in_import_scope({"province": "Alicante", "country": "PT"}, "province:Alicante:holiday")
    with pytest.raises(ValueError, match="holiday catalogue"):
        validate_scope(ScopeDefinition("Pisos", "province:Madrid:holiday", ("https://www.pisos.com/alquiler/pisos-madrid/",)))


def test_discovery_uses_public_widget_context_and_empty_ancestor_without_constructing_provinces():
    class Source(PisosSource):
        async def request(self, url):
            if "GetChildren" in url:
                assert "geoId=&" in url
                assert "serializedSearchContext=0.0101.F002." in url
                assert "isSearchResultsView=false" in url
                return FIXTURE.read_text(encoding="utf-8-sig")
            return '<input id="hdnSearchContext" value="0.0101.F002.P00000000000029.0"/>'

    async def run():
        source = Source()
        try:
            assert len(await discover_published_holiday_scopes(source)) == 27
        finally:
            await source.close()
    asyncio.run(run())


def test_holiday_scope_rejects_monthly_recommendations_while_legacy_long_scope_still_accepts():
    data = {"title": "Apartamento", "description": "Larga estancia", "property_type": "apartment",
            "bedroom_count": 1, "rental_category": "residential", "price_text": "950 €/mes",
            "city": "Madrid", "province": "Madrid", "country": "ES"}
    source = PisosSource()
    try:
        source.scope_key = "province:Madrid:holiday"
        assert source.normalize_listing(data, "https://www.pisos.com/alquilar/piso-madrid-123456/") is None
        source.scope_key = "province:Madrid"
        item = source.normalize_listing(data, "https://www.pisos.com/alquilar/piso-madrid-123456/")
        assert item and item.rental_mode == "long" and item.price_amount == 950
    finally:
        asyncio.run(source.close())


@pytest.mark.parametrize("label,amount,expected", [("sem", 490, (70, "week")),
                                                  ("d&#xED;a", 70, (70, "night"))])
def test_pisos_price_selector_preserves_its_selected_cadence_even_when_title_disagrees(label, amount, expected):
    source = PisosSource()
    source.scope_key = "province:A Coruña:holiday"
    document = f'''<meta property="og:title" content="Piso en Cariño por 490 €/día">
      <script type="application/ld+json">{{"@type":"Apartment","propertyType":"apartment",
      "numberOfBedrooms":1,"name":"Apartamento","description":"Alquiler vacacional",
      "rentalCategory":"holiday","address":{{"addressLocality":"Cariño","addressRegion":"A Coruña","addressCountry":"ES"}}}}</script>
      <div class="price__value jsPriceValue">{amount} €</div>
      <select class="price__selector jsPriceSelector">
        <option data-value="999 €">mes</option>
        <option data-value="{amount} &#x20AC;" selected="selected">{label}</option>
      </select>'''
    try:
        parsed = source.parse_listing(document, "https://www.pisos.com/alquilar/piso-carino-9246773760_999170/")
        item = source.normalize_listing(parsed, parsed["url"])
        assert item and (item.price_amount, item.price_period) == expected
        assert item.rental_mode == "holiday"
        assert item.weekly_price_amount == (490 if expected[1] == "week" else None)
        assert parsed["raw"]["price_cadence_evidence"]["primary_text"] == f"{amount} €"
    finally:
        asyncio.run(source.close())


@pytest.mark.parametrize("option", ['<option data-value="70 €" selected>día</option>',
                                     '<option data-value="490 €">día</option>',
                                     '<option data-value="490 €" selected>temporada</option>'])
def test_pisos_selector_never_guesses_from_unselected_mismatched_or_ambiguous_options(option):
    source = PisosSource()
    try:
        data = source.parse_listing(f'<div class="jsPriceValue">490 €</div><select class="jsPriceSelector">{option}</select>',
                                    "https://www.pisos.com/alquilar/piso-carino-123456/")
        assert data["price_text"] == "490 €"
        assert "price_cadence_evidence" not in data["raw"]
    finally:
        asyncio.run(source.close())


@pytest.mark.parametrize('bedrooms,price,provider_type,structured_type,accepted', [
    (1, '120 €/día', 'aticos', None, True),
    (2, '120 €/día', 'aticos', None, False),
    (1, '1200 €/mes', 'aticos', None, False),
    (1, '120 €', 'aticos', None, False),
    (1, '120 €/día', 'casas', None, False),
    (1, '120 €/día', '', None, False),
    (1, '120 €/día', 'aticos', 'house', False),
    (1, '120 €/día', 'aticos', 'hotel', False),
])
def test_published_penthouse_apartment_keeps_existing_bedroom_price_and_type_restrictions(
    bedrooms, price, provider_type, structured_type, accepted,
):
    # Public fields captured from the Roquetas de Mar holiday detail: the
    # headline says "Ático", the provider's own type is "aticos".
    document = f'''<meta property="og:title" content="Ático en alquiler en Centro">
      <div class="jsPriceValue">{price}</div>
      <span id="vtmExtraVars" data-var='{{"nHabitaciones":"{bedrooms}"}}'></span>
      <span id="gaCusVar" data-var="({{tipoOperacion:'alquiler',tipoInmueble:'{provider_type}'}})"></span>
      <div class="breadcrumb__item"><a href="/alquiler-vacacional_viviendas/almeria/">Almería</a></div>
      <div class="breadcrumb__item"><a href="/alquiler-vacacional_viviendas/roquetas_de_mar/">Roquetas de Mar</a></div>
      <div class="breadcrumb__item">Ático en alquiler vacacional en Centro</div>'''
    if structured_type:
        document += f'<script type="application/ld+json">{{"propertyType":"{structured_type}"}}</script>'
    source = PisosSource()
    source.scope_key = 'province:Almería:holiday'
    url = 'https://www.pisos.com/alquilar/atico-barrio_centro-55002100609_100500/'
    try:
        parsed = source.parse_listing(document, url)
        item = source.normalize_listing(parsed, url)
        assert bool(item) is accepted
        if item:
            assert (item.room_type, item.rental_mode, item.price_amount, item.price_period) == (
                'Apartamento de 1 dormitorio', 'holiday', 120, 'night',
            )
            assert parsed['raw']['property_type_evidence']['value'] == 'aticos'
        if structured_type:
            assert 'property_type_evidence' not in parsed['raw']
    finally:
        asyncio.run(source.close())


def test_penthouse_discovery_requires_holiday_scope_and_provider_https_host():
    source = PisosSource()
    url = 'https://www.pisos.com/alquilar/atico-torrox_torrox_costa-45091123400_108500/'
    try:
        assert not source.is_listing_url(url)
        source.scope_key = 'province:Málaga:holiday'
        assert source.is_listing_url(url)
        assert not source.is_listing_url(url.replace('https:', 'http:'))
        assert not source.is_listing_url(url.replace('www.pisos.com', 'www.pisos.com.evil.test'))
        assert not source.is_listing_url(url.replace('/atico-', '/casa-'))
        source.scope_key = 'province:Málaga'
        assert not source.is_listing_url(url)
    finally:
        asyncio.run(source.close())
