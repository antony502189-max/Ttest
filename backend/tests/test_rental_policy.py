from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.listings import ListingPatch, ListingWrite
from app.services.rental_policy import evaluate, require_eligible


@pytest.mark.parametrize("amount,accepted", [(999, True), (1000, True), (1001, False),
    (0, False), (-1, False), (None, False), ("NaN", False), ("Infinity", False), ("1000.01", False)])
def test_exact_monthly_boundary(amount, accepted):
    assert evaluate(mode="long", amount=amount).eligible is accepted


@pytest.mark.parametrize("extra", [{"mode": "holiday"}, {"currency": None}, {"currency": "USD"},
    {"period": None}, {"period": "night"}, {"period": "week"}, {"is_from": True}, {"is_from": None}])
def test_uncertain_or_unsupported_offer(extra):
    assert not evaluate(**({"mode": "long", "amount": 800} | extra)).eligible


def test_mandatory_fees_and_deposit_semantics():
    assert evaluate(mode="long", amount=750, mandatory_monthly_fees=250).eligible
    assert not evaluate(mode="long", amount=750, mandatory_monthly_fees=251).eligible
    assert not evaluate(mode="long", amount=950, bills_text="Gastos adicionales: 100 €/mes").eligible
    assert evaluate(mode="long", amount=1000, bills_text="Gastos según consumo").eligible
    assert evaluate(mode="long", amount=1000, bills_included=True, bills_text="Incluidos 100 €/mes").eligible


def test_effective_patch_and_legacy_restore():
    listing = SimpleNamespace(rental_mode="long", monthly_price=1200, is_external=False)
    with pytest.raises(HTTPException):
        require_eligible(listing, {"title": "New title"})
    require_eligible(listing, {"monthlyPrice": 1000})
    with pytest.raises(HTTPException):
        require_eligible(listing, {"status": "published"})
    with pytest.raises(HTTPException):
        require_eligible(listing, {"monthlyPrice": None})


@pytest.mark.parametrize("payload", [{"monthlyPrice": 1001}, {"monthlyPrice": 0},
    {"rentalMode": "holiday"}, {"nightlyPrice": 50}, {"weeklyPrice": 350}])
def test_patch_contract(payload):
    with pytest.raises(ValidationError):
        ListingPatch(**payload)


def test_manual_contract_at_limit_with_large_deposit():
    valid = {"title": "Habitación residencial", "city": "Adeje", "area": "Centro",
        "approximateAddress": "Adeje centro", "rentalMode": "long", "monthlyPrice": 1000,
        "depositAmount": 1500, "latitude": 28.1, "longitude": -16.7}
    assert ListingWrite(**valid).monthlyPrice == 1000
    for extra in ({"monthlyPrice": 1001}, {"rentalMode": "holiday", "nightlyPrice": 50},
                  {"monthlyPrice": None}, {"billsText": "100 EUR extra monthly"}):
        with pytest.raises(ValidationError):
            ListingWrite(**(valid | extra))
