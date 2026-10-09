from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_room_first_listing_schemas import base_payload

from app.external_sources import IdealistaSource, PisosSource, parse_price
from app.schemas.listings import ListingWrite
from app.services.external_import import upsert
from app.services.rental_price_limit import (
    exact_euro_amount,
    imported_price_allowed,
    long_term_price_allowed,
    require_listing_price,
)


@pytest.mark.parametrize("amount,allowed", [(999, True), (1000, True), (1001, False), (1000.5, False), (None, False)])
def test_long_term_inclusive_ceiling(amount, allowed):
    assert long_term_price_allowed("long", amount) is allowed


def test_write_and_merged_patch_apply_limit_only_to_long_term():
    payload = base_payload()
    assert ListingWrite.model_validate(payload | {"monthlyPrice": 1000}).monthlyPrice == 1000
    with pytest.raises(ValidationError):
        ListingWrite.model_validate(payload | {"monthlyPrice": 1001})
    holiday = ListingWrite.model_validate(
        payload
        | {
            "rentalMode": "holiday",
            "monthlyPrice": 5000,
            "nightlyPrice": 2000,
            "weeklyPrice": 7000,
        }
    )
    assert holiday.nightlyPrice == 2000 and holiday.weeklyPrice == 7000 and holiday.monthlyPrice == 5000
    listing = SimpleNamespace(rental_mode="holiday", monthly_price=5000)
    require_listing_price(listing, {"nightlyPrice": 3000})
    with pytest.raises(HTTPException) as error:
        require_listing_price(listing, {"rentalMode": "long"})
    assert error.value.status_code == 422
    require_listing_price(listing, {"rentalMode": "long", "monthlyPrice": 1000})


@pytest.mark.parametrize("text", ["1001 €/mes", "1.000,50 €/mes", "1000.50 €/mes"])
async def test_importer_rejects_long_prices_without_truncating_cents(text):
    source = IdealistaSource()
    try:
        data = {
            "title": "Habitación individual en alquiler",
            "description": "Piso compartido para alquilar",
            "category": "alquiler habitación",
            "city": "Adeje",
            "breadcrumbs": "Santa Cruz de Tenerife",
            "price_text": text,
        }
        assert source.normalize_listing(data, "https://www.idealista.com/inmueble/123456/") is None
        assert not imported_price_allowed(
            SimpleNamespace(rental_mode="long", price_amount=1000, source_price_text=text)
        )
    finally:
        await source.close()


async def test_holiday_importer_preserves_high_prices():
    source = PisosSource()
    try:
        source.scope_key = "province:Madrid:holiday"
        data = {
            "title": "Apartamento",
            "description": "Alquiler vacacional",
            "property_type": "apartment",
            "bedroom_count": 1,
            "rental_category": "holiday",
            "price_text": "2000 €/noche",
            "city": "Madrid",
            "province": "Madrid",
            "country": "ES",
        }
        item = source.normalize_listing(data, "https://www.pisos.com/alquiler-vacacional/piso-madrid-123456/")
        assert item and item.rental_mode == "holiday" and item.price_amount == 2000
        assert imported_price_allowed(item)
    finally:
        await source.close()


async def test_upsert_rejects_over_limit_before_network_or_insert():
    session = SimpleNamespace(scalar=AsyncMock(return_value=None), commit=AsyncMock(), add=AsyncMock())
    item = SimpleNamespace(
        source_name="Idealista",
        external_id="cap-test",
        source_url="https://example.test/1",
        room_capacity=1,
        rental_mode="long",
        price_amount=1001,
        source_price_text="1001 €/mes",
    )
    assert await upsert(session, item) == "rejected_invalid_price"
    session.add.assert_not_called()
    session.commit.assert_awaited_once()


@pytest.mark.parametrize("text,expected", [
    ("999 €/mes", 999),
    ("1.000 €/mes", 1000),
    ("1 000 €/mes", 1000),
    ("1,000 €/month", 1000),
    ("1000.01 €/mes", 1000.01),
    ("1.000,50 €/mes", 1000.50),
    ("1,000.50 €/month", 1000.50),
    ("1 200 €/mes", 1200),
    ("1.200 €/mes", 1200),
    ("1,200 €/month", 1200),
    ("1000,999 €/mes", None),
    ("800 €/mes - 1500 €/mes", None),
    ("sin precio", None),
])
def test_exact_euro_price_parsing_never_drops_thousands_or_cents(text, expected):
    value = exact_euro_amount(text)
    assert (float(value) if value is not None else None) == expected


@pytest.mark.parametrize("text", [
    "1 200 €/mes", "1,200 €/month", "1.200 €/mes",
    "1000.01 €/mes", "1.000,50 €/mes", "1,000.50 €/month",
    "1000,999 €/mes", "800 €/mes - 1500 €/mes",
])
def test_ambiguous_or_expensive_imports_fail_closed_even_after_legacy_integer_parse(text):
    assert not imported_price_allowed(
        SimpleNamespace(rental_mode="long", price_amount=800, source_price_text=text)
    )


def test_missing_raw_advertised_price_cannot_bypass_import_guard():
    assert not imported_price_allowed(SimpleNamespace(
        rental_mode="long", price_amount=750, source_price_text=""
    ))


@pytest.mark.parametrize("text,price", [
    ("1 200 €/mes", 1200),
    ("1.200 €/mes", 1200),
    ("1,200 €/month", 1200),
    ("1.000 €/mes", 1000),
    ("1 000 €/mes", 1000),
    ("1000,99 €/mes", 1000),
    ("800 €/mes - 1200 €/mes", None),
])
def test_provider_parser_and_price_guard_share_unambiguous_amount(text, price):
    parsed_amount, currency, cadence, _ = parse_price(text)
    assert parsed_amount == price
    assert cadence == "month"
    assert currency == ("EUR" if price is not None else None)


@pytest.mark.parametrize("text", ["Desde 750 €/mes", "desde 999 €/month"])
async def test_importer_rejects_long_term_minimum_price_not_fixed_rent(text):
    source = IdealistaSource()
    try:
        item = {
            "title": "Habitación individual en alquiler",
            "description": "Piso compartido amueblado",
            "category": "alquiler habitación",
            "city": "Adeje",
            "breadcrumbs": "Santa Cruz de Tenerife",
            "price_text": text,
        }
        assert source.normalize_listing(item, "https://www.idealista.com/inmueble/900012/") is None
        assert not imported_price_allowed(SimpleNamespace(
            rental_mode="long", price_amount=750,
            source_price_text=text, price_is_from=True,
        ))
    finally:
        await source.close()
