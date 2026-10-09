"""Regression coverage for card/detail galleries after bounded catalog optimization."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Listing, ListingImage, MediaAsset, User
from app.repositories.listings import point, response_from, search_public_cards, visible_query
from app.schemas.listings import ListingCardSearchRequest

pytestmark = pytest.mark.integration


async def _seed_listing_with_gallery(session, owner: User, rental_mode: str, suffix: str) -> Listing:
    listing = Listing(
        owner_user_id=owner.id,
        title=f"Gallery regression {rental_mode} {suffix}",
        city="Adeje",
        area="Playa de las Américas",
        approximate_address="Playa de las Américas · ubicación aproximada",
        rental_mode=rental_mode,
        monthly_price=725 if rental_mode == "long" else None,
        nightly_price=55 if rental_mode == "holiday" else None,
        weekly_price=330 if rental_mode == "holiday" else None,
        location=point(-16.733, 28.061),
        status="published",
        published_at=datetime.now(UTC),
    )
    session.add(listing)
    await session.flush()

    for index in range(5):
        asset = MediaAsset(
            owner_id=owner.id,
            storage_key=f"gallery-regression/{suffix}/{index}.jpg",
            mime_type="image/jpeg",
            size_bytes=1024 + index,
            width=1200,
            height=800,
            checksum=f"{suffix}-{index}".ljust(64, "0")[:64],
            perceptual_hash=None,
            kind="listing_image",
        )
        session.add(asset)
        await session.flush()
        session.add(ListingImage(
            listing_id=listing.id,
            media_asset_id=asset.id,
            sort_order=index,
            is_cover=index == 0,
        ))
    return listing


@pytest.mark.parametrize("rental_mode", ["long"])
async def test_bounded_cards_and_detail_keep_full_gallery_for_eligible_long_term_rentals(rental_mode: str):
    async with SessionLocal() as session:
        owner = User(
            email=f"gallery-{rental_mode}@example.test",
            password_hash="unused",
            name="Gallery Host",
            role="host",
            initials="GH",
            email_verified=True,
        )
        session.add(owner)
        await session.flush()
        listing = await _seed_listing_with_gallery(session, owner, rental_mode, rental_mode)
        listing_id = listing.id
        await session.commit()

    async with SessionLocal() as session:
        cards = await search_public_cards(session, ListingCardSearchRequest(
            rentalMode=rental_mode,
            query="Tenerife",
            limit=20,
            sort="newest",
        ))
        card = next(item for item in cards.items if item.id == str(listing_id))
        assert len(card.imageUrls) == 5
        assert card.coverImageUrl == card.imageUrls[0]
        assert card.imageUrls == [
            f"/api/v1/media/{asset_id}"
            for asset_id in (
                await session.execute(
                    select(ListingImage.media_asset_id)
                    .where(ListingImage.listing_id == listing_id)
                    .order_by(ListingImage.is_cover.desc(), ListingImage.sort_order)
                )
            ).scalars().all()
        ]

        row = (await session.execute(visible_query().where(Listing.id == listing_id))).one()
        detail = response_from(row)
        assert detail.imageUrls == card.imageUrls
        assert len(detail.imageUrls) == 5
