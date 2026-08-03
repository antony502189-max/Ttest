from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Listing, ListingView, User
from app.repositories.listings import point
from app.services.listing_views import register_view

pytestmark = pytest.mark.integration


async def test_listing_view_deduplication_prunes_prior_days():
    async with SessionLocal() as setup:
        owner = User(
            email="listing-view-owner@example.test",
            password_hash="unused",
            name="View Owner",
            role="host",
            initials="VO",
            email_verified=True,
        )
        setup.add(owner)
        await setup.flush()
        listing = Listing(
            owner_user_id=owner.id,
            title="View-limited listing",
            city="Santa Cruz de Tenerife",
            area="Centro",
            approximate_address="Centro",
            rental_mode="long",
            monthly_price=700,
            location=point(-16.25, 28.46),
            status="published",
            views=0,
        )
        setup.add(listing)
        await setup.flush()
        setup.add(
            ListingView(
                listing_id=listing.id,
                viewer_key="old-viewer",
                view_date=datetime.now(UTC).date() - timedelta(days=2),
            )
        )
        await setup.commit()
        listing_id = listing.id

    async with SessionLocal() as session:
        stored = await session.get(Listing, listing_id)
        assert stored is not None
        assert await register_view(stored, "stable-viewer", session) is True
        assert await register_view(stored, "stable-viewer", session) is False

    async with SessionLocal() as check:
        stored = await check.get(Listing, listing_id)
        assert stored is not None
        assert stored.views == 1
        rows = await check.scalar(
            select(func.count()).select_from(ListingView).where(ListingView.listing_id == listing_id)
        )
        old_rows = await check.scalar(
            select(func.count())
            .select_from(ListingView)
            .where(
                ListingView.listing_id == listing_id,
                ListingView.view_date < datetime.now(UTC).date(),
            )
        )
        assert rows == 1
        assert old_rows == 0
