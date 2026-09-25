from hashlib import sha256
from uuid import uuid4

from app.services.listing_deduplication import ImageFingerprint, galleries_are_duplicates, hamming_distance


def image(index: int, *, checksum: str | None = None, phash: str | None = None) -> ImageFingerprint:
    return ImageFingerprint(
        asset_id=uuid4(),
        checksum=checksum or f"{index:064x}",
        perceptual_hash=phash or sha256(f"fixture-{index}".encode()).hexdigest()[:16],
        width=1200,
        height=800,
    )


def test_identical_and_reordered_galleries_are_duplicates():
    left = [image(index) for index in range(5)]
    right = list(reversed(left))

    assert galleries_are_duplicates(left, right)


def test_four_shared_images_out_of_five_do_not_block_a_different_room():
    shared = [image(index) for index in range(4)]
    left = [*shared, image(10)]
    right = [*shared, image(20)]

    assert not galleries_are_duplicates(left, right)


def test_two_common_property_photos_do_not_block_a_larger_different_gallery():
    shared = [image(1), image(2)]
    left = [*shared, image(3), image(4), image(5)]
    right = [*shared, image(30), image(40), image(50), image(60)]

    assert not galleries_are_duplicates(left, right)


def test_single_photo_requires_exact_normalized_checksum():
    left = [image(1, checksum="a" * 64, phash="0" * 16)]
    perceptually_same = [image(2, checksum="b" * 64, phash="0" * 16)]
    exact = [image(3, checksum="a" * 64, phash="f" * 16)]

    assert not galleries_are_duplicates(left, perceptually_same)
    assert galleries_are_duplicates(left, exact)


def test_perceptual_hash_hamming_distance_is_bit_based():
    assert hamming_distance("0000000000000000", "0000000000000001") == 1
    assert hamming_distance("0000000000000000", "000000000000000f") == 4
