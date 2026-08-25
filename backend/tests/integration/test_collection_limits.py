from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models import DiscardedListing, Favorite, Listing, User
from app.repositories.listings import point
from app.schemas.searches import GuestStateImport
from app.services import search_state
from app.services.listings import delete_listing
from app.services.users import delete_account

pytestmark = pytest.mark.integration


def limited_settings(limit: int) -> Settings:
    return Settings(max_listing_collection_items_per_user=limit)


async def create_users_and_listings(count: int = 3) -> tuple[User, User, list[Listing]]:
    async with SessionLocal() as session:
        owner = User(
            email=f"collection-owner-{uuid4()}@example.test",
            password_hash="unused",
            name="Collection Owner",
            role="host",
            initials="CO",
            email_verified=True,
        )
        tenant = User(
            email=f"collection-tenant-{uuid4()}@example.test",
            password_hash="unused",
            name="Collection Tenant",
            role="tenant",
            initials="CT",
            email_verified=True,
        )
        session.add_all([owner, tenant])
        await session.flush()
        listings = [
            Listing(
                owner_user_id=owner.id,
                title=f"Collection listing {index}",
                city="Santa Cruz de Tenerife",
                area="Centro",
                approximate_address="Centro",
                rental_mode="long",
                monthly_price=700 + index,
                location=point(-16.25, 28.46),
                status="published",
            )
            for index in range(count)
        ]
        session.add_all(listings)
        await session.commit()
        for value in [owner, tenant, *listings]:
            await session.refresh(value)
        return owner, tenant, listings


async def test_direct_collection_add_is_idempotent_and_enforces_quota(monkeypatch):
    monkeypatch.setattr(search_state, "get_settings", lambda: limited_settings(2))
    _, tenant, listings = await create_users_and_listings()

    async with SessionLocal() as session:
        stored_tenant = await session.get(User, tenant.id)
        assert stored_tenant is not None
        await search_state.add_collection_item(
            Favorite,
            "uq_favorites_user_listing",
            listings[0].id,
            stored_tenant,
            session,
        )
        await search_state.add_collection_item(
            Favorite,
            "uq_favorites_user_listing",
            listings[1].id,
            stored_tenant,
            session,
        )
        await search_state.add_collection_item(
            Favorite,
            "uq_favorites_user_listing",
            listings[0].id,
            stored_tenant,
            session,
        )
        with pytest.raises(HTTPException, match="Listing collection limit reached") as error:
            await search_state.add_collection_item(
                Favorite,
                "uq_favorites_user_listing",
                listings[2].id,
                stored_tenant,
                session,
            )
        assert error.value.status_code == 409
        await session.rollback()

    async with SessionLocal() as check:
        count = await check.scalar(select(func.count()).select_from(Favorite).where(Favorite.user_id == tenant.id))
        assert count == 2


async def test_guest_import_respects_zero_quota_without_breaking_import(monkeypatch):
    monkeypatch.setattr(search_state, "get_settings", lambda: limited_settings(0))
    _, tenant, listings = await create_users_and_listings(count=1)
    payload = GuestStateImport(favoriteIds=[str(listings[0].id)], savedSearches=[])

    async with SessionLocal() as session:
        stored_tenant = await session.get(User, tenant.id)
        assert stored_tenant is not None
        await search_state.import_guest_state(payload, stored_tenant, session)

    async with SessionLocal() as check:
        count = await check.scalar(select(func.count()).select_from(Favorite).where(Favorite.user_id == tenant.id))
        assert count == 0


async def test_soft_deleted_listing_removes_collection_rows(monkeypatch):
    monkeypatch.setattr(search_state, "get_settings", lambda: limited_settings(10))
    owner, tenant, listings = await create_users_and_listings(count=1)
    listing = listings[0]

    async with SessionLocal() as session:
        stored_tenant = await session.get(User, tenant.id)
        stored_owner = await session.get(User, owner.id)
        assert stored_tenant is not None and stored_owner is not None
        # Destructive listing removal is intentionally reserved for the
        # production hard-delete allow-list. This test exercises its cleanup
        # side effects with an authorized account.
        stored_owner.email = "antony502189@gmail.com"
        await search_state.add_collection_item(
            Favorite,
            "uq_favorites_user_listing",
            listing.id,
            stored_tenant,
            session,
        )
        await search_state.add_collection_item(
            DiscardedListing,
            "uq_discarded_user_listing",
            listing.id,
            stored_tenant,
            session,
        )
        await delete_listing(listing.id, stored_owner, session)

    async with SessionLocal() as check:
        assert await check.scalar(select(Favorite).where(Favorite.listing_id == listing.id)) is None
        assert await check.scalar(select(DiscardedListing).where(DiscardedListing.listing_id == listing.id)) is None


async def test_account_deletion_removes_rows_that_reference_owned_listings(monkeypatch):
    monkeypatch.setattr(search_state, "get_settings", lambda: limited_settings(10))
    owner, tenant, listings = await create_users_and_listings(count=1)
    listing = listings[0]

    async with SessionLocal() as session:
        stored_tenant = await session.get(User, tenant.id)
        stored_owner = await session.get(User, owner.id)
        assert stored_tenant is not None and stored_owner is not None
        await search_state.add_collection_item(
            Favorite,
            "uq_favorites_user_listing",
            listing.id,
            stored_tenant,
            session,
        )
        await delete_account(stored_owner, session)

    async with SessionLocal() as check:
        assert await check.scalar(select(Favorite).where(Favorite.listing_id == listing.id)) is None
