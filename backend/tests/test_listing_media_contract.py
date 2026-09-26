from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.uploads import VIDEO_READ_CHUNK_BYTES, parse_video_range
from app.services.listings import validate_listing_photo_count


@pytest.mark.parametrize("count,accepted", [(4, False), (5, True), (15, True), (16, False)])
def test_owner_listing_photo_boundaries(count: int, accepted: bool):
    assets = [uuid4() for _ in range(count)]
    if accepted:
        validate_listing_photo_count(assets)
    else:
        with pytest.raises(HTTPException) as error:
            validate_listing_photo_count(assets)
        assert error.value.status_code == 422
        assert error.value.detail["fieldErrors"]["assetIds"]


@pytest.mark.parametrize(
    "header,size,expected",
    [
        ("bytes=2-5", 10, (2, 5)),
        ("bytes=-3", 10, (7, 9)),
        ("bytes=5-", 10, (5, 9)),
        (f"bytes=0-{VIDEO_READ_CHUNK_BYTES * 2}", VIDEO_READ_CHUNK_BYTES * 3, (0, VIDEO_READ_CHUNK_BYTES - 1)),
    ],
)
def test_video_range_bounds_storage_read(header: str, size: int, expected: tuple[int, int]):
    assert parse_video_range(header, size) == expected


@pytest.mark.parametrize("header", ["bytes=10-", "bytes=-0", "bytes=5-2", "bytes=a-b", "bytes=0-1,3-4", "items=0-1"])
def test_invalid_video_ranges_are_rejected(header: str):
    with pytest.raises(ValueError):
        parse_video_range(header, 10)
