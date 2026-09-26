from __future__ import annotations

MEDIA_VARIANTS = ("full", "card", "thumb")


def variant_storage_key(storage_key: str, variant: str) -> str:
    """Return the deterministic sibling key used for one responsive media variant."""
    if variant not in MEDIA_VARIANTS:
        raise ValueError(f"Unsupported media variant: {variant}")
    stem, separator, suffix = storage_key.rpartition(".")
    if not separator:
        return f"{storage_key}.{variant}.webp"
    return f"{stem}.{variant}.{suffix}"


def storage_keys_for_asset(storage_key: str) -> tuple[str, ...]:
    """Return the original object and every derived object deleted with it."""
    if storage_key.endswith(".mp4"):
        return (storage_key,)
    if any(storage_key.endswith(f".{variant}.webp") for variant in MEDIA_VARIANTS):
        return (storage_key,)
    return (storage_key, *(variant_storage_key(storage_key, variant) for variant in MEDIA_VARIANTS))
