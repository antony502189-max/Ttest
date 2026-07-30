import asyncio
import json
import os
import re
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.external_sources import (
    ExternalListingSource,
    FotocasaSource,
    IdealistaSource,
    MilanunciosSource,
    PisoCompartidoSource,
    PisosSource,
    ThinkSpainSource,
    is_in_target_province,
    is_rental,
    is_room_offer,
    parse_price,
)
from app.services.external_import import completeness_score, perceptual_hash, similarity


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
            if path.endswith("/100002/"):
                return httpx.Response(200, text="Anuncio eliminado", request=request)
            if path.endswith("/100003/"):
                return httpx.Response(302, headers={"location": "/alquiler-habitacion/"}, request=request)
            return httpx.Response(200, text="HabitaciГіn individual en alquiler", request=request)

        source.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100404/") == "not_found"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100410/") == "removed"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100403/") == "temporary_error"
        assert await source.check_listing_state("https://www.idealista.com/inmueble/100002/") == "removed"
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
