from __future__ import annotations

import asyncio

from app import external_sources
from app.habitaclia_source import HabitacliaSource, install_habitaclia_source
import app.habitaclia_source as habitaclia_module


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


def test_habitaclia_rejects_whole_home_bedroom_count() -> None:
    source = HabitacliaSource()
    try:
        url = "https://www.habitaclia.com/alquiler-piso-3_habitaciones-la_laguna-i500004541315.htm"
        data = source.parse_listing(whole_home_document(), url)
        assert source.normalize_listing(data, url) is None
    finally:
        asyncio.run(source.close())


def test_habitaclia_url_and_pagination_contract() -> None:
    source = HabitacliaSource()
    try:
        room_url = "https://www.habitaclia.com/alquiler-piso-habitacion_solo_chica-la_laguna-i500004551704.htm"
        whole_home_url = "https://www.habitaclia.com/alquiler-piso-la_laguna-i500004551705.htm"
        assert source.is_listing_url(room_url)
        assert source.is_room_candidate_url(room_url)
        assert not source.is_room_candidate_url(whole_home_url)
        assert source.is_pagination_url(
            "https://www.habitaclia.com/alquiler/viviendas/santa-cruz-de-tenerife-provincia/tenerife/s/2"
        )
        assert not source.is_pagination_url(
            "https://www.habitaclia.com/alquiler/viviendas/madrid-provincia/s/2"
        )
    finally:
        asyncio.run(source.close())


def test_habitaclia_canary_install_is_production_only(monkeypatch) -> None:
    monkeypatch.setattr(external_sources, "configured_sources", lambda: [])
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
