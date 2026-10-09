from pathlib import Path

import pytest

from app.external_sources import parse_price
from app.services.external_scopes import SOURCE_TYPES, ScopeDefinition, validate_scope


@pytest.mark.parametrize("name", list(SOURCE_TYPES))
@pytest.mark.parametrize("price,category,accepted", [
    ("999 €/mes", "long", True), ("1.000 €/mes", "long", True),
    ("1.001 €/mes", "long", False), ("800 €", "long", False),
    ("50 €/noche", "holiday", False), ("800 €/mes", "holiday", False),
    ("desde 800 €/mes", "long", False), ("800–950 €/mes", "long", False),
    ("1000.01 €/mes", "long", False), ("800 USD/month", "long", False),
])
def test_all_registered_adapters_use_authoritative_policy(name, price, category, accepted):
    source = SOURCE_TYPES[name]()
    # Flatio additionally requires explicit InStock and MON structured evidence.
    data = {"title": "Habitación individual en alquiler", "property_type": "room",
        "description": "Residencial larga estancia", "price_text": price,
        "rental_category": category, "city": "Adeje", "province": "Santa Cruz de Tenerife", "country": "ES",
        "monthly_price_confirmed": True, "availability": "instock"}
    item = source.normalize_listing(data, f"https://www.{source.domain}/policy-fixture-123456")
    assert (item is not None) is accepted


def test_price_parsing_never_truncates_into_eligibility():
    assert parse_price("1000.01 €/mes")[0] is None
    assert parse_price("1.000,01 €/mes")[0] is None
    assert parse_price("999,99 €/mes")[0] is None
    assert parse_price("from 800 €/mes")[3]
    assert parse_price("800 €/mes USD")[1] is None


def test_legacy_holiday_scopes_fail_before_requests():
    for urls in (("https://www.pisos.com/alquiler-vacacional/pisos-malaga/",),):
        for key in ("province:Málaga:holiday", "province:Málaga"):
            with pytest.raises(ValueError, match="Holiday"):
                validate_scope(ScopeDefinition("Pisos", key, urls))


def test_source_fixtures_exist_for_every_active_provider():
    fixtures = Path(__file__).parent / "fixtures" / "external_sources"
    for name in ("fotocasa", "milanuncios", "pisocompartido", "pisos", "alquiler_docente_canarias"):
        assert (fixtures / name / "room.html").is_file()
    assert (Path(__file__).parent / "fixtures" / "spain_rental_flatio.html").is_file()


@pytest.mark.parametrize("price,amount", [
    ("999 €/mes", 999),
    ("1.000 €/mes", 1000),
    ("1 000 €/mes", 1000),
    ("1,000 €/month", 1000),
    ("1.200 €/mes", 1200),
    ("1 200 €/mes", 1200),
    ("1,200 €/month", 1200),
    ("1.000,50 €/mes", None),
    ("1,000.50 €/month", None),
    ("1000.01 €/mes", None),
    ("800 €/mes - 1200 €/mes", None),
    ("1000,999 €/mes", None),
])
def test_provider_price_cannot_drop_thousands_or_cents(price, amount):
    parsed_amount, currency, period, _uncertain = parse_price(price)
    assert parsed_amount == amount
    assert period == "month"
    if amount is not None:
        assert currency == "EUR"


@pytest.mark.parametrize("description,period,category,expected", [
    ("Se prefieren trabajadores de temporada. Alquiler de 6 a 11 meses", "month", "", True),
    ("Contrato temporal. Duración mínima del alquiler: 6 meses con prórroga", "month", "", True),
    ("Alquiler de temporada por meses", "month", "", False),
    ("Alquiler temporal de 3 a 5 meses", "month", "", False),
    ("Alquiler de 6 a 11 meses, turístico vacacional", "month", "", False),
    ("Alquiler de 6 a 11 meses", "night", "", False),
    ("Contrato de 6 meses", "month", "holiday", False),
])
def test_explicit_residential_term_is_admitted_without_tourism_or_ambiguous_seasonal_price(
    description, period, category, expected,
):
    from app.rental_classification import rental_price
    data = {"title": "Habitación individual en alquiler",
            "description": description, "rental_category": category,
            "category": "compartir vivienda alquiler habitación"}
    result = rental_price(data, "Fotocasa", 620, period)
    assert (result is not None and result.mode == "long") is expected
