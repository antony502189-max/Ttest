from types import SimpleNamespace

from app.schemas.listings import ListingPatch, ListingWrite
from app.services.listings import apply_write


def make_payload(**overrides):
    values = {
        "title": "Habitación privada con gastos claros",
        "city": "Adeje",
        "area": "Armeñime",
        "approximateAddress": "Armeñime · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 450,
        "roomType": "Habitación individual",
        "availableFrom": "2026-08-01",
        "availableUntil": None,
        "minimumStayMonths": 3,
        "depositAmount": 100,
        "billsIncluded": False,
        "billsText": "Gastos aparte: aprox. 45 €/mes",
        "roomSizeM2": 14,
        "roomCapacity": 1,
        "shower": "Ducha compartida",
        "amenities": ["Wi-Fi", "Lavadora"],
        "latitude": 28.1272,
        "longitude": -16.7390,
    }
    values.update(overrides)
    return ListingWrite(**values)


def test_open_ended_listing_and_bills_text_are_accepted_and_written():
    payload = make_payload()

    assert payload.availableUntil is None
    assert payload.billsText == "Gastos aparte: aprox. 45 €/mes"

    target = SimpleNamespace()
    apply_write(target, payload)

    assert target.available_until is None
    assert target.bills_included is False
    assert target.bills_text == "Gastos aparte: aprox. 45 €/mes"
    assert "Wi-Fi" in target.amenities


def test_patch_can_clear_optional_end_date_and_bills_text():
    patch = ListingPatch(availableUntil=None, billsText=None)

    assert patch.availableUntil is None
    assert patch.billsText is None
