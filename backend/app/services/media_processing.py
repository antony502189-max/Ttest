from __future__ import annotations

import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from typing import cast

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from ..core.config import get_settings

SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MEDIA_VARIANTS = ("card", "thumb")


@dataclass(frozen=True)
class PreparedImage:
    content: bytes
    width: int
    height: int
    variants: dict[str, bytes]
    perceptual_hash: str


def _validated_image(content: bytes) -> Image.Image:
    settings = get_settings()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as probe:
                if probe.format not in SUPPORTED_IMAGE_FORMATS:
                    raise HTTPException(415, "Only JPEG, PNG and WebP images are supported")
                width, height = probe.size
                if (
                    width < 1
                    or height < 1
                    or width > settings.max_image_dimension
                    or height > settings.max_image_dimension
                    or width * height > settings.max_image_pixels
                ):
                    raise HTTPException(422, "Image dimensions are not allowed")
                probe.verify()

            with Image.open(BytesIO(content)) as source:
                source.load()
                transposed = ImageOps.exif_transpose(source)
                return transposed.convert("RGBA" if "A" in transposed.getbands() else "RGB")
    except Image.DecompressionBombWarning as exc:
        raise HTTPException(422, "Image dimensions are not allowed") from exc
    except Image.DecompressionBombError as exc:
        raise HTTPException(422, "Image dimensions are not allowed") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(415, "Invalid image file") from exc


def _resize_to_fit(image: Image.Image, max_dimension: int) -> Image.Image:
    resized = image.copy()
    if max(resized.size) > max_dimension:
        resized.thumbnail(
            (max_dimension, max_dimension),
            Image.Resampling.LANCZOS,
            reducing_gap=3.0,
        )
    return resized


def _webp(image: Image.Image, *, quality: int) -> bytes:
    output = BytesIO()
    image.save(output, format="WEBP", method=4, quality=quality)
    return output.getvalue()


def perceptual_hash(content: bytes) -> str:
    """Stable average hash used later for conservative photo similarity checks."""
    with Image.open(BytesIO(content)) as image:
        pixels = list(
            cast(
                "Iterable[int]",
                image.convert("L").resize((8, 8), Image.Resampling.LANCZOS).get_flattened_data(),
            )
        )
    average = sum(pixels) / len(pixels)
    return f"{sum((1 << index) for index, value in enumerate(pixels) if value >= average):016x}"


def _variant_target(variant: str) -> tuple[int, int]:
    settings = get_settings()
    if variant == "full":
        return settings.media_full_max_dimension, settings.media_full_webp_quality
    if variant == "card":
        return settings.media_card_max_dimension, settings.media_card_webp_quality
    if variant == "thumb":
        return settings.media_thumb_max_dimension, settings.media_thumb_webp_quality
    raise ValueError(f"Unsupported media variant: {variant}")


def prepare_image(content: bytes) -> PreparedImage:
    """Validate once, resize once and encode browser-oriented versions in one CPU job."""
    settings = get_settings()
    source = _validated_image(content)
    full = _resize_to_fit(source, settings.media_full_max_dimension)
    full_content = _webp(full, quality=settings.media_full_webp_quality)
    width, height = full.size

    variants: dict[str, bytes] = {}
    for variant in MEDIA_VARIANTS:
        target, quality = _variant_target(variant)
        if max(width, height) <= target:
            continue
        variants[variant] = _webp(_resize_to_fit(full, target), quality=quality)

    return PreparedImage(
        content=full_content,
        width=width,
        height=height,
        variants=variants,
        perceptual_hash=perceptual_hash(full_content),
    )


def validate_and_normalize(content: bytes) -> tuple[bytes, int, int]:
    """Validate and normalize only the full image without derivative work."""
    settings = get_settings()
    source = _validated_image(content)
    full = _resize_to_fit(source, settings.media_full_max_dimension)
    return _webp(full, quality=settings.media_full_webp_quality), *full.size


def render_variant(content: bytes, variant: str) -> bytes | None:
    """Build a responsive derivative for a legacy asset.

    None means the original is already at or below the requested dimensions.
    """
    target, quality = _variant_target(variant)
    try:
        with Image.open(BytesIO(content)) as source:
            source.load()
            if max(source.size) <= target:
                return None
            normalized = source.convert("RGBA" if "A" in source.getbands() else "RGB")
            return _webp(_resize_to_fit(normalized, target), quality=quality)
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(415, "Invalid stored image") from exc
