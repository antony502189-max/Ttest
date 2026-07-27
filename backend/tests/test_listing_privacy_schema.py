import pytest
from pydantic import ValidationError

from app.api.v1.listings import anonymous_viewer_key
from app.schemas.listings import ListingResponse, ListingSearchRequest, ListingWrite, OwnedListingResponse


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


def test_search_polygon_is_closed_for_postgis():
    search = ListingSearchRequest(polygon=[
        {"latitude": 28.0, "longitude": -16.8},
        {"latitude": 28.1, "longitude": -16.8},
        {"latitude": 28.1, "longitude": -16.7},
    ])

    assert len(search.polygon) == 4
    assert search.polygon[0] == search.polygon[-1]


def test_anonymous_viewer_key_is_stable_but_does_not_reveal_the_cookie():
    key = anonymous_viewer_key("private-browser-token")

    assert key == anonymous_viewer_key("private-browser-token")
    assert key != "private-browser-token"
    assert len(key) == 64
