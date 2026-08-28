from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Listing, MailOutbox, Notification
from app.services.listing_lifecycle import expire_due_listings

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def listing_payload(title: str) -> dict:
    today = datetime.now(UTC).date()
    return {
        "title": title,
        "city": "Adeje",
        "area": "Centro",
        "street": "Private street",
        "postcode": "38670",
        "approximateAddress": "Adeje · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 650,
        "nightlyPrice": None,
        "weeklyPrice": None,
        "roomType": "Habitación individual",
        "availableFrom": today.isoformat(),
        "availableUntil": None,
        "minimumStayMonths": 1,
        "minimumNights": None,
        "depositAmount": 650,
        "billsIncluded": True,
        "bathroom": "Baño compartido",
        "kitchen": "Cocina compartida",
        "furnished": True,
        "roomSizeM2": 12,
        "bedroomCount": 3,
        "currentResidents": 2,
        "roomCapacity": 1,
        "shower": "Ducha compartida",
        "tenantRequirement": "any",
        "smokingAllowed": False,
        "petsAllowed": False,
        "childrenAllowed": False,
        "empadronamientoAllowed": True,
        "restrictions": [],
        "amenities": ["Wifi"],
        "latitude": 28.1227,
        "longitude": -16.7244,
        "exactLatitude": 28.123,
        "exactLongitude": -16.724,
        "description": "Lifecycle integration listing.",
        "homeDescription": "Shared home.",
        "advertiserType": "Particular",
        "expiresAt": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
    }


async def test_expired_listing_closes_once_and_notifies_owner_and_favorite_holder(
    client: AsyncClient,
    register_user,
) -> None:
    owner_token, owner = await register_user(client, email="expiry-owner@example.com", role="host")
    tenant_token, tenant = await register_user(client, email="expiry-tenant@example.com", role="tenant")

    created = await client.post(
        "/api/v1/listings",
        headers=auth(owner_token),
        json=listing_payload("Room that expires server-side"),
    )
    assert created.status_code == 201, created.text
    listing_id = UUID(created.json()["id"])

    favorited = await client.put(f"/api/v1/favorites/{listing_id}", headers=auth(tenant_token))
    assert favorited.status_code == 204, favorited.text

    async with SessionLocal() as session:
        listing = await session.get(Listing, listing_id)
        assert listing is not None
        listing.status = "published"
        listing.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    async with SessionLocal() as session:
        assert await expire_due_listings(session) == 1

    async with SessionLocal() as session:
        listing = await session.get(Listing, listing_id)
        assert listing is not None
        assert listing.status == "closed"
        assert listing.closed_reason == "expired"

        owner_types = set(
            await session.scalars(
                select(Notification.type).where(Notification.recipient_user_id == UUID(owner["id"]))
            )
        )
        tenant_types = set(
            await session.scalars(
                select(Notification.type).where(Notification.recipient_user_id == UUID(tenant["id"]))
            )
        )
        assert "listing_expired" in owner_types
        assert "favorite_unavailable" in tenant_types

        owner_mail = await session.scalar(
            select(func.count()).select_from(MailOutbox).where(
                MailOutbox.recipient == "expiry-owner@example.com",
                MailOutbox.kind == "notification_listing_expired",
            )
        )
        tenant_mail = await session.scalar(
            select(func.count()).select_from(MailOutbox).where(
                MailOutbox.recipient == "expiry-tenant@example.com",
                MailOutbox.kind == "notification_favorite_unavailable",
            )
        )
        assert owner_mail == 1
        assert tenant_mail == 1

        notification_count = await session.scalar(
            select(func.count()).select_from(Notification).where(Notification.entity_listing_id == listing_id)
        )

    async with SessionLocal() as session:
        assert await expire_due_listings(session) == 0
        repeated_count = await session.scalar(
            select(func.count()).select_from(Notification).where(Notification.entity_listing_id == listing_id)
        )
        assert repeated_count == notification_count
