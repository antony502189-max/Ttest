import pytest
from pydantic import ValidationError

from app.schemas.listings import ListingSearchRequest
from app.services.listings import ROOM_DETAIL_MAPPING


def test_floor_filter_contract_is_structured_and_validated():
    assert ListingSearchRequest(floor="basement").floor == "basement"
    assert ListingSearchRequest(floor="top").floor == "top"
    assert ListingSearchRequest(floor="4+").floor == "4+"
    assert ROOM_DETAIL_MAPPING["floor"] == "floor"

    with pytest.raises(ValidationError):
        ListingSearchRequest(floor="between floors")
