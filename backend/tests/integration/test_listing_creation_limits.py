from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models import Listing, User
from app.models.moderation import AdminAccess
from app.repositories.listings import point
from app.services import listing_limits

pytestmark = pytest.mark.integration


def limit_settings(**overrides) -> Settings:
    values = {
        "max_active_listings_per_user": 2,
        "max_listing_creations_per_day": 100,
    }
    values.update(overrides)
    return Settings(**values)


async def create_user(email: str, *, role: str = "host", google_subject: str | None = None) -> User:
    async with SessionLocal() as session:
        user = User(
            email=email,
            password_hash="unused",
            name="Listing Limit Test",
            role=role,
            initials="LL",
            email_verified=True,
            google_subject=google_subject,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def listing_for(user: User, *, status: str, deleted: bool = False) -> Listing:
    return Listing(
        owner_user_id=user.id,
        title="Quota listing",
        city="Santa Cruz de Tenerife",
        area="Centro",
        approximate_address="Centro",
        rental_mode="long",
        monthly_price=700,
        location=point(-16.25, 28.46),
        status=status,
        deleted_at=datetime.now(UTC) if deleted else None,
    )


async def test_active_listing_quota_counts_only_non_deleted_active_states(monkeypatch):
    settings = limit_settings()
    monkeypatch.setattr(listing_limits, "get_settings", lambda: settings)
    user = await create_user("listing-active-limit@example.test")

    async with SessionLocal() as session:
        stored_user = await session.get(User, user.id)
        assert stored_user is not None
        session.add_all(
            [
                listing_for(stored_user, status="pending"),
                listing_for(stored_user, status="hidden"),
                listing_for(stored_user, status="closed", deleted=True),
            ]
        )
        await session.commit()

        with pytest.raises(HTTPException, match="Active listing limit reached") as error:
            await listing_limits.enforce_listing_creation_limits(stored_user, session)
        assert error.value.status_code == 409
        await session.rollback()


async def test_daily_quota_counts_soft_deleted_rows(monkeypatch):
    settings = limit_settings(
        max_active_listings_per_user=100,
        max_listing_creations_per_day=2,
    )
    monkeypatch.setattr(listing_limits, "get_settings", lambda: settings)
    user = await create_user("listing-daily-limit@example.test")

    async with SessionLocal() as session:
        stored_user = await session.get(User, user.id)
        assert stored_user is not None
        session.add_all(
            [
                listing_for(stored_user, status="closed", deleted=True),
                listing_for(stored_user, status="closed", deleted=True),
            ]
        )
        await session.commit()

        with pytest.raises(HTTPException, match="Daily listing creation limit reached") as error:
            await listing_limits.enforce_listing_creation_limits(stored_user, session)
        assert error.value.status_code == 429
        await session.rollback()


async def test_allowlisted_google_admin_is_not_subject_to_host_quota(monkeypatch):
    settings = limit_settings(max_active_listings_per_user=1, max_listing_creations_per_day=1)
    monkeypatch.setattr(listing_limits, "get_settings", lambda: settings)
    admin = await create_user(
        "listing-admin@example.test",
        role="tenant",
        google_subject="listing-admin-google-subject",
    )

    async with SessionLocal() as session:
        stored_admin = await session.get(User, admin.id)
        assert stored_admin is not None
        session.add(AdminAccess(email=stored_admin.email.lower(), active=True, created_by=None))
        session.add(listing_for(stored_admin, status="pending"))
        await session.commit()

        await listing_limits.enforce_listing_creation_limits(stored_admin, session)


async def test_legacy_admin_role_without_allowlist_is_subject_to_host_quota(monkeypatch):
    settings = limit_settings(max_active_listings_per_user=1, max_listing_creations_per_day=1)
    monkeypatch.setattr(listing_limits, "get_settings", lambda: settings)
    legacy_admin = await create_user("listing-legacy-admin@example.test", role="admin")

    async with SessionLocal() as session:
        stored_admin = await session.get(User, legacy_admin.id)
        assert stored_admin is not None
        session.add(listing_for(stored_admin, status="pending"))
        await session.commit()

        with pytest.raises(HTTPException, match="Active listing limit reached") as error:
            await listing_limits.enforce_listing_creation_limits(stored_admin, session)
        assert error.value.status_code == 409
        await session.rollback()
