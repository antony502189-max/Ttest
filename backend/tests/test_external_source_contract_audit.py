from __future__ import annotations

import asyncio

from app.commands.audit_external_sources import audit_source
from app.external_sources import DiscoveryResult, NormalizedListing, SourceBlocked


class HealthySource:
    name = "Healthy"
    max_discovery_pages = 30
    discovery_diagnostics: dict[str, dict] = {}

    async def discover_listing_urls(self):
        return DiscoveryResult(
            urls={"https://example.test/room/1"}, complete=True, visited_pages=1, reached_last_page=True
        )

    async def fetch_listing(self, _url):
        return "detail"

    def parse_listing(self, _document, url):
        return {
            "title": "Habitación individual en alquiler",
            "description": "Se alquila habitación en piso compartido",
            "category": "alquiler habitación",
            "breadcrumbs": "Adeje, Santa Cruz de Tenerife",
            "url": url,
            "price_text": "710 €/mes",
        }

    def normalize_listing(self, _data, url):
        return NormalizedListing(
            source_name=self.name,
            external_id="1",
            source_url=url,
            title="Habitación individual en alquiler",
            description="Se alquila habitación en piso compartido",
            city="Adeje",
            area="Adeje",
            rental_mode="long",
            source_price_text="710 €/mes",
            price_amount=710,
            price_currency="EUR",
            price_period="month",
            price_is_from=False,
        )

    async def close(self):
        return None


class BlockedSource(HealthySource):
    name = "Blocked"

    async def discover_listing_urls(self):
        raise SourceBlocked("challenge")


def test_contract_audit_checks_discovery_detail_parse_and_normalize():
    result = asyncio.run(
        audit_source(HealthySource(), max_pages=2, max_details=2, source_timeout=15, detail_timeout=5)
    )
    assert result.status == "healthy"
    assert result.discovered_urls == 1
    assert result.fetched_details == 1
    assert result.normalized_details == 1
    assert result.details[0].room_offer is True
    assert result.details[0].rental is True
    assert result.details[0].target_province is True


def test_contract_audit_isolates_a_blocked_source():
    result = asyncio.run(
        audit_source(BlockedSource(), max_pages=1, max_details=1, source_timeout=15, detail_timeout=5)
    )
    assert result.status == "blocked"
    assert result.blocked is True
    assert "SourceBlocked" in (result.error or "")


def test_global_sale_navigation_does_not_poison_room_rental_classification():
    from app.external_sources import IdealistaSource

    document = """
    <header><nav>Comprar · Pisos en venta · Alquilar</nav></header>
    <nav aria-label="Breadcrumb"><a>Tenerife</a><a>Santa Cruz de Tenerife</a></nav>
    <script type="application/ld+json">
      {"@type":"Room","name":"Habitación individual en alquiler",
       "description":"Se alquila habitación amueblada en piso compartido.",
       "address":{"addressLocality":"Santa Cruz de Tenerife","addressRegion":"Santa Cruz de Tenerife"}}
    </script>
    <p>710 €/mes</p>
    """
    source = IdealistaSource()
    url = "https://www.idealista.com/inmueble/123456/"
    parsed = source.parse_listing(document, url)
    assert "Comprar" not in parsed["category"]
    assert "Pisos en venta" not in parsed["breadcrumbs"]
    assert source.normalize_listing(parsed, url) is not None


def test_pisocompartido_page_chrome_does_not_reject_a_valid_detail_page():
    from app.external_sources import PisoCompartidoSource

    document = """
    <header><a>Pisos en venta</a><a>Comprar</a></header>
    <ol class="breadcrumbs"><li>Tenerife</li><li>Arona</li></ol>
    <h1>Habitación individual en alquiler en Arona</h1>
    <section class="descripcion">Se alquila habitación amueblada en piso compartido.</section>
    <p>Precio: 550 € al mes</p>
    """
    source = PisoCompartidoSource()
    url = "https://www.pisocompartido.com/habitacion/1009160/"
    parsed = source.parse_listing(document, url)
    normalized = source.normalize_listing(parsed, url)
    assert normalized is not None
    assert normalized.city == "Arona"
    assert normalized.price_amount == 550


def test_actual_sale_detail_remains_rejected():
    from app.external_sources import IdealistaSource

    document = """
    <nav class="breadcrumb">Santa Cruz de Tenerife</nav>
    <script type="application/ld+json">
      {"@type":"Room","name":"Habitación en venta",
       "description":"Se vende habitación en Santa Cruz de Tenerife."}
    </script>
    <p>75.000 €</p>
    """
    source = IdealistaSource()
    url = "https://www.idealista.com/inmueble/123457/"
    assert source.normalize_listing(source.parse_listing(document, url), url) is None


def test_idealista_style_html_pagination_is_discovered():
    from app.external_sources import IdealistaSource

    source = IdealistaSource()
    assert source.is_pagination_url(
        "https://www.idealista.com/alquiler-habitacion/santa-cruz-de-tenerife-provincia/pagina-2.htm"
    )


def test_detail_shell_uses_anonymous_browser_fallback(monkeypatch):
    from app.external_sources import FotocasaSource

    class Source(FotocasaSource):
        def __init__(self):
            self.rendered = False

        async def request(self, _url):
            return '<html><head><title>Fotocasa</title></head><body><div id="root"></div></body></html>'

        async def render_public_page(self, _url):
            self.rendered = True
            return '<h1>Habitación en Arona</h1><p>Se alquila habitación</p><strong>650 €/mes</strong>'

    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.external_sources.get_settings",
        lambda: SimpleNamespace(external_import_playwright_enabled=True),
    )
    source = Source()
    document = asyncio.run(source.fetch_listing("https://www.fotocasa.es/es/compartir/vivienda/arona/x/123456789/d"))
    assert source.rendered is True
    assert "650 €/mes" in (document or "")


def test_fotocasa_reads_the_nested_listing_object_itself():
    from app.external_sources import FotocasaSource

    document = '''
    <script id="__NEXT_DATA__" type="application/json">
      {"props":{"pageProps":{"property":{
        "title":"Habitación en Arona",
        "description":"Se alquila habitación amueblada en Santa Cruz de Tenerife",
        "priceText":"650 €/mes",
        "municipality":"Arona"
      }}}}
    </script>
    '''
    source = FotocasaSource()
    url = "https://www.fotocasa.es/es/compartir/vivienda/arona/amueblado/123456789/d"
    parsed = source.parse_listing(document, url)
    normalized = source.normalize_listing(parsed, url)
    assert parsed["title"] == "Habitación en Arona"
    assert parsed["price_text"] == "650 €/mes"
    assert normalized is not None
    assert normalized.city == "Arona"
    assert normalized.price_amount == 650
