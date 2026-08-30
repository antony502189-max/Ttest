from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Listing, User
from app.services.listing_lifecycle import expire_due_listings

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def listing_payload(title: str) -> dict:
    return {
        "title": title,
        "city": "Santa Cruz de Tenerife",
        "area": "Centro",
        "street": "Synthetic lifecycle street",
        "postcode": "38001",
        "approximateAddress": "Centro · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 700,
        "nightlyPrice": None,
        "weeklyPrice": None,
        "roomType": "Habitación individual",
        "availableFrom": datetime.now(UTC).date().isoformat(),
        "availableUntil": None,
        "minimumStayMonths": 1,
        "minimumNights": None,
        "depositAmount": 700,
        "billsIncluded": True,
        "bathroom": "Baño compartido",
        "kitchen": "Cocina compartida",
        "furnished": True,
        "roomSizeM2": 14,
        "bedroomCount": 3,
        "currentResidents": 2,
        "roomCapacity": 1,
        "shower": "Ducha compartida",
        "tenantRequirement": "any",
        "smokingAllowed": False,
        "petsAllowed": False,
        "childrenAllowed": False,
        "empadronamientoAllowed": True,
        "restrictions": ["No fumar"],
        "amenities": ["Wi-Fi"],
        "latitude": 28.1000,
        "longitude": -16.7000,
        "exactLatitude": 28.1004,
        "exactLongitude": -16.6996,
        "description": "Synthetic listing used to prove lifecycle serialization.",
        "homeDescription": "Synthetic shared-home description.",
        "advertiserType": "Particular",
        "expiresAt": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
    }


async def test_expiry_worker_skips_owner_locked_by_account_mutation_and_retries_next_cycle(
    client,
    register_user,
) -> None:
    token, user_body = await register_user(
        client,
        email="lifecycle-lock-order@example.com",
        role="host",
    )
    created = await client.post(
        "/api/v1/listings",
        headers=auth(token),
        json=listing_payload("Lifecycle lock order regression"),
    )
    assert created.status_code == 201, created.text
    listing_id = UUID(created.json()["id"])
    user_id = UUID(user_body["id"])

    async with SessionLocal() as prepare:
        listing = await prepare.get(Listing, listing_id)
        assert listing is not None
        listing.status = "published"
        listing.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await prepare.commit()

    async with SessionLocal() as blocker, SessionLocal() as worker:
        locked_user = await blocker.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )
        assert locked_user is not None

        # The worker must not take Listing first and then wait for User. It skips
        # this owner immediately and leaves the row for the next lifecycle pass.
        expired = await asyncio.wait_for(expire_due_listings(worker), timeout=2)
        assert expired == 0

        await blocker.rollback()

    async with SessionLocal() as verify:
        listing = await verify.get(Listing, listing_id)
        assert listing is not None
        assert listing.status == "published"

    async with SessionLocal() as retry:
        expired = await asyncio.wait_for(expire_due_listings(retry), timeout=5)
        assert expired == 1

    async with SessionLocal() as verify:
        listing = await verify.get(Listing, listing_id)
        assert listing is not None
        assert listing.status == "closed"
        assert listing.closed_reason == "expired"
