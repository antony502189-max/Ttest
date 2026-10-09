"""Small synthetic catalog proving response bounds independently of catalog size."""

from datetime import UTC, datetime, timedelta

import pytest

from app.db.session import SessionLocal
from app.models import Listing, User
from app.repositories.listings import point, search_public_cards, search_public_map
from app.schemas.listings import ListingCardSearchRequest, ListingMapRequest

pytestmark = pytest.mark.integration


async def test_keyset_pages_and_viewport_clusters_remain_bounded():
    async with SessionLocal() as session:
        owner = User(
            email="spain-scale-owner@example.test", password_hash="unused",
            name="Scale Owner", role="host", initials="SO", email_verified=True,
        )
        session.add(owner)
        await session.flush()
        now = datetime.now(UTC)
        for number in range(505):
            session.add(Listing(
                owner_user_id=owner.id, title=f"Madrid room {number}",
                city="Madrid", area="Centro", approximate_address="Centro",
                rental_mode="long", monthly_price=400 + (number % 550),
                location=point(-3.70 + number * 0.00001, 40.42),
                status="published", published_at=now,
                created_at=now - timedelta(minutes=number),
            ))
        await session.commit()

    async with SessionLocal() as session:
        first = await search_public_cards(session, ListingCardSearchRequest(
            rentalMode="long", query="Madrid", limit=20, sort="newest",
        ))
        assert first.total == 505
        assert len(first.items) == 20
        assert all(item.coverImageUrl is None for item in first.items)
        second = await search_public_cards(session, ListingCardSearchRequest(
            rentalMode="long", query="Madrid", limit=20, sort="newest", cursor=first.nextCursor,
        ))
        assert len(second.items) == 20
        assert {item.id for item in first.items}.isdisjoint(item.id for item in second.items)
        previous = await search_public_cards(session, ListingCardSearchRequest(
            rentalMode="long", query="Madrid", limit=20, sort="newest", cursor=second.previousCursor,
        ))
        assert [item.id for item in previous.items] == [item.id for item in first.items]

        penultimate = await search_public_cards(session, ListingCardSearchRequest(
            rentalMode="long", query="Madrid", limit=50, sort="newest",
        ))
        cursor = penultimate.nextCursor
        for _ in range(9):
            page = await search_public_cards(session, ListingCardSearchRequest(
                rentalMode="long", query="Madrid", limit=50, sort="newest", cursor=cursor,
            ))
            cursor = page.nextCursor
        last = await search_public_cards(session, ListingCardSearchRequest(
            rentalMode="long", query="Madrid", limit=50, sort="newest", cursor=cursor,
        ))
        assert len(last.items) == 5
        assert last.nextCursor is None
        assert last.previousCursor is not None

        for sort in ("oldest", "price_asc", "price_desc", "saved_new", "saved_old", "reduced",
                     "sqm_asc", "sqm_desc", "area_asc", "area_desc", "floor_asc", "floor_desc"):
            request = {"rentalMode": "long", "query": "Madrid", "limit": 20, "sort": sort,
                       "favoriteIds": [second.items[0].id]}
            sorted_first = await search_public_cards(session, ListingCardSearchRequest(**request))
            sorted_second = await search_public_cards(session, ListingCardSearchRequest(
                **request, cursor=sorted_first.nextCursor,
            ))
            assert len(sorted_first.items) == len(sorted_second.items) == 20
            assert {item.id for item in sorted_first.items}.isdisjoint(item.id for item in sorted_second.items)
            if sort.startswith("saved_"):
                assert sorted_first.items[0].id == second.items[0].id

        viewport = {"rentalMode": "long", "west": -4, "east": -3, "south": 40, "north": 41}
        low = await search_public_map(session, ListingMapRequest(**viewport, zoom=6))
        high = await search_public_map(session, ListingMapRequest(**viewport, zoom=16))
        assert len(low.items) <= 400
        assert all(item.type == "cluster" for item in low.items)
        assert len(high.items) <= 400
        assert all(item.type == "cluster" for item in high.items)
