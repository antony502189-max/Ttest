import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest, UserUpdateRequest
from app.schemas.listings import ListingPatch, ListingSearchRequest, ListingWrite


def valid_listing() -> dict:
    return {
        "title": "Valid listing title",
        "city": "Santa Cruz de Tenerife",
        "area": "Centro",
        "approximateAddress": "Centro · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 700,
        "roomType": "Habitación individual",
        "latitude": 28.46,
        "longitude": -16.25,
    }


def test_registration_strips_whitespace_and_limits_roles():
    parsed = RegisterRequest(name="  Host Person  ", email="host@example.com", password="Correct-Horse-1234", role="host")
    assert parsed.name == "Host Person"
    with pytest.raises(ValidationError):
        RegisterRequest(name="Host Person", email="host@example.com", password="Correct-Horse-1234", role="admin")


def test_profile_patch_rejects_explicit_null_and_blank_name():
    with pytest.raises(ValidationError):
        UserUpdateRequest(name=None)
    with pytest.raises(ValidationError):
        UserUpdateRequest(name="   ")


def test_listing_write_rejects_blank_text_and_unknown_room_type():
    blank = valid_listing() | {"title": "   "}
    with pytest.raises(ValidationError):
        ListingWrite(**blank)
    unsupported = valid_listing() | {"roomType": "Palacio"}
    with pytest.raises(ValidationError):
        ListingWrite(**unsupported)


def test_listing_patch_rejects_null_required_fields_and_invalid_status():
    with pytest.raises(ValidationError):
        ListingPatch(title=None)
    with pytest.raises(ValidationError):
        ListingPatch(status="arbitrary")


def test_listing_patch_can_clear_exact_location_only_as_a_pair():
    cleared = ListingPatch(exactLatitude=None, exactLongitude=None)
    assert cleared.model_fields_set == {"exactLatitude", "exactLongitude"}
    with pytest.raises(ValidationError):
        ListingPatch(exactLatitude=None)


def test_listing_search_validates_date_range_deposit_and_duplicates():
    with pytest.raises(ValidationError):
        ListingSearchRequest(availableFrom="2026-08-10", availableUntil="2026-08-01")
    with pytest.raises(ValidationError):
        ListingSearchRequest(deposit="unknown")
    with pytest.raises(ValidationError):
        ListingSearchRequest(roomTypes=["Estudio", "Estudio"])
