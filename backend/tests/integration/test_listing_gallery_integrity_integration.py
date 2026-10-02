from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Listing, ListingImage, MediaAsset, User
from app.repositories.listings import point
from app.services.listing_gallery_integrity import (
    active_listing_photo_count,
    repair_legacy_internal_galleries,
)
from app.services.listings import renew_listing

pytestmark = pytest.mark.integration


def checksum(index: int) -> str:
    return f"{index:064x}"


async def add_listing(
    session,
    owner: User,
    *,
    rental_mode: str,
    status: str,
    checksums: list[str],
    title: str = "Habitación privada con cocina y aseo propios",
) -> Listing:
    listing = Listing(
        owner_user_id=owner.id,
        title=title,
        city="Adeje",
        area="Playa de las Américas",
        street="Avenida V Centenario 1",
        postcode="38660",
        approximate_address="Playa de las Américas · ubicación aproximada",
        rental_mode=rental_mode,
        monthly_price=700 if rental_mode == "long" else None,
        nightly_price=55 if rental_mode == "holiday" else None,
        location=point(-16.731, 28.064),
        status=status,
        is_external=False,
    )
    session.add(listing)
    await session.flush()
    for sort_order, value in enumerate(checksums):
        asset = MediaAsset(
            owner_id=owner.id,
            storage_key=f"gallery-integrity/{uuid4()}.webp",
            mime_type="image/webp",
            size_bytes=2048,
            width=1200,
            height=800,
            checksum=value,
            perceptual_hash=f"{sort_order:016x}",
            kind="listing_image",
        )
        session.add(asset)
        await session.flush()
        session.add(
            ListingImage(
                listing_id=listing.id,
                media_asset_id=asset.id,
                sort_order=sort_order,
                is_cover=sort_order == 0,
            )
        )
    await session.flush()
    return listing


async def test_renew_rejects_legacy_internal_listing_with_too_few_active_photos():
    async with SessionLocal() as session:
        owner = User(
            email=f"gallery-guard-{uuid4()}@example.test",
            password_hash="unused",
            name="Gallery Guard",
            role="host",
            initials="GG",
            email_verified=True,
        )
        session.add(owner)
        await session.flush()
        listing = await add_listing(
            session,
            owner,
            rental_mode="holiday",
            status="closed",
            checksums=[checksum(1)],
        )
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await renew_listing(listing.id, owner, session)

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "LISTING_PHOTO_COUNT_INVALID"
        await session.rollback()


async def test_repair_restores_only_missing_suffix_from_unique_cross_mode_sibling():
    async with SessionLocal() as session:
        owner = User(
            email=f"gallery-repair-{uuid4()}@example.test",
            password_hash="unused",
            name="Gallery Repair",
            role="host",
            initials="GR",
            email_verified=True,
        )
        session.add(owner)
        await session.flush()
        source_checksums = [checksum(index) for index in range(100, 108)]
        source = await add_listing(
            session,
            owner,
            rental_mode="long",
            status="published",
            checksums=source_checksums,
        )
        target = await add_listing(
            session,
            owner,
            rental_mode="holiday",
            status="published",
            checksums=[source_checksums[0]],
        )
        source_id = source.id
        target_id = target.id
        target_cover_id = (
            await session.scalar(
                select(ListingImage.media_asset_id)
                .where(ListingImage.listing_id == target_id)
                .order_by(ListingImage.sort_order)
            )
        )
        await session.commit()

        dry_run = await repair_legacy_internal_galleries(session, apply=False)
        assert dry_run["repairable"] == 1
        assert dry_run["repaired"] == 0
        assert await active_listing_photo_count(session, target_id) == 1

        applied = await repair_legacy_internal_galleries(session, apply=True)
        assert applied["repaired"] == 1
        assert applied["repairs"][0]["listingId"] == str(target_id)
        assert applied["repairs"][0]["sourceListingId"] == str(source_id)
        assert applied["repairs"][0]["before"] == 1
        assert applied["repairs"][0]["after"] == 8
        assert await active_listing_photo_count(session, target_id) == 8

        rows = (
            await session.execute(
                select(ListingImage)
                .where(ListingImage.listing_id == target_id)
                .order_by(ListingImage.sort_order)
            )
        ).scalars().all()
        assert [row.sort_order for row in rows] == list(range(8))
        assert rows[0].media_asset_id == target_cover_id
        assert rows[0].is_cover is True
        assert all(row.is_cover is False for row in rows[1:])
