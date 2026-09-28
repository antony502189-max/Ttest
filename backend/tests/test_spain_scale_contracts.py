import pytest
from pydantic import ValidationError

from app.external_sources import is_in_import_scope
from app.schemas.listings import ListingCardIdsRequest, ListingCardSearchRequest, ListingMapRequest


def test_bounded_public_contracts_reject_large_requests():
    with pytest.raises(ValidationError):
        ListingCardSearchRequest(limit=51)
    with pytest.raises(ValidationError):
        ListingCardIdsRequest(ids=["00000000-0000-0000-0000-000000000000"] * 101)
    with pytest.raises(ValidationError):
        ListingMapRequest(north=40, south=41, east=-3, west=-4, zoom=6)
    with pytest.raises(ValidationError):
        ListingMapRequest(north=41, south=40, east=-3, west=-4, zoom=1)


def test_new_province_scope_requires_structured_location():
    assert is_in_import_scope({"province": "Madrid", "country": "España"}, "province:madrid")
    assert not is_in_import_scope({"title": "Madrid room"}, "province:madrid")
    assert not is_in_import_scope({"province": "Madrid", "country": "France"}, "province:madrid")
    assert not is_in_import_scope({"province": "Madrid"}, "province:barcelona")
