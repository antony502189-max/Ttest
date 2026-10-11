"""Real PostgreSQL/PostGIS contract: region facet totals match public card totals."""
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.db.session import SessionLocal
from app.models import Listing, User
from app.repositories.listings import point

pytestmark = pytest.mark.integration


async def test_autonomous_community_counts_match_published_spatial_card_search(client: AsyncClient):
    async with SessionLocal() as session:
        owner = User(
            email="community-region-owner@example.test", password_hash="unused",
            name="Region Owner", role="host", initials="RO", email_verified=True,
        )
        session.add(owner)
        await session.flush()
        now = datetime.now(UTC)
        fixtures = [
            # Name deliberately differs from the autonomous community; city
            # substring matching must never be used for Cataluña or Canarias.
            ("Barcelona centre", "Barcelona", 2.1686, 41.3874, "long", 700, "published"),
            ("Madrid centre", "Madrid", -3.7038, 40.4168, "long", 800, "published"),
            ("Tenerife coast", "Adeje", -16.751, 28.119, "long", 650, "published"),
            ("Gran Canaria", "Telde", -15.416, 27.99, "long", 690, "published"),
            ("Sevilla", "Sevilla", -5.9845, 37.3891, "long", 550, "published"),
            ("Hidden Barcelona", "Barcelona", 2.1686, 41.3874, "long", 500, "hidden"),
            ("Over-cap Madrid", "Madrid", -3.7038, 40.4168, "long", 1100, "published"),
            ("Holiday Madrid", "Madrid", -3.7038, 40.4168, "holiday", 800, "published"),
        ]
        for title, city, lng, lat, mode, price, status in fixtures:
            session.add(Listing(
                owner_user_id=owner.id, title=title, city=city, area="Centro",
                approximate_address="Centro", rental_mode=mode, monthly_price=price,
                nightly_price=price if mode == "holiday" else None,
                location=point(lng, lat), status=status, published_at=now,
                created_at=now,
            ))
        await session.commit()

    request = {"rentalMode": "long"}
    counts_response = await client.post("/api/v1/listings/regions/counts", json=request)
    assert counts_response.status_code == 200, counts_response.text
    facets = {item["id"]: item for item in counts_response.json()["items"]}
    assert len(facets) == 17
    assert {region: facets[region]["count"] for region in ("01", "05", "09", "13")} == {
        "01": 1, "05": 2, "09": 1, "13": 1,
    }
    assert "Barcelona" in facets["09"]["cities"]
    assert "Telde" in facets["05"]["cities"]
    assert sum(facet["count"] for facet in facets.values()) == 5

    for region in ("01", "05", "09", "13", "17"):
        results = await client.post(
            "/api/v1/listings/search/cards",
            json={**request, "query": "name must be ignored when region is selected",
                  "autonomousCommunity": region, "limit": 20},
        )
        assert results.status_code == 200, results.text
        assert results.json()["total"] == facets[region]["count"]

    filtered = await client.post(
        "/api/v1/listings/regions/counts",
        json={"rentalMode": "long", "maxPrice": 700},
    )
    assert filtered.status_code == 200, filtered.text
    reduced = {item["id"]: item["count"] for item in filtered.json()["items"]}
    assert reduced["13"] == 0
    assert reduced["09"] == 1
    assert reduced["05"] == 2
