import pytest
from pydantic import ValidationError

from app.schemas.listings import ListingSearchRequest


def test_search_offset_accepts_the_documented_maximum() -> None:
    assert ListingSearchRequest(offset=10_000).offset == 10_000


def test_search_offset_rejects_unbounded_database_scans() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 10000"):
        ListingSearchRequest(offset=10_001)
