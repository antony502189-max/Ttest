import pytest
from pydantic import ValidationError

from app.schemas.listings import ListingResponse, ListingWrite, OwnedListingResponse


def listing_payload() -> dict:
    return {
        "title": "Habitación luminosa",
        "city": "Adeje",
        "area": "Costa Adeje",
        "approximateAddress": "Costa Adeje",
        "rentalMode": "long",
        "monthlyPrice": 750,
        "latitude": 28.087,
        "longitude": -16.732,
    }


def test_exact_coordinates_must_be_supplied_as_a_pair():
    with pytest.raises(ValidationError, match="exactLatitude and exactLongitude"):
        ListingWrite(**listing_payload(), exactLatitude=28.088)


def test_exact_coordinates_are_optional_and_valid_as_a_pair():
    listing = ListingWrite(**listing_payload(), exactLatitude=28.088, exactLongitude=-16.733)

    assert listing.exactLatitude == 28.088
    assert listing.exactLongitude == -16.733


def test_public_listing_dto_cannot_expose_exact_location_fields():
    assert "exactLatitude" not in ListingResponse.model_fields
    assert "exactLongitude" not in ListingResponse.model_fields
    assert {"street", "postcode", "exactLatitude", "exactLongitude"}.issubset(OwnedListingResponse.model_fields)
