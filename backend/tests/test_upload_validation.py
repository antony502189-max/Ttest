from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image

from app.api.v1.uploads import media_quota_exceeded, validate_and_normalize
from app.core.config import Settings
from app.services.media_processing import prepare_image, render_variant


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
    monkeypatch.setattr("app.services.media_processing.get_settings", lambda: settings)

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



def test_large_image_is_resized_and_gets_responsive_variants(monkeypatch):
    settings = Settings(
        max_image_pixels=2_000_000,
        max_image_dimension=2_000,
        media_full_max_dimension=1_000,
        media_card_max_dimension=600,
        media_thumb_max_dimension=300,
    )
    monkeypatch.setattr("app.services.media_processing.get_settings", lambda: settings)

    prepared = prepare_image(png_bytes(1_200, 600))

    assert (prepared.width, prepared.height) == (1_000, 500)
    with Image.open(BytesIO(prepared.content)) as image:
        assert image.size == (1_000, 500)
    with Image.open(BytesIO(prepared.variants["card"])) as image:
        assert image.size == (600, 300)
    with Image.open(BytesIO(prepared.variants["thumb"])) as image:
        assert image.size == (300, 150)
    assert len(prepared.perceptual_hash) == 16


def test_legacy_variant_is_generated_only_when_smaller(monkeypatch):
    settings = Settings(
        media_full_max_dimension=1_000,
        media_card_max_dimension=600,
        media_thumb_max_dimension=300,
    )
    monkeypatch.setattr("app.services.media_processing.get_settings", lambda: settings)
    source = validate_and_normalize(png_bytes(800, 400))[0]

    card = render_variant(source, "card")
    assert card is not None
    with Image.open(BytesIO(card)) as image:
        assert image.size == (600, 300)

    already_small = validate_and_normalize(png_bytes(200, 100))[0]
    assert render_variant(already_small, "thumb") is None
