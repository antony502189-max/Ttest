from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image

from app.api.v1.uploads import media_quota_exceeded, validate_and_normalize
from app.core.config import Settings


def png_bytes(width: int = 12, height: int = 8) -> bytes:
    image = Image.new("RGBA", (width, height), (20, 40, 60, 128))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_valid_png_is_normalized_to_webp():
    normalized, width, height = validate_and_normalize(png_bytes())

    assert (width, height) == (12, 8)
    with Image.open(BytesIO(normalized)) as image:
        assert image.format == "WEBP"


def test_invalid_image_is_rejected():
    with pytest.raises(HTTPException) as error:
        validate_and_normalize(b"<svg><script>alert(1)</script></svg>")

    assert error.value.status_code == 415


def test_corrupt_image_stream_is_rejected():
    with pytest.raises(HTTPException) as error:
        validate_and_normalize(b"\x89PNG\r\n\x1a\nbroken-image-data")

    assert error.value.status_code == 415


def test_image_above_pixel_budget_is_rejected(monkeypatch):
    settings = Settings(max_image_pixels=100, max_image_dimension=1_000)
    monkeypatch.setattr("app.api.v1.uploads.get_settings", lambda: settings)

    with pytest.raises(HTTPException) as error:
        validate_and_normalize(png_bytes(11, 10))

    assert error.value.status_code == 422


def test_media_quota_rejects_asset_count_boundary():
    settings = Settings(
        max_upload_bytes=10,
        max_media_assets_per_user=2,
        max_media_bytes_per_user=100,
    )

    assert media_quota_exceeded(
        active_assets=2,
        active_bytes=20,
        new_bytes=5,
        settings=settings,
    )


def test_media_quota_rejects_byte_overflow_but_accepts_exact_boundary():
    settings = Settings(
        max_upload_bytes=10,
        max_media_assets_per_user=10,
        max_media_bytes_per_user=100,
    )

    assert media_quota_exceeded(
        active_assets=1,
        active_bytes=95,
        new_bytes=6,
        settings=settings,
    )
    assert not media_quota_exceeded(
        active_assets=1,
        active_bytes=90,
        new_bytes=10,
        settings=settings,
    )
