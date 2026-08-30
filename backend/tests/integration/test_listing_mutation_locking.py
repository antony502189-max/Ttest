from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Listing, User
from app.schemas.listings import ListingPatch
from app.services import listings

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def listing_payload(title: str) -> dict:
    return {
        "title": title,
        "city": "Santa Cruz de Tenerife",
        "area": "Centro",
        "street": "Synthetic locking street",
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
        "description": "Synthetic listing used to prove transaction-level mutation serialization.",
        "homeDescription": "Synthetic shared-home description.",
        "advertiserType": "Particular",
        "expiresAt": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
    }


@pytest.mark.parametrize("operation", ["update", "renew"])
async def test_owner_listing_mutation_locks_row_before_authorization_and_validation(
    client,
    register_user,
    monkeypatch,
    operation: str,
) -> None:
    """A competing transaction must not observe the listing row as lockable.

    The pause happens inside ``ensure_owner_or_admin``. Therefore the mutation
    must have acquired its explicit row lock before authorization/transition
    validation. Locking only immediately before commit would not satisfy this
    contract and would still permit stale-state validation races.
    """
    token, user_body = await register_user(
        client,
        email=f"locking-{operation}@example.com",
        role="host",
    )
    created = await client.post(
        "/api/v1/listings",
        headers=auth(token),
        json=listing_payload(f"Locking regression {operation}"),
    )
    assert created.status_code == 201, created.text
    listing_id = UUID(created.json()["id"])
    user_id = UUID(user_body["id"])

    entered_authorization = asyncio.Event()
    release_authorization = asyncio.Event()
    original_authorize = listings.ensure_owner_or_admin

    async def paused_authorize(listing, user, session):
        entered_authorization.set()
        await release_authorization.wait()
        return await original_authorize(listing, user, session)

    monkeypatch.setattr(listings, "ensure_owner_or_admin", paused_authorize)

    async def mutate() -> None:
        async with SessionLocal() as session:
            user = await session.get(User, user_id)
            assert user is not None
            if operation == "update":
                await listings.update_listing(
                    listing_id,
                    ListingPatch(title="Serialized owner update"),
                    user,
                    session,
                )
            else:
                await listings.renew_listing(listing_id, user, session)

    task = asyncio.create_task(mutate())
    await asyncio.wait_for(entered_authorization.wait(), timeout=5)

    async with SessionLocal() as probe:
        lockable_id = await probe.scalar(
            select(Listing.id)
            .where(Listing.id == listing_id)
            .with_for_update(skip_locked=True)
        )
        await probe.rollback()

    release_authorization.set()
    await asyncio.wait_for(task, timeout=5)

    assert lockable_id is None, (
        f"{operation} reached authorization without locking the listing row; "
        "a concurrent mutation can validate against stale lifecycle state"
    )
