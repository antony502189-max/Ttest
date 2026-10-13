from datetime import UTC, datetime
from uuid import UUID

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import insert

from app.db.session import SessionLocal
from app.models import Listing, User
from app.models.moderation import AdminAccess

pytestmark = pytest.mark.integration


async def seed(client, register_user):
    token, admin = await register_user(client, email="listing-pages@example.com")
    owner_id = UUID(admin["id"])
    async with SessionLocal() as session:
        owner = await session.get(User, owner_id)
        owner.google_subject = "synthetic-admin-google-subject"
        owner.name = "Ana García"
        session.add(AdminAccess(email=owner.email))
        await session.execute(insert(Listing), [{
            "id": UUID(f"10000000-0000-4000-8000-{i:012}"), "owner_user_id": owner_id,
            "title": f"Habitación {i:05}" if i != 1 else "100%_/ literal",
            "city": "City-only marker", "area": "Centro", "approximate_address": "Centro",
            "rental_mode": "long" if i % 2 == 0 else "holiday", "status": "pending",
            "monthly_price": 500 if i % 2 == 0 else None, "nightly_price": 50 if i % 2 else None,
            "location": WKTElement("POINT(-16.25 28.46)", srid=4326),
            "created_at": datetime(2026, 9, 30, tzinfo=UTC),
        } for i in range(205)])
        await session.commit()
    return {"Authorization": f"Bearer {token}"}


async def test_filtered_cursor_pages_reach_every_matching_listing_with_equal_timestamps(client, register_user):
    headers = await seed(client, register_user)
    params = {"rentalMode": "long", "limit": 50}
    ids = []
    while True:
        response = await client.get("/api/v1/admin/listings", params=params, headers=headers)
        assert response.status_code == 200, response.text
        page = response.json()
        assert all(row["rentalMode"] == "long" for row in page)
        ids.extend(row["id"] for row in page)
        if len(page) < 50:
            break
        params.update(afterId=page[-1]["id"], afterCreatedAt=page[-1]["createdAt"])
    assert ids == [f"10000000-0000-4000-8000-{i:012}" for i in range(204, -1, -2)]
    assert len(ids) == len(set(ids)) == 103


@pytest.mark.parametrize("search,expected", [
    ("habitACIÓN 00000", 1), ("GARCÍA Centro", 205), ("100%_/", 1),
    ("City-only marker", 0), ("listing-pages@example.com", 0), ("   ", 205),
    (" literal", 1), (" literal ", 1), (" literal  ", 0),
])
async def test_display_search_preserves_the_existing_literal_title_owner_area_filter(client, register_user, search, expected):
    headers = await seed(client, register_user)
    response = await client.get("/api/v1/admin/listings", params={"displaySearch": search, "limit": 200}, headers=headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == min(expected, 200)


async def test_page_parameters_keep_admin_authorization_and_validation(client, register_user):
    token, _ = await register_user(client, email="ordinary-listing-pages@example.com")
    assert (await client.get("/api/v1/admin/listings", params={"rentalMode": "long"})).status_code == 401
    assert (await client.get("/api/v1/admin/listings", headers={"Authorization": f"Bearer {token}"})).status_code == 403
    headers = await seed(client, register_user)
    assert (await client.get("/api/v1/admin/listings", headers=headers, params={"rentalMode": "invalid"})).status_code == 422
    assert (await client.get("/api/v1/admin/listings", headers=headers, params={"afterId": "10000000-0000-4000-8000-000000000100"})).status_code == 422
    assert (await client.get("/api/v1/admin/listings", headers=headers, params={"limit": 201})).status_code == 422
