from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import app.habitaclia_source as habitaclia_module
from app import external_sources
from app.habitaclia_source import HabitacliaSource, install_habitaclia_source


def test_public_uuid_detail_uses_primary_structured_unit_and_preserves_legacy_id():
    source = HabitacliaSource()
    url = "https://www.habitaclia.com/alquiler/apartamento/calle-asturias/costa-adeje/adeje/40910a17-9d4d-40f8-ad52-db8e7f9165f2/d"
    document = Path(__file__).with_name("fixtures").joinpath("habitaclia_uuid_rental.html").read_text(encoding="utf-8")
    try:
        assert source.is_listing_url(url)
        assert not source.is_listing_url(url.replace("habitaclia.com", "evil.test"))
        parsed = source.parse_listing(document, url)
        assert parsed["property_type"] == "flat" and parsed["bedroom_count"] == 1
        assert source.normalize_listing(parsed, url) is None  # Captured rent is 1,160 EUR/month.
        item = source.normalize_listing({**parsed, "price_text": "1000 €/mes"}, url)
        assert item and (item.city, item.province, item.external_id, item.rental_mode) == (
            "Adeje",
            "Santa Cruz de Tenerife",
            "34745000000014",
            "long",
        )
        assert item.latitude is None and item.longitude is None
        assert item.photos == ["https://static.fotocasa.es/images/ads/sanitized-primary.webp"]
        assert source._public_listing_state(document, "wrong-id") == {}
        assert source.normalize_listing({**parsed, "bedroom_count": 2}, url) is None
    finally:
        asyncio.run(source.close())


def test_uuid_hydration_routes_are_discovered_without_cross_card_classification():
    source = HabitacliaSource()
    first = "/alquiler/apartamento/adeje/40910a17-9d4d-40f8-ad52-db8e7f9165f2/d"
    second = "/alquiler/apartamento/madrid/d08d89e6-e063-49b0-af82-3f060b9445aa/d"
    cards = [
        {"navigationUrl": first, "summary": {"title": "Apartamento de 1 dormitorio"}},
        {"navigationUrl": second, "summary": {"title": "Apartamento de 3 dormitorios"}},
    ]
    doc = "<script>self.__next_f.push(" + json.dumps([1, json.dumps(cards)]) + ")</script>"
    try:
        all_urls, targets = source._extract_page_listings(doc, source.discovery_urls[0])
        assert len(all_urls) == 2 and targets == {"https://www.habitaclia.com" + first}
        from app.commands.audit_habitaclia_source import _catalog_probe

        probe = _catalog_probe(source, f'<a href="{first}">Apartamento</a>', source.discovery_urls[0])
        assert probe["recognized_route_samples"] == ["https://www.habitaclia.com" + first]
    finally:
        asyncio.run(source.close())


def room_document() -> str:
    return """
    <html><head><script type="application/ld+json">
    {
      "@type": "Apartment",
      "name": "Alquiler piso. Se alquila habitación en La Laguna",
      "description": "Se alquila habitación amueblada para una persona, disponible para larga estancia.",
      "address": {"addressLocality": "La Laguna", "addressRegion": "Santa Cruz de Tenerife"},
      "image": ["https://images.habimg.com/example-room.jpg"]
    }
    </script></head><body>
      <h1>Alquiler piso. Se alquila habitación en La Laguna</h1>
      <div class="description">Se alquila habitación amueblada para una persona, disponible para larga estancia.</div>
      <strong>530 €</strong>
    </body></html>
    """


def studio_document() -> str:
    return """
    <html><head><script type="application/ld+json">
    {
      "@type": "Apartment",
      "name": "Estudio amueblado en Puerto de la Cruz",
      "description": "Estudio completo con cocina y baño, disponible para alquiler de larga estancia.",
      "address": {"addressLocality": "Puerto de la Cruz", "addressRegion": "Santa Cruz de Tenerife"}
    }
    </script></head><body>
      <h1>Estudio amueblado en Puerto de la Cruz</h1>
      <div class="description">Estudio completo con cocina y baño, disponible para alquiler de larga estancia.</div>
      <strong>650 €</strong>
    </body></html>
    """


def one_bedroom_whole_home_document() -> str:
    return """
    <html><head><script type="application/ld+json">
    {
      "@type": "Apartment",
      "name": "Piso de una habitación en alquiler por temporadas en Garachico",
      "description": "Apartamento completo de una habitación, salón, cocina y baño para alquiler por temporadas.",
      "address": {"addressLocality": "Garachico", "addressRegion": "Santa Cruz de Tenerife"}
    }
    </script></head><body>
      <h1>Piso de una habitación en alquiler por temporadas en Garachico</h1>
      <div class="description">Apartamento completo de una habitación, salón, cocina y baño.</div>
      <strong>780 €/mes</strong>
    </body></html>
    """


def whole_home_document() -> str:
    return """
    <html><head><script type="application/ld+json">
    {
      "@type": "Apartment",
      "name": "Piso de 3 habitaciones en alquiler en La Laguna",
      "description": "Vivienda completa con tres habitaciones, salón, cocina y baño.",
      "address": {"addressLocality": "La Laguna", "addressRegion": "Santa Cruz de Tenerife"}
    }
    </script></head><body>
      <h1>Piso de 3 habitaciones en alquiler en La Laguna</h1>
      <div class="description">Vivienda completa con tres habitaciones, salón, cocina y baño.</div>
      <strong>1.200 €</strong>
    </body></html>
    """


def el_medano_location_document() -> str:
    return """
    <html><head><script type="application/ld+json">
    {
      "@type": "Apartment",
      "name": "Apartamento de una habitación en alquiler en El Médano",
      "description": "Apartamento completo de una habitación para alquiler de larga estancia en El Médano.",
      "address": {
        "addressLocality": "Granadilla de Abona",
        "addressRegion": "Santa Cruz de Tenerife",
        "streetAddress": "Avenida JOSE MIGUEL GALVAN BELLO"
      }
    }
    </script>
    <script>window.mapState = {"lat": 28.0438656770, "long": -16.5351811288};</script>
    </head><body>
      <div>Zona El Médano</div>
      <h1>Apartamento de una habitación en alquiler en El Médano</h1>
      <div class="description">Apartamento completo de una habitación para alquiler de larga estancia.</div>
      <strong>1.100 €/mes</strong>
      <section>
        <h2>Ubicación</h2>
        <h4>El Médano Avenida JOSE MIGUEL GALVAN BELLO</h4>
        <p>Navega por el mapa haciendo clic sobre él</p>
        <img src="https://web.gw.habitaclia.com/v2/staticmap?center=28%2C0438656770%2C-16%2C5351811288&amp;size=640x400&amp;tenant=habitaclia&amp;zoom=17">
      </section>
    </body></html>
    """


def hydration_image_document() -> str:
    return r"""
    <html><head>
      <script type="application/ld+json">
      {
        "@type": "Apartment",
        "name": "Apartamento con ascensor en alquiler en Los Sabandeños",
        "description": "Apartamento completo de una habitación para alquiler de larga estancia.",
        "address": {
          "addressLocality": "Los Cristianos",
          "addressRegion": "Santa Cruz de Tenerife"
        }
      }
      </script>
      <script>
      self.__next_f.push([1,"{\"legacyNumericId\":\"500004551799\",\"navigationUrl\":\"/i500004551799.htm?from=list\",\"gallery\":[{\"imageUrl\":\"https:\\/\\/static.fotocasa.es\\/images\\/ads\\/sabandenos-1.webp\"},{\"imageUrl\":\"https:\\/\\/static.fotocasa.es\\/images\\/ads\\/sabandenos-2.webp\"}]}"])
      </script>
    </head><body>
      <h1>Apartamento con ascensor en alquiler en Los Sabandeños</h1>
      <div class="description">Apartamento completo de una habitación para alquiler de larga estancia.</div>
      <strong>1.250 €</strong>
    </body></html>
    """


def test_habitaclia_accepts_explicit_room_offer_and_preserves_source_id() -> None:
    source = HabitacliaSource()
    try:
        url = "https://www.habitaclia.com/alquiler-piso-se_alquila_habitacion-la_laguna-i28898000001041.htm"
        data = source.parse_listing(room_document(), url)
        item = source.normalize_listing(data, url)
        assert item is not None
        assert item.source_name == "Habitaclia"
        assert item.external_id == "28898000001041"
        assert item.city == "La Laguna"
        assert item.price_amount == 530
        assert item.rental_mode == "long"
        assert item.room_type == "Habitación individual"
        assert item.phone is None
        assert item.email is None
    finally:
        asyncio.run(source.close())


def test_habitaclia_preserves_public_address_without_promoting_static_map_center() -> None:
    source = HabitacliaSource()
    try:
        url = "https://www.habitaclia.com/i34692000000210.htm"
        data = source.parse_listing(el_medano_location_document(), url)
        assert data["city"] == "Granadilla de Abona"
        assert data["area"] == "El Médano"
        assert data["public_address"] == "El Médano Avenida JOSE MIGUEL GALVAN BELLO"
        assert data["latitude"] is None
        assert data["longitude"] is None

        assert source.normalize_listing(data, url) is None  # Captured long rent exceeds the ceiling.
        item = source.normalize_listing({**data, "price_text": "1000 €/mes"}, url)
        assert item is not None
        assert item.city == "Granadilla de Abona"
        assert item.area == "El Médano"
        assert item.public_address == "El Médano Avenida JOSE MIGUEL GALVAN BELLO"
        assert item.latitude is None
        assert item.longitude is None

        moved = replace(item, area="Granadilla de Abona", public_address="Granadilla de Abona")
        assert moved.fingerprint != item.fingerprint
    finally:
        asyncio.run(source.close())


def test_habitaclia_extracts_images_from_detail_hydration() -> None:
    source = HabitacliaSource()
    try:
        url = "https://www.habitaclia.com/i500004551799.htm"
        data = source.parse_listing(hydration_image_document(), url)
        assert data["images"] == [
            "https://static.fotocasa.es/images/ads/sabandenos-1.webp",
            "https://static.fotocasa.es/images/ads/sabandenos-2.webp",
        ]
        assert source.normalize_listing(data, url) is None  # Captured long rent exceeds the ceiling.
        item = source.normalize_listing({**data, "price_text": "1000 €/mes"}, url)
        assert item is not None
        assert item.photos == data["images"]
        assert item.room_type == "Apartamento de 1 dormitorio"
        assert item.fingerprint != replace(item, photos=[]).fingerprint
    finally:
        asyncio.run(source.close())


def test_habitaclia_accepts_studio() -> None:
    source = HabitacliaSource()
    try:
        url = "https://www.habitaclia.com/i58067000000201.htm"
        data = source.parse_listing(studio_document(), url)
        item = source.normalize_listing(data, url)
        assert item is not None
        assert item.external_id == "58067000000201"
        assert item.city == "Puerto de la Cruz"
        assert item.price_amount == 650
        assert item.room_type == "Estudio"
    finally:
        asyncio.run(source.close())


def test_habitaclia_accepts_one_bedroom_whole_home() -> None:
    source = HabitacliaSource()
    try:
        url = "https://www.habitaclia.com/i54975000000055.htm"
        data = source.parse_listing(one_bedroom_whole_home_document(), url)
        item = source.normalize_listing(data, url)
        assert item is not None
        assert item.external_id == "54975000000055"
        assert item.room_type == "Apartamento de 1 dormitorio"
        card = (
            '"navigationUrl":"/i54975000000055.htm?from=list",'
            '"summary":{"title":"Piso de una habitación en alquiler por temporadas en Garachico",'
            '"description":"Apartamento completo de una habitación, salón, cocina y baño."}'
        )
        assert source._is_room_card(card)
        assert source._target_unit_type(card) == "Apartamento de 1 dormitorio"
    finally:
        asyncio.run(source.close())


def test_habitaclia_rejects_multi_bedroom_whole_home() -> None:
    source = HabitacliaSource()
    try:
        url = "https://www.habitaclia.com/alquiler-piso-3_habitaciones-la_laguna-i500004541315.htm"
        data = source.parse_listing(whole_home_document(), url)
        assert source.normalize_listing(data, url) is None
    finally:
        asyncio.run(source.close())


def test_habitaclia_explicit_room_wins_inside_multi_bedroom_shared_flat() -> None:
    source = HabitacliaSource()
    try:
        text = "Piso compartido de 4 habitaciones. Se alquila habitación individual para estudiante."
        assert source._room_text_is_explicit(text)
        assert source._target_unit_type(text) == "Habitación individual"
    finally:
        asyncio.run(source.close())


def test_habitaclia_extracts_modern_hydration_cards_without_cross_card_leakage() -> None:
    source = HabitacliaSource()
    try:
        page = source.discovery_urls[0]
        document = r"""
        <script>
        self.__next_f.push([1,"{\"legacyNumericId\":\"500004551704\",\"navigationUrl\":\"/i500004551704.htm?from=list\",\"summary\":{\"title\":\"ALQUILER HABITACIÓN SOLO CHICA\",\"description\":\"Se alquila habitaci\u00F3n amueblada para estudiante.\"},\"imageUrl\":\"https:\\/\\/static.fotocasa.es\\/images\\/ads\\/room.webp\"},{\"legacyNumericId\":\"500004551705\",\"navigationUrl\":\"/i500004551705.htm?from=list\",\"summary\":{\"title\":\"Estudio amueblado en Puerto de la Cruz\",\"description\":\"Estudio completo con cocina y ba\u00F1o.\"},\"imageUrl\":\"https:\\/\\/static.fotocasa.es\\/images\\/ads\\/studio.webp\"},{\"legacyNumericId\":\"500004551706\",\"navigationUrl\":\"/i500004551706.htm?from=list\",\"summary\":{\"title\":\"Piso de 1 dormitorio en Garachico\",\"description\":\"Apartamento completo con un dormitorio, sal\u00F3n, cocina y ba\u00F1o.\"},\"imageUrl\":\"https:\\/\\/static.fotocasa.es\\/images\\/ads\\/one-bed.webp\"},{\"legacyNumericId\":\"500004551707\",\"navigationUrl\":\"/i500004551707.htm?from=list\",\"summary\":{\"title\":\"Piso de 3 habitaciones en alquiler\",\"description\":\"Vivienda completa con tres habitaciones, sal\u00F3n, cocina y ba\u00F1o.\"},\"imageUrl\":\"https:\\/\\/static.fotocasa.es\\/images\\/ads\\/three-bed.webp\"}}"])
        </script>
        """
        all_urls, target_urls = source._extract_page_listings(document, page)
        room_url = "https://www.habitaclia.com/i500004551704.htm"
        studio_url = "https://www.habitaclia.com/i500004551705.htm"
        one_bed_url = "https://www.habitaclia.com/i500004551706.htm"
        whole_home_url = "https://www.habitaclia.com/i500004551707.htm"
        assert all_urls == {room_url, studio_url, one_bed_url, whole_home_url}
        assert target_urls == {room_url, studio_url, one_bed_url}
        assert source._discovered_images[room_url] == ["https://static.fotocasa.es/images/ads/room.webp"]
        assert source._discovered_images[studio_url] == ["https://static.fotocasa.es/images/ads/studio.webp"]
        assert source._discovered_images[one_bed_url] == ["https://static.fotocasa.es/images/ads/one-bed.webp"]
    finally:
        asyncio.run(source.close())


def test_habitaclia_falls_back_to_same_card_image_when_detail_has_no_gallery() -> None:
    source = HabitacliaSource()
    try:
        page = source.discovery_urls[0]
        detail_url = "https://www.habitaclia.com/i500004551706.htm"
        card = r"""
        <script>
        self.__next_f.push([1,"{\"navigationUrl\":\"/i500004551706.htm?from=list\",\"summary\":{\"title\":\"Piso de 1 dormitorio en Garachico\",\"description\":\"Apartamento completo con un dormitorio.\"},\"imageUrl\":\"https:\\/\\/static.fotocasa.es\\/images\\/ads\\/one-bed-card.webp\"}"])
        </script>
        """
        source._extract_page_listings(card, page)
        data = source.parse_listing(one_bedroom_whole_home_document(), detail_url)
        assert data["images"] == ["https://static.fotocasa.es/images/ads/one-bed-card.webp"]
        item = source.normalize_listing(data, detail_url)
        assert item is not None
        assert item.photos == data["images"]
    finally:
        asyncio.run(source.close())


def test_habitaclia_keeps_legacy_semantic_slug_fallback() -> None:
    source = HabitacliaSource()
    try:
        page = source.discovery_urls[0]
        room_url = "/alquiler-piso-se_alquila_habitacion-la_laguna-i500004551704.htm"
        studio_url = "/alquiler-estudio-puerto_de_la_cruz-i500004551705.htm"
        one_bed_url = "/alquiler-piso-1_dormitorio-garachico-i500004551706.htm"
        whole_home_url = "/alquiler-piso-con_terraza-la_laguna-i500004551707.htm"
        document = f"""
        <div data-url="{room_url}">Se alquila habitación amueblada para estudiante.</div>
        <div data-url="{studio_url}">Estudio completo.</div>
        <div data-url="{one_bed_url}">Piso de un dormitorio.</div>
        <script>window.card = {{"url":"{whole_home_url}"}}</script>
        """
        all_urls, target_urls = source._extract_page_listings(document, page)
        assert len(all_urls) == 4
        assert f"https://www.habitaclia.com{room_url}" in target_urls
        assert f"https://www.habitaclia.com{studio_url}" in target_urls
        assert f"https://www.habitaclia.com{one_bed_url}" in target_urls
        assert f"https://www.habitaclia.com{whole_home_url}" not in target_urls
    finally:
        asyncio.run(source.close())


def test_habitaclia_url_and_pagination_contract() -> None:
    source = HabitacliaSource()
    try:
        room_url = "https://www.habitaclia.com/alquiler-piso-habitacion_solo_chica-la_laguna-i500004551704.htm"
        studio_url = "https://www.habitaclia.com/alquiler-estudio-puerto_de_la_cruz-i500004551705.htm"
        one_bed_url = "https://www.habitaclia.com/alquiler-piso-1_dormitorio-garachico-i500004551706.htm"
        whole_home_url = "https://www.habitaclia.com/alquiler-piso-la_laguna-i500004551707.htm"
        modern_url = "https://www.habitaclia.com/i500004551704.htm?from=list"
        assert source.is_listing_url(room_url)
        assert source.is_listing_url(modern_url)
        assert source.is_room_candidate_url(room_url)
        assert source.is_room_candidate_url(studio_url)
        assert source.is_room_candidate_url(one_bed_url)
        assert not source.is_room_candidate_url(whole_home_url)
        assert source.is_pagination_url(
            "https://www.habitaclia.com/alquiler/viviendas/santa-cruz-de-tenerife-provincia/tenerife/s/2"
        )
        assert not source.is_pagination_url(
            "https://www.habitaclia.com/alquiler/viviendas/santa-cruz-de-tenerife-provincia/tenerife/sm/2"
        )
        assert not source.is_pagination_url("https://www.habitaclia.com/alquiler/viviendas/madrid-provincia/s/2")
    finally:
        asyncio.run(source.close())


def test_habitaclia_canary_install_is_production_only(monkeypatch) -> None:
    monkeypatch.setattr(external_sources, "configured_sources", list)
    monkeypatch.setattr(habitaclia_module, "_installed", False)
    monkeypatch.setenv("APP_ENV", "test")
    install_habitaclia_source()
    assert external_sources.configured_sources() == []

    monkeypatch.setattr(habitaclia_module, "_installed", False)
    monkeypatch.setenv("APP_ENV", "production")
    install_habitaclia_source()
    sources = external_sources.configured_sources()
    try:
        assert [source.name for source in sources] == ["Habitaclia"]
    finally:
        for source in sources:
            asyncio.run(source.close())
