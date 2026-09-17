from __future__ import annotations

import asyncio

import app.habitaclia_source as habitaclia_module
from app import external_sources
from app.habitaclia_source import HabitacliaSource, install_habitaclia_source


def room_document() -> str:
    return """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@type": "Apartment",
          "name": "Alquiler piso. Se alquila habitación en La Laguna",
          "description": "Se alquila habitación amueblada para una persona, disponible para larga estancia.",
          "address": {
            "addressLocality": "La Laguna",
            "addressRegion": "Santa Cruz de Tenerife"
          },
          "image": ["https://images.habimg.com/example-room.jpg"]
        }
        </script>
      </head>
      <body>
        <h1>Alquiler piso. Se alquila habitación en La Laguna</h1>
        <div class="description">Se alquila habitación amueblada para una persona, disponible para larga estancia.</div>
        <strong>530 €</strong>
      </body>
    </html>
    """


def whole_home_document() -> str:
    return """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@type": "Apartment",
          "name": "Piso de 3 habitaciones en alquiler en La Laguna",
          "description": "Vivienda completa con tres habitaciones, salón, cocina y baño.",
          "address": {
            "addressLocality": "La Laguna",
            "addressRegion": "Santa Cruz de Tenerife"
          }
        }
        </script>
      </head>
      <body>
        <h1>Piso de 3 habitaciones en alquiler en La Laguna</h1>
        <div class="description">Vivienda completa con tres habitaciones, salón, cocina y baño.</div>
        <strong>1.200 €</strong>
      </body>
    </html>
    """


def one_bedroom_whole_home_document() -> str:
    return """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@type": "Apartment",
          "name": "Alquiler piso de un habitación en alquiler por temporadas en Garachico",
          "description": "Apartamento completo de una habitación, salón, cocina y baño para alquiler por temporadas.",
          "address": {
            "addressLocality": "Garachico",
            "addressRegion": "Santa Cruz de Tenerife"
          }
        }
        </script>
      </head>
      <body>
        <h1>Alquiler piso de un habitación en alquiler por temporadas en Garachico</h1>
        <div class="description">Apartamento completo de una habitación, salón, cocina y baño.</div>
        <strong>780 €</strong>
      </body>
    </html>
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
        assert item.phone is None
        assert item.email is None
    finally:
        asyncio.run(source.close())


def test_habitaclia_modern_id_route_preserves_source_id() -> None:
    source = HabitacliaSource()
    try:
        url = "https://www.habitaclia.com/i28898000001041.htm"
        assert source.is_listing_url(url)
        data = source.parse_listing(room_document(), url)
        item = source.normalize_listing(data, url)
        assert item is not None
        assert item.external_id == "28898000001041"
    finally:
        asyncio.run(source.close())


def test_habitaclia_rejects_whole_home_bedroom_count() -> None:
    source = HabitacliaSource()
    try:
        url = "https://www.habitaclia.com/alquiler-piso-3_habitaciones-la_laguna-i500004541315.htm"
        data = source.parse_listing(whole_home_document(), url)
        assert source.normalize_listing(data, url) is None
    finally:
        asyncio.run(source.close())


def test_habitaclia_rejects_one_bedroom_whole_home_with_weak_room_phrase() -> None:
    source = HabitacliaSource()
    try:
        url = "https://www.habitaclia.com/i54975000000055.htm"
        data = source.parse_listing(one_bedroom_whole_home_document(), url)
        assert source.normalize_listing(data, url) is None
        assert not source._is_room_card(
            '"navigationUrl":"/i54975000000055.htm?from=list",'
            '"summary":{"title":"Alquiler piso de un habitación en alquiler por temporadas en Garachico",'
            '"description":"Apartamento completo de una habitación, salón, cocina y baño."}'
        )
    finally:
        asyncio.run(source.close())


def test_habitaclia_extracts_modern_hydration_cards_without_cross_card_leakage() -> None:
    source = HabitacliaSource()
    try:
        page = source.discovery_urls[0]
        document = r'''
        <script>
        self.__next_f.push([1,"{\"legacyNumericId\":\"500004551704\",\"kind\":\"secondHand\",\"navigationUrl\":\"/i500004551704.htm?from=list\",\"summary\":{\"title\":\"ALQUILER HABITACIÓN SOLO CHICA\",\"description\":\"Se alquila habitaci\u00F3n amueblada para estudiante.\"}},{\"legacyNumericId\":\"500004551705\",\"kind\":\"secondHand\",\"navigationUrl\":\"/i500004551705.htm?from=list\",\"summary\":{\"title\":\"Piso de 3 habitaciones en alquiler\",\"description\":\"Vivienda completa con tres habitaciones, sal\u00F3n, cocina y ba\u00F1o.\"}}"])
        </script>
        '''
        all_urls, room_urls = source._extract_page_listings(document, page)
        room_url = "https://www.habitaclia.com/i500004551704.htm"
        whole_home_url = "https://www.habitaclia.com/i500004551705.htm"
        assert all_urls == {room_url, whole_home_url}
        assert room_urls == {room_url}
    finally:
        asyncio.run(source.close())


def test_habitaclia_keeps_legacy_semantic_slug_fallback() -> None:
    source = HabitacliaSource()
    try:
        page = source.discovery_urls[0]
        room_url = "/alquiler-piso-se_alquila_habitacion-la_laguna-i500004551704.htm"
        whole_home_url = "/alquiler-piso-con_terraza-la_laguna-i500004551705.htm"
        document = f"""
        <div data-url="{room_url}">Se alquila habitación amueblada para estudiante.</div>
        <script>window.card = {{"url":"{whole_home_url}"}}</script>
        """
        all_urls, room_urls = source._extract_page_listings(document, page)
        assert len(all_urls) == 2
        assert f"https://www.habitaclia.com{room_url}" in room_urls
        assert f"https://www.habitaclia.com{whole_home_url}" not in room_urls
    finally:
        asyncio.run(source.close())


def test_habitaclia_url_and_pagination_contract() -> None:
    source = HabitacliaSource()
    try:
        room_url = "https://www.habitaclia.com/alquiler-piso-habitacion_solo_chica-la_laguna-i500004551704.htm"
        whole_home_url = "https://www.habitaclia.com/alquiler-piso-la_laguna-i500004551705.htm"
        modern_url = "https://www.habitaclia.com/i500004551704.htm?from=list"
        assert source.is_listing_url(room_url)
        assert source.is_listing_url(modern_url)
        assert source.is_room_candidate_url(room_url)
        assert not source.is_room_candidate_url(whole_home_url)
        assert source.is_pagination_url(
            "https://www.habitaclia.com/alquiler/viviendas/santa-cruz-de-tenerife-provincia/tenerife/s/2"
        )
        assert not source.is_pagination_url(
            "https://www.habitaclia.com/alquiler/viviendas/santa-cruz-de-tenerife-provincia/tenerife/sm/2"
        )
        assert not source.is_pagination_url(
            "https://www.habitaclia.com/alquiler/viviendas/madrid-provincia/s/2"
        )
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
