import asyncio
import json
import os
import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from PIL import Image

from app.external_sources import (
    AlquilerDocenteCanariasSource,
    DiscoveryResult,
    ExternalListingSource,
    FlatioSource,
    FotocasaSource,
    IdealistaSource,
    MilanunciosSource,
    PisoCompartidoSource,
    PisosSource,
    ThinkSpainSource,
    is_in_target_province,
    is_rental,
    is_room_offer,
    parse_optional_date,
    parse_optional_datetime,
    parse_price,
    public_map_coordinates,
)
from app.services.external_import import (
    completeness_score,
    external_storage_key,
    perceptual_hash,
    public_location,
    similarity,
)


def room_offer(**overrides):
    value = {
        "title": "Habitación individual en alquiler",
        "description": "Habitación amueblada para alquilar en piso compartido.",
        "category": "alquiler habitación",
        "breadcrumbs": "Santa Cruz de Tenerife",
        "url": "https://example.test/alquiler-habitacion/123456",
        "price_text": "710 €/mes",
    }
    value.update(overrides)
    return value


def test_strict_room_offer_accepts_only_confirmed_room_rental_in_target_province():
    item = room_offer()
    assert is_room_offer(item)
    assert is_rental(item)
    assert is_in_target_province(item)
    assert is_room_offer(room_offer(title="Habitación individual en apartamento compartido"))


def test_strict_room_offer_rejects_complete_home_sale_search_and_las_palmas():
    assert not is_room_offer(room_offer(title="Piso completo en alquiler"))
    assert not is_rental(room_offer(title="Habitación en venta"))
    assert not is_room_offer(room_offer(title="Busco habitación en alquiler"))
    assert not is_room_offer(room_offer(title="Busco cuarto en piso compartido"))
    assert not is_room_offer(room_offer(title="Estudio en alquiler"))
    assert not is_room_offer(room_offer(title="Casa completa con habitación"))
    assert not is_room_offer(room_offer(title="Plaza en habitación compartida"))
    assert not is_in_target_province(room_offer(breadcrumbs="Las Palmas de Gran Canaria"))


def test_geo_filter_covers_the_whole_santa_cruz_province_not_just_tenerife():
    palmera = room_offer(breadcrumbs="Barlovento, Santa Cruz de Tenerife", city="Barlovento")
    gomera = room_offer(breadcrumbs="Valle Gran Rey, La Gomera", city="Valle Gran Rey")
    herreña = room_offer(breadcrumbs="Valverde, El Hierro", city="Valverde")
    assert is_in_target_province(palmera)
    assert is_in_target_province(gomera)
    assert is_in_target_province(herreña)
    normalized = IdealistaSource().normalize_listing(palmera, "https://www.idealista.com/inmueble/123456/")
    assert normalized is not None and normalized.city == "Barlovento"


def test_coordinates_outside_the_province_are_rejected_even_when_text_mentions_tenerife():
    listing = room_offer(latitude=28.128, longitude=-15.438)  # Gran Canaria
    assert IdealistaSource().normalize_listing(listing, "https://www.idealista.com/inmueble/123456/") is None


def test_public_location_never_falls_back_to_a_municipality_centroid():
    item = IdealistaSource().normalize_listing(
        room_offer(city="Adeje", municipality="Adeje"),
        "https://www.idealista.com/inmueble/123456/",
    )
    assert item is not None
    assert item.latitude is None and item.longitude is None
    assert public_location(item) is None


def test_generic_source_preserves_public_map_point_and_coarse_locality():
    document = """
    <script type="application/ld+json">
    {
      "@type":"Residence",
      "name":"Habitación individual en alquiler",
      "description":"Se alquila habitación amueblada en piso compartido.",
      "address":{
        "addressLocality":"Granadilla de Abona",
        "addressSubLocality":"El Médano",
        "addressRegion":"Santa Cruz de Tenerife",
        "streetAddress":"Avenida pública 10"
      }
    }
    </script>
    <a href="https://www.google.com/maps?q=28.0438656770,-16.5351811288">Mapa</a>
    <p>710 €/mes alquiler habitación</p>
    """
    source = IdealistaSource()
    url = "https://www.idealista.com/inmueble/123456/"
    parsed = source.parse_listing(document, url)
    assert parsed["area"] == "El Médano"
    assert parsed["latitude"] == pytest.approx(28.0438656770)
    assert parsed["longitude"] == pytest.approx(-16.5351811288)

    item = source.normalize_listing(parsed, url)
    assert item is not None
    assert item.city == "Granadilla de Abona"
    assert item.area == "El Médano"
    assert item.public_address == "El Médano"
    assert public_location(item) == pytest.approx((28.0438656770, -16.5351811288))


def test_public_map_coordinates_support_source_static_map_decimal_commas():
    assert public_map_coordinates(
        '<img src="https://maps.example.test/static?center=28%2C0438656770%2C-16%2C5351811288">'
    ) == pytest.approx((28.0438656770, -16.5351811288))


def test_public_map_coordinates_support_real_estate_js_coordinate_keys():
    assert public_map_coordinates(
        '<script>window.marker = {"lat": 28.482123, "long": -16.321987};</script>'
    ) == pytest.approx((28.482123, -16.321987))
    assert public_map_coordinates(
        '<script>window.property = {"property_latitude":"28.482123","property_longitude":"-16.321987"};</script>'
    ) == pytest.approx((28.482123, -16.321987))


def test_public_map_coordinates_support_bare_source_attributes_and_map_paths():
    assert public_map_coordinates(
        '<div class="map" lat="28.5022764" long="-16.3197064"></div>'
    ) == pytest.approx((28.5022764, -16.3197064))
    assert public_map_coordinates(
        f'<div lat="28.5022764" data-meta="{"x" * 1400}" long="-16.3197064"></div>'
    ) == pytest.approx((28.5022764, -16.3197064))
    assert public_map_coordinates(
        '<script>latitude=28.4182; longitude=-16.5001;</script>'
    ) == pytest.approx((28.4182, -16.5001))
    assert public_map_coordinates(
        '<img src="https://map.imghs.net/Cache/Z/1_350_28.4182@-16.5001_1_0.gif">'
    ) == pytest.approx((28.4182, -16.5001))


def test_external_storage_keys_are_unique_per_asset_attempt():
    owner_id = uuid4()
    first = external_storage_key(owner_id, uuid4())
    second = external_storage_key(owner_id, uuid4())

    assert first != second
    assert first.startswith(f"external/{owner_id}/")
    assert first.endswith(".webp")


def test_perceptual_hash_is_stable_for_the_same_public_image():
    image = Image.new("RGB", (16, 16), color="white")
    image.putpixel((0, 0), (0, 0, 0))
    output = BytesIO()
    image.save(output, format="PNG")
    assert perceptual_hash(output.getvalue()) == perceptual_hash(output.getvalue())


def test_source_adapters_normalize_a_long_and_holiday_room_without_inventing_data():
    long_item = IdealistaSource().normalize_listing(room_offer(), "https://www.idealista.com/inmueble/123456/")
    holiday_item = FotocasaSource().normalize_listing(
        room_offer(title="Room for rent", price_text="Desde 65 €/noche"),
        "https://www.fotocasa.es/es/alquiler/inmueble/123456",
    )
    assert long_item is not None
    assert (long_item.rental_mode, long_item.price_amount, long_item.source_price_text) == ("long", 710, "710 €/mes")
    assert holiday_item is not None
    assert (holiday_item.rental_mode, holiday_item.price_amount, holiday_item.price_is_from) == ("holiday", 65, True)
    shared = IdealistaSource().normalize_listing(
        room_offer(title="Habitación compartida en alquiler"), "https://www.idealista.com/inmueble/123458/"
    )
    assert shared is not None and shared.room_type == "Habitación compartida"
    assert long_item.phone is None and long_item.email is None


def test_price_parser_preserves_period_and_from_marker():
    assert parse_price("300 € por semana") == (300, "EUR", "week", False)
    assert parse_price("Consultar precio") == (None, None, None, False)


def test_external_dates_keep_date_and_datetime_semantics_and_student_is_a_restriction():
    published = parse_optional_datetime("2026-07-30T10:30:00Z")
    assert parse_optional_date("30/07/2026").isoformat() == "2026-07-30"
    assert published is not None and published.isoformat().startswith("2026-07-30T10:30:00")
    item = IdealistaSource().normalize_listing(
        room_offer(description="Solo estudiantes. Disponible desde 30/07/2026."),
        "https://www.idealista.com/inmueble/123456/",
    )
    assert item is not None
    assert item.tenant_requirement is None
    assert "Solo estudiantes" in item.restrictions


def test_long_category_does_not_turn_an_unqualified_property_sale_price_into_room_rent():
    item = room_offer(price_text="275.000€", category="compartir vivienda")
    assert FotocasaSource().normalize_listing(item, "https://www.fotocasa.es/es/compartir/vivienda/arona/room/123456/d") is None


def test_each_source_has_its_own_public_discovery_adapter():
    assert IdealistaSource().name == "Idealista"
    assert FotocasaSource().name == "Fotocasa"
    assert MilanunciosSource().name == "Milanuncios"
    assert PisoCompartidoSource().name == "PisoCompartido"
    assert PisosSource().name == "Pisos"
    assert ThinkSpainSource().name == "ThinkSpain"
    assert AlquilerDocenteCanariasSource().name == "AlquilerDocenteCanarias"
    assert FlatioSource().name == "Flatio"


def milanuncios_offer(**overrides):
    value = {
        "title": "Habitación individual en alquiler",
        "description": "Se alquila habitación amueblada en piso compartido.",
        "category": "pisos compartidos alquiler habitación",
        "breadcrumbs": "Arona, Tenerife",
        "url": "https://www.milanuncios.com/pisos-compartidos-en-arona-tenerife/habitacion-individual-599522658.htm",
        "price_text": "710 €/mes",
        "city": "Arona",
        "municipality": "Arona",
        "province": "Santa Cruz de Tenerife",
        "images": [],
    }
    value.update(overrides)
    return value


def test_milanuncios_accepts_supported_canary_detail_routes():
    source = MilanunciosSource()
    assert source.is_listing_url(
        "https://www.milanuncios.com/pisos-compartidos-en-los-erales-tenerife/habitacion-individual-599522658.htm"
    )
    assert source.is_listing_url(
        "https://www.milanuncios.com/alquiler-de-estudios-en-el-chaparral-tenerife/estudio-costa-del-silencio-597460843.htm"
    )
    assert source.is_listing_url(
        "https://www.milanuncios.com/alquiler-de-pisos-en-arona-tenerife/piso-1-dormitorio-598000001.htm"
    )
    assert source.is_listing_url(
        "https://www.milanuncios.com/alquiler-de-apartamentos-en-adeje-tenerife/apartamento-1-dormitorio-598000002.htm"
    )
    assert not source.is_listing_url("https://www.milanuncios.com/alquiler-de-pisos-en-tenerife/")
    assert not source.is_listing_url("https://www.milanuncios.com/venta-de-pisos-en-tenerife/piso-598000003.htm")


@pytest.mark.parametrize(
    ("payload", "url", "expected_type"),
    [
        (
            milanuncios_offer(
                description="Piso de 3 habitaciones. Se alquila habitación individual amueblada.",
            ),
            "https://www.milanuncios.com/pisos-compartidos-en-arona-tenerife/habitacion-individual-599522658.htm",
            "Habitación individual",
        ),
        (
            milanuncios_offer(
                title="Estudio en alquiler en Costa del Silencio",
                description="Estudio amueblado disponible para larga temporada.",
                category="alquiler estudio",
                url="https://www.milanuncios.com/alquiler-de-estudios-en-el-chaparral-tenerife/estudio-costa-del-silencio-597460843.htm",
            ),
            "https://www.milanuncios.com/alquiler-de-estudios-en-el-chaparral-tenerife/estudio-costa-del-silencio-597460843.htm",
            "Estudio",
        ),
        (
            milanuncios_offer(
                title="Piso de 1 dormitorio en alquiler",
                description="Vivienda completa de un dormitorio para larga temporada.",
                category="alquiler piso",
                url="https://www.milanuncios.com/alquiler-de-pisos-en-arona-tenerife/piso-1-dormitorio-598000001.htm",
            ),
            "https://www.milanuncios.com/alquiler-de-pisos-en-arona-tenerife/piso-1-dormitorio-598000001.htm",
            "Apartamento de 1 dormitorio",
        ),
    ],
)
def test_milanuncios_normalizes_rooms_studios_and_one_bedroom_homes(payload, url, expected_type):
    item = MilanunciosSource().normalize_listing(payload, url)
    assert item is not None
    assert item.room_type == expected_type
    assert item.city == "Arona"
    assert item.price_amount == 710
    assert item.price_period == "month"


def test_milanuncios_preserves_source_area_instead_of_collapsing_it_to_city():
    payload = milanuncios_offer(
        area="Los Cristianos",
        latitude=28.0509,
        longitude=-16.7172,
    )
    item = MilanunciosSource().normalize_listing(
        payload,
        "https://www.milanuncios.com/pisos-compartidos-en-arona-tenerife/habitacion-individual-599522658.htm",
    )
    assert item is not None
    assert item.city == "Arona"
    assert item.area == "Los Cristianos"
    assert item.public_address == "Los Cristianos"


@pytest.mark.parametrize(
    ("payload", "url"),
    [
        (milanuncios_offer(title="Piso de 2 dormitorios en alquiler", description="Vivienda completa con dos dormitorios.", category="alquiler piso"),
         "https://www.milanuncios.com/alquiler-de-pisos-en-arona-tenerife/piso-2-dormitorios-598000004.htm"),
        (milanuncios_offer(title="Busco estudio en Tenerife", description="Busco estudio económico para vivir.", category="alquiler estudio"),
         "https://www.milanuncios.com/alquiler-de-estudios-en-arona-tenerife/busco-estudio-598000005.htm"),
        (milanuncios_offer(title="Piso de 1 dormitorio en venta", description="Se vende apartamento de un dormitorio.", category="venta piso"),
         "https://www.milanuncios.com/alquiler-de-pisos-en-arona-tenerife/piso-en-venta-598000006.htm"),
        (milanuncios_offer(title="Estudio en alquiler", description="Estudio disponible en Arrecife.", category="alquiler estudio",
                           breadcrumbs="Arrecife, Lanzarote", city="Arrecife", municipality="Arrecife", province="Las Palmas"),
         "https://www.milanuncios.com/alquiler-de-estudios-en-arrecife-lanzarote/estudio-598000007.htm"),
        (milanuncios_offer(title="Apartamento de 1 dormitorio en alquiler", description="Apartamento disponible en Puerto del Rosario.",
                           category="alquiler apartamento", breadcrumbs="Puerto del Rosario, Fuerteventura",
                           city="Puerto del Rosario", municipality="Puerto del Rosario", province="Las Palmas"),
         "https://www.milanuncios.com/alquiler-de-apartamentos-en-puerto-del-rosario-fuerteventura/apartamento-598000010.htm"),
    ],
)
def test_milanuncios_rejects_non_target_inventory_and_islands_outside_map(payload, url):
    assert MilanunciosSource().normalize_listing(payload, url) is None


@pytest.mark.parametrize(
    ("city", "breadcrumbs", "latitude", "longitude"),
    [
        ("Arona", "Arona, Tenerife", 28.0509, -16.7172),
        ("Santa Cruz de La Palma", "Santa Cruz de La Palma, La Palma", 28.6835, -17.7642),
        ("Valle Gran Rey", "Valle Gran Rey, La Gomera", 28.0964, -17.3336),
        ("Valverde", "Valverde, El Hierro", 27.8063, -17.9158),
        ("Las Palmas de Gran Canaria", "Las Palmas de Gran Canaria, Gran Canaria", 28.1235, -15.4363),
    ],
)
def test_milanuncios_accepts_all_five_islands_shown_on_map(city, breadcrumbs, latitude, longitude):
    payload = milanuncios_offer(city=city, municipality=city, breadcrumbs=breadcrumbs, latitude=latitude, longitude=longitude)
    item = MilanunciosSource().normalize_listing(
        payload,
        "https://www.milanuncios.com/pisos-compartidos-en-canarias/habitacion-598000012.htm",
    )
    assert item is not None
    assert item.room_type == "Habitación individual"


def test_milanuncios_coordinates_override_misleading_location_text():
    source = MilanunciosSource()
    lanzarote_with_tenerife_text = milanuncios_offer(
        latitude=28.9630, longitude=-13.5477, breadcrumbs="Arona, Tenerife", city="Arona", municipality="Arona"
    )
    assert source.normalize_listing(
        lanzarote_with_tenerife_text,
        "https://www.milanuncios.com/pisos-compartidos-en-canarias/habitacion-598000011.htm",
    ) is None


def test_milanuncios_canarias_catalogues_are_the_only_discovery_pagination_scope():
    source = MilanunciosSource()
    assert source.is_pagination_url("https://www.milanuncios.com/pisos-compartidos-en-canarias/?pagina=2")
    assert source.is_pagination_url("https://www.milanuncios.com/alquiler-de-estudios-en-canarias/?pagina=3")
    assert source.is_pagination_url("https://www.milanuncios.com/alquiler-de-pisos-en-canarias/?pagina=4")
    assert source.is_pagination_url("https://www.milanuncios.com/alquiler-de-apartamentos-en-canarias/?pagina=5")
    assert not source.is_pagination_url("https://www.milanuncios.com/alquiler-de-pisos-en-madrid/?pagina=2")

def test_flatio_accepts_only_in_stock_target_room_from_public_structured_data():
    source = FlatioSource()
    url = "https://www.flatio.com/rent/room/119561-santa_cruz_de_tenerife"
    document = '''
    <script type="application/ld+json">
    {"@type":["Room", "Product"],"name":"Tenerife room","description":"Furnished private room",
     "image":"https://images.example.test/room.jpg","address":{"addressLocality":"Santa Cruz de Tenerife"},
     "geo":{"latitude":28.46,"longitude":-16.25},
     "offers":{"price":788,"priceCurrency":"EUR","availability":"https://schema.org/InStock",
     "priceSpecification":{"referenceQuantity":{"unitCode":"MON"}}}}
    </script>
    '''
    parsed = source.parse_listing(document, url)
    normalized = source.normalize_listing(parsed, url)
    assert normalized is not None
    assert (normalized.external_id, normalized.price_amount, normalized.price_period) == ("119561", 788, "month")
    assert normalized.phone is None and normalized.email is None

    parsed["availability"] = "https://schema.org/OutOfStock"
    assert source.normalize_listing(parsed, url) is None


def test_flatio_sitemap_filter_rejects_whole_homes_and_outside_province_urls():
    source = FlatioSource()
    assert source._target_room_sitemap_url("https://www.flatio.com/rent/room/119561-santa_cruz_de_tenerife")
    assert not source._target_room_sitemap_url("https://www.flatio.com/rent/apartment/119561-santa_cruz_de_tenerife")
    assert not source._target_room_sitemap_url("https://www.flatio.com/rent/room/119561-las_palmas_de_gran_canaria")


def test_pisos_detail_url_and_public_municipality_slug_are_normalized():
    source = PisosSource()
    url = "https://www.pisos.com/alquilar/habitacion-el_rosario_la_esperanza-65036703493_106000/"
    assert source.is_listing_url(url)
    parsed = source.parse_listing(
        "<title>Habitación en alquiler</title><body>520 €/mes alquiler habitación</body>", url
    )
    assert parsed["city"] == "El Rosario"
    assert parsed["province"] == "Santa Cruz de Tenerife"


def test_thinkspain_requires_an_explicit_room_phrase_not_a_one_bedroom_flat():
    source = ThinkSpainSource()
    url = "https://www.thinkspain.com/property-to-rent-long-term/8247202"
    assert source.is_listing_url(url)
    assert source.normalize_listing(room_offer(title="1 bedroom apartment for rent", description="Santa Cruz de Tenerife"), url) is None
    accepted = source.normalize_listing(
        room_offer(title="Private room for rent", description="Private room for rent in Santa Cruz de Tenerife"), url
    )
    assert accepted is not None


@pytest.mark.parametrize(
    ("source", "fixture", "url"),
    [
        (PisosSource, "pisos", "https://www.pisos.com/alquilar/habitacion-el_rosario-65036703493_106000/"),
        (ThinkSpainSource, "thinkspain", "https://www.thinkspain.com/property-to-rent-long-term/8247202"),
    ],
)
def test_new_source_fixtures_parse_confirmed_room_offers(source, fixture, url):
    document = (Path(__file__).parent / "fixtures" / "external_sources" / fixture / "room.html").read_text(encoding="utf-8")
    parsed = source().parse_listing(document, url)
    normalized = source().normalize_listing(parsed, url)
    assert normalized is not None
    assert normalized.source_price_text.endswith("€/mes")


def test_conservative_text_similarity_requires_substantial_shared_information():
    assert similarity("Habitación amplia en La Laguna", "Habitacion amplia en La Laguna") > 0.9
    assert similarity("Habitación en La Laguna", "Habitación en Arona") < 0.8
    complete = IdealistaSource().normalize_listing(
        room_offer(phone="+34 612 345 678"), "https://www.idealista.com/inmueble/123456/"
    )
    sparse = IdealistaSource().normalize_listing(
        room_offer(description=""), "https://www.idealista.com/inmueble/123457/"
    )
    assert complete is not None and sparse is not None
    assert completeness_score(complete) > completeness_score(sparse)


def test_html_meta_fallback_parses_public_listing_when_json_ld_is_missing():
    document = """
    <html><head>
      <meta property="og:title" content="Habitación individual en alquiler">
      <meta property="og:description" content="Habitación amueblada en Santa Cruz de Tenerife">
      <meta property="og:image" content="https://images.example.test/room.jpg">
    </head><body>710 €/mes · Santa Cruz de Tenerife · alquiler habitación</body></html>
    """
    parsed = IdealistaSource().parse_listing(document, "https://www.idealista.com/inmueble/123456/")
    assert parsed["title"] == "Habitación individual en alquiler"
    assert parsed["description"] == "Habitación amueblada en Santa Cruz de Tenerife"
    assert parsed["images"] == ["https://images.example.test/room.jpg"]


def test_detail_state_distinguishes_removed_pages_and_transient_access_errors():
    async def verify() -> None:
        source = IdealistaSource()
        await source.client.aclose()

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/100404/"):
                return httpx.Response(404, request=request)
            if path.endswith("/100410/"):
                return httpx.Response(410, request=request)
            if path.endswith("/100403/"):
                return httpx.Response(403, request=request)
            if path.endswith("/100429/"):
                return httpx.Response(429, request=request)
            if path.endswith("/100500/"):
                return httpx.Response(500, request=request)
            if path.endswith("/100timeout/"):
                raise httpx.ReadTimeout("test timeout", request=request)
            if path.endswith("/100002/"):
                return httpx.Response(200, text="Anuncio eliminado", request=request)
            if path.endswith("/100004/"):
                return httpx.Response(200, text="Ya no disponible", request=request)
            if path.endswith("/100003/"):
                return httpx.Response(302, headers={"location": "/alquiler-habitacion/"}, request=request)
            return httpx.Response(200, text="HabitaciГіn individual en alquiler", request=request)

        source.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100404/") == "not_found"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100410/") == "removed"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100403/") == "temporary_error"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100429/") == "temporary_error"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100500/") == "temporary_error"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100timeout/") == "temporary_error"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100002/") == "removed"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100004/") == "removed"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100003/") == "removed"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/123456/") == "active"
        await source.close()

    asyncio.run(verify())


def test_detail_request_marks_410_and_catalog_redirect_as_confirmed_removals():
    async def verify() -> None:
        source = IdealistaSource()
        await source.client.aclose()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/100410/"):
                return httpx.Response(410, request=request)
            if request.url.path.endswith("/100003/"):
                return httpx.Response(302, headers={"location": "/alquiler-habitacion/"}, request=request)
            return httpx.Response(200, text="catalog", request=request)

        source.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
        gone = "https://www.idealista.com/inmueble/100410/"
        redirected = "https://www.idealista.com/inmueble/100003/"
        assert await source.fetch_listing(gone) is None
        assert await source.fetch_listing(redirected) is None
        assert source.removed_urls == {gone, redirected}
        await source.close()

    asyncio.run(verify())


def test_discovery_is_partial_when_pagination_limit_prevents_reaching_end():
    class PagedSource(ExternalListingSource):
        name = "Paged"
        domain = "example.test"
        url_tokens = ("/room/",)
        listing_url_pattern = re.compile(r"/room/\d+/?$")
        discovery_urls = ("https://example.test/search",)
        max_discovery_pages = 1

        async def request(self, url: str) -> str:
            return '<a href="/room/1/">room</a><a href="/search?page=2">next</a><p>2 anuncios</p>'

    async def verify() -> None:
        source = PagedSource()
        result = await source.discover_listing_urls()
        assert result.urls == {"https://example.test/room/1/"}
        assert result.complete is False
        assert result.reached_last_page is False
        assert result.expected_total == 2
        await source.close()

    asyncio.run(verify())


def test_discovery_is_partial_when_a_pagination_page_fails():
    class PagedSource(ExternalListingSource):
        name = "Paged"
        domain = "example.test"
        url_tokens = ("/room/",)
        listing_url_pattern = re.compile(r"/room/\d+/?$")
        discovery_urls = ("https://example.test/search",)

        async def request(self, url: str) -> str:
            if "page=2" in url:
                raise RuntimeError("temporary page error")
            return '<a href="/room/1/">room</a><a href="/search?page=2">next</a>'

    async def verify() -> None:
        source = PagedSource()
        result = await source.discover_listing_urls()
        assert result.complete is False
        assert result.failed_pages == ["https://example.test/search?page=2"]
        assert result.reached_last_page is True
        await source.close()

    asyncio.run(verify())


def test_pisocompartido_discovery_ignores_locale_switcher_detail_links_as_pagination():
    async def verify() -> None:
        source = PisoCompartidoSource()

        async def request(_: str) -> str:
            return (
                '<a href="/habitacion/1008162/">room</a>'
                '<a href="/ca/habitacio/1008162/">Catal\u00e0</a>'
                '<a href="/en/room/1008162/">English</a>'
            )

        source.request = request  # type: ignore[method-assign]
        result = await source.discover_listing_urls()
        assert result.complete is True
        assert result.visited_pages == 1
        await source.close()

    asyncio.run(verify())


def test_fotocasa_discovery_reads_listing_urls_from_next_data_when_html_has_only_one_card_link():
    urls = [
        "https://www.fotocasa.es/es/compartir/vivienda/adeje/amueblado/100001/d",
        "https://www.fotocasa.es/es/compartir/vivienda/arona/amueblado/100002/d",
        "https://www.fotocasa.es/es/compartir/vivienda/la-laguna/amueblado/100003/d",
    ]
    document = (
        f'<a href="{urls[0]}">visible card</a>'
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps({"props": {"pageProps": {"cards": [{"url": url, "id": str(index)} for index, url in enumerate(urls, 100001)]}}})}</script>'
        "<p>3 habitaciones</p>"
    )

    async def verify() -> None:
        source = FotocasaSource()

        async def request(_: str) -> str:
            return document

        source.request = request  # type: ignore[method-assign]
        result = await source.discover_listing_urls()
        assert result.urls == set(urls)
        assert result.complete is True
        assert result.expected_total == 3
        assert result.reached_last_page is True
        await source.close()

    asyncio.run(verify())


def test_embedded_public_json_fallback_parses_listing_state():
    document = """
    <script id="__NEXT_DATA__" type="application/json">
      {"props":{"pageProps":{"listing":{"title":"Habitación individual en alquiler","description":"Piso compartido en Adeje","telephone":"+34 612 345 678","email":"owner@example.test","images":["https://images.example.test/room.jpg"]}}}}
    </script>
    <body>710 €/mes · Adeje · alquiler habitación</body>
    """
    parsed = FotocasaSource().parse_listing(document, "https://www.fotocasa.es/es/alquiler/inmueble/123456")
    assert parsed["title"] == "Habitación individual en alquiler"
    assert parsed["description"] == "Piso compartido en Adeje"
    assert parsed["images"] == ["https://images.example.test/room.jpg"]
    assert parsed["phone"] == "+34 612 345 678"
    assert parsed["email"] == "owner@example.test"


def test_fotocasa_and_pisocompartido_use_their_own_detail_field_fallbacks():
    fotocasa = FotocasaSource().parse_listing(
        '''<h1>Habitación Fotocasa</h1><script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"property":{"title":"Habitación JSON","description":"Detalle compartido","priceText":"680 €/mes","city":"Adeje","agencyName":"Agencia pública","availableFrom":"2026-08-01","publishedAt":"2026-07-30T08:00:00Z"}}}}</script>''',
        "https://www.fotocasa.es/es/compartir/vivienda/adeje/123456/d",
    )
    piso = PisoCompartidoSource().parse_listing(
        '<h1>Habitación PisoCompartido</h1><div class="descripcion">Detalle de habitación compartida</div>'
        '<p>Precio: 640 € al mes</p><img data-src="https://images.example.test/piso.jpg">'
        '<p>Disponible desde 2026-08-15</p>',
        "https://www.pisocompartido.com/habitacion/123456/",
    )
    assert fotocasa["title"] == "Habitación JSON"
    assert fotocasa["advertiser_name"] == "Agencia pública"
    assert piso["title"] == "Habitación PisoCompartido"
    assert piso["images"] == ["https://images.example.test/piso.jpg"]


def test_alquiler_docente_sitemap_discovery_stays_with_target_room_adverts():
    sitemap = """
    <urlset>
      <url><loc><![CDATA[https://alquilerdocentecanarias.com/estate_property/habitacion-en-san-cristobal-de-la-laguna-tenerife/]]></loc></url>
      <url><loc>https://alquilerdocentecanarias.com/estate_property/habitacion-en-ingenio-gran-canaria/</loc></url>
      <url><loc>https://alquilerdocentecanarias.com/estate_property/piso-en-la-laguna-tenerife/</loc></url>
    </urlset>
    """

    async def verify() -> None:
        source = AlquilerDocenteCanariasSource()

        async def request(_: str) -> str:
            return sitemap

        source.request = request  # type: ignore[method-assign]
        result = await source.discover_listing_urls()
        assert result == DiscoveryResult(
            urls={"https://alquilerdocentecanarias.com/estate_property/habitacion-en-san-cristobal-de-la-laguna-tenerife/"},
            complete=True,
            visited_pages=1,
            expected_total=1,
            reached_last_page=True,
        )
        await source.close()

    asyncio.run(verify())


def test_alquiler_docente_reads_template_lat_long_even_when_they_are_far_apart():
    source = AlquilerDocenteCanariasSource()
    document = f"""
    <html>
      <head><title>Habitación en La Laguna</title></head>
      <body>
        <h1>Habitación en San Cristóbal de La Laguna, Tenerife.</h1>
        <div class="property-description">Se alquila habitación amueblada en piso compartido.</div>
        <p>450 € /mes + gastos</p>
        <p>Dirección: Camino Rincón, 21, La Laguna</p>
        <p>Ciudad: La Laguna Código postal: 38203 País: España</p>
        <div lat="28.5022764"></div>
        <!-- {"x" * 1400} -->
        <div long="-16.3197064"></div>
        <p>ID de Inmueble: 74795</p>
      </body>
    </html>
    """
    url = "https://alquilerdocentecanarias.com/estate_property/habitacion-test-san-cristobal-de-la-laguna-tenerife/"
    parsed = source.parse_listing(document, url)
    normalized = source.normalize_listing(parsed, url)
    assert normalized is not None
    assert normalized.latitude == pytest.approx(28.5022764)
    assert normalized.longitude == pytest.approx(-16.3197064)


def test_alquiler_docente_fixture_uses_public_source_id_and_omits_contact_data():
    document = (Path(__file__).parent / "fixtures" / "external_sources" / "alquiler_docente_canarias" / "room.html").read_text(
        encoding="utf-8"
    )
    source = AlquilerDocenteCanariasSource()
    url = "https://alquilerdocentecanarias.com/estate_property/habitacion-en-san-cristobal-de-la-laguna-tenerife/"
    parsed = source.parse_listing(document, url)
    normalized = source.normalize_listing(parsed, url)
    assert normalized is not None
    assert normalized.external_id == "74795"
    assert normalized.city == "La Laguna"
    assert normalized.price_amount == 450
    assert normalized.price_period == "month"
    assert normalized.latitude == pytest.approx(28.482123)
    assert normalized.longitude == pytest.approx(-16.321987)
    assert normalized.phone is None and normalized.whatsapp is None and normalized.email is None
    assert normalized.photos == ["https://images.example.test/alquiler-docente-room.jpg"]


def test_structured_items_are_merged_for_public_address_coordinates_and_all_photos():
    document = """
    <script type="application/ld+json">
      [{"@type":"Product","image":"https://images.example.test/cover.jpg"},
       {"@type":"Residence","address":{"addressLocality":"Arona","addressRegion":"Santa Cruz de Tenerife","streetAddress":"Calle Venus"},
        "geo":{"latitude":"28.014793","longitude":"-16.653652"},
        "photo":[{"contentUrl":"https://images.example.test/cover.jpg"},{"contentUrl":"https://images.example.test/second.jpg"}]}]
    </script>
    <meta property="og:title" content="Habitación individual en alquiler">
    <meta property="og:description" content="Se alquila habitación en piso compartido">
    <body>450€ al mes · Arona</body>
    """
    parsed = PisoCompartidoSource().parse_listing(document, "https://www.pisocompartido.com/habitacion/1008162/")
    assert parsed["city"] == "Arona"
    assert parsed["latitude"] == "28.014793"
    assert parsed["longitude"] == "-16.653652"
    assert parsed["images"] == ["https://images.example.test/cover.jpg", "https://images.example.test/second.jpg"]
    assert parsed["price_text"] == "450€ al mes"


@pytest.mark.parametrize(
    ("source", "fixture", "url"),
    [
        (IdealistaSource, "idealista", "https://www.idealista.com/inmueble/123456/"),
        (FotocasaSource, "fotocasa", "https://www.fotocasa.es/es/alquiler/inmueble/123456"),
        (MilanunciosSource, "milanuncios", "https://www.milanuncios.com/habitaciones-en-alquiler/123456.htm"),
        (PisoCompartidoSource, "pisocompartido", "https://www.pisocompartido.com/habitacion/123456/"),
    ],
)
def test_source_specific_room_fixtures(source, fixture, url):
    document = (Path(__file__).parent / "fixtures" / "external_sources" / fixture / "room.html").read_text(
        encoding="utf-8"
    )
    parsed = source().parse_listing(document, url)
    normalized = source().normalize_listing(parsed, url)
    assert normalized is not None
    assert normalized.source_price_text == "710 €/mes"


@pytest.mark.parametrize(
    ("source", "fixture", "url"),
    [
        (IdealistaSource, "idealista", "https://www.idealista.com/inmueble/123456/"),
        (FotocasaSource, "fotocasa", "https://www.fotocasa.es/es/alquiler/inmueble/123456"),
        (MilanunciosSource, "milanuncios", "https://www.milanuncios.com/habitaciones-en-alquiler/123456.htm"),
        (PisoCompartidoSource, "pisocompartido", "https://www.pisocompartido.com/habitacion/123456/"),
    ],
)
def test_source_case_fixtures_keep_only_confirmed_room_offers(source, fixture, url):
    cases = json.loads(
        (Path(__file__).parent / "fixtures" / "external_sources" / fixture / "cases.json").read_text(encoding="utf-8")
    )
    adapter = source()
    assert adapter.normalize_listing(cases["long"], url) is not None
    holiday = adapter.normalize_listing(cases["holiday"], url)
    assert holiday is not None and holiday.rental_mode == "holiday" and holiday.price_is_from
    changed = adapter.normalize_listing(cases["changed_price"], url)
    assert changed is not None and changed.source_price_text == "740 €/mes"
    assert all(
        adapter.normalize_listing(cases[name], url) is None
        for name in ("complete_home", "sale", "wanted", "wrong_location", "deleted")
    )
    missing_contact = adapter.normalize_listing(cases["missing_contact"], url)
    assert missing_contact is not None and missing_contact.phone is None and missing_contact.email is None


@pytest.mark.skipif(os.getenv("RUN_LIVE_EXTERNAL_SOURCE_TESTS") != "1", reason="opt-in public-source smoke test")
def test_live_public_source_discovery_is_opt_in_and_isolates_blocked_sources():
    async def discover() -> dict[str, int | None]:
        results: dict[str, int | None] = {}
        for source in (IdealistaSource(), FotocasaSource(), MilanunciosSource(), PisoCompartidoSource()):
            try:
                results[source.name] = len(await source.discover_listing_urls())
            except (RuntimeError, httpx.HTTPError):
                # Public anti-bot responses are expected and must stay isolated.
                results[source.name] = None
            finally:
                await source.close()
        return results

    results = asyncio.run(discover())
    assert set(results) == {"Idealista", "Fotocasa", "Milanuncios", "PisoCompartido"}
