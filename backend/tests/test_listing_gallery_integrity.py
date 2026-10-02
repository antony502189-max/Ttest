from uuid import UUID

from app.services.listing_gallery_integrity import (
    GalleryImageSnapshot,
    GalleryListingSnapshot,
    _matching_repair_candidates,
)


def image(index: int, checksum: str) -> GalleryImageSnapshot:
    return GalleryImageSnapshot(
        asset_id=UUID(int=index + 1),
        checksum=checksum,
        sort_order=index,
        is_cover=index == 0,
    )


def listing(
    listing_id: int,
    *,
    rental_mode: str,
    checksums: list[str],
    owner_id: int = 1,
    title: str = "Habitación privada con cocina y aseo propios",
    street: str = "Avenida V Centenario 1",
    postcode: str = "38660",
) -> GalleryListingSnapshot:
    return GalleryListingSnapshot(
        listing_id=UUID(int=listing_id),
        owner_id=UUID(int=owner_id),
        title=title,
        street=street,
        postcode=postcode,
        rental_mode=rental_mode,
        status="published",
        images=tuple(image(index, checksum) for index, checksum in enumerate(checksums)),
    )


def test_truncated_holiday_gallery_can_recover_from_exact_long_stay_prefix():
    target = listing(10, rental_mode="holiday", checksums=["cover"])
    source = listing(
        20,
        rental_mode="long",
        checksums=["cover", "2", "3", "4", "5", "6", "7", "8"],
    )

    assert _matching_repair_candidates(target, [source]) == [source]


def test_repair_refuses_similar_address_when_cover_does_not_match_exactly():
    target = listing(10, rental_mode="holiday", checksums=["target-cover"])
    source = listing(
        20,
        rental_mode="long",
        checksums=["different-cover", "2", "3", "4", "5"],
    )

    assert _matching_repair_candidates(target, [source]) == []


def test_repair_refuses_ambiguous_same_cover_siblings():
    target = listing(10, rental_mode="holiday", checksums=["cover"])
    first = listing(20, rental_mode="long", checksums=["cover", "2", "3", "4", "5"])
    second = listing(30, rental_mode="long", checksums=["cover", "a", "b", "c", "d"])

    assert len(_matching_repair_candidates(target, [first, second])) == 2


def test_repair_requires_same_owner_normalized_private_address_and_title():
    target = listing(10, rental_mode="holiday", checksums=["cover"])
    other_owner = listing(20, rental_mode="long", checksums=["cover", "2", "3", "4", "5"], owner_id=2)
    other_address = listing(
        30,
        rental_mode="long",
        checksums=["cover", "2", "3", "4", "5"],
        street="Otra calle 2",
    )
    other_title = listing(
        40,
        rental_mode="long",
        checksums=["cover", "2", "3", "4", "5"],
        title="Otra habitación",
    )

    assert _matching_repair_candidates(target, [other_owner, other_address, other_title]) == []


def test_repair_accepts_normalized_accents_case_and_whitespace():
    target = listing(
        10,
        rental_mode="holiday",
        checksums=["cover"],
        title="Habitación privada",
        street="Avenida   V Centenario 1",
    )
    source = listing(
        20,
        rental_mode="long",
        checksums=["cover", "2", "3", "4", "5"],
        title="HABITACION PRIVADA",
        street=" avenida v centenario 1 ",
    )

    assert _matching_repair_candidates(target, [source]) == [source]
