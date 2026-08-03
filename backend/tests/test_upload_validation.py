from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image

from app.api.v1.uploads import validate_and_normalize
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
