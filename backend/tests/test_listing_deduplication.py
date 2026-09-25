from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.services.duplicate_cleanup import _direct_duplicate_batches
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



def test_cleanup_does_not_collapse_transitive_similarity_chain():
    shared_ab = [image(index) for index in range(9)]
    only_a = image(90)
    shared_bc_only = image(91)
    only_c = image(92)

    first_id = UUID(int=1)
    middle_id = UUID(int=2)
    last_id = UUID(int=3)
    galleries = {
        first_id: [*shared_ab, only_a],
        middle_id: [*shared_ab, shared_bc_only],
        last_id: [*shared_ab[:8], shared_bc_only, only_c],
    }
    listings = {
        listing_id: SimpleNamespace(
            id=listing_id,
            is_external=False,
            published_at=None,
            created_at=None,
        )
        for listing_id in galleries
    }

    assert galleries_are_duplicates(galleries[first_id], galleries[middle_id])
    assert galleries_are_duplicates(galleries[middle_id], galleries[last_id])
    assert not galleries_are_duplicates(galleries[first_id], galleries[last_id])

    batches = _direct_duplicate_batches(galleries.keys(), galleries, listings)  # type: ignore[arg-type]
    assert [(batch[0].id, [item.id for item in batch[1]]) for batch in batches] == [
        (first_id, [middle_id])
    ]
