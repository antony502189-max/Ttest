import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models import SavedSearch, User
from app.schemas.searches import GuestStateImport, SavedSearchWrite
from app.services import search_state

pytestmark = pytest.mark.integration


def limited_settings() -> Settings:
    return Settings(
        max_saved_searches_per_user=2,
        max_saved_search_filter_bytes=16_384,
        max_saved_search_filter_nodes=500,
    )


def saved(name: str) -> SavedSearchWrite:
    return SavedSearchWrite(
        name=name,
        query=name,
        rentalMode="long",
        filters={"area": name},
        polygon=[],
        alertsEnabled=True,
    )


async def create_user(email: str) -> User:
    async with SessionLocal() as session:
        user = User(
            email=email,
            password_hash="unused",
            name="Saved Search Test",
            role="tenant",
            initials="SS",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def test_direct_create_rejects_searches_above_account_quota(monkeypatch):
    settings = limited_settings()
    monkeypatch.setattr(search_state, "get_settings", lambda: settings)
    user = await create_user("saved-search-limit@example.test")

    async with SessionLocal() as session:
        stored_user = await session.get(User, user.id)
        assert stored_user is not None
        await search_state.create_saved_search(saved("first"), stored_user, session)
        await search_state.create_saved_search(saved("second"), stored_user, session)
        with pytest.raises(HTTPException, match="Saved search limit reached") as error:
            await search_state.create_saved_search(saved("third"), stored_user, session)
        assert error.value.status_code == 409
        await session.rollback()

    async with SessionLocal() as check:
        count = await check.scalar(
            select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user.id)
        )
        assert count == 2


async def test_guest_import_stops_at_quota_without_failing_login_flow(monkeypatch):
    settings = limited_settings()
    monkeypatch.setattr(search_state, "get_settings", lambda: settings)
    user = await create_user("saved-search-import@example.test")
    payload = GuestStateImport(
        favoriteIds=[],
        savedSearches=[saved("first"), saved("second"), saved("third")],
    )

    async with SessionLocal() as session:
        stored_user = await session.get(User, user.id)
        assert stored_user is not None
        await search_state.import_guest_state(payload, stored_user, session)

    async with SessionLocal() as check:
        searches = (
            await check.scalars(
                select(SavedSearch)
                .where(SavedSearch.user_id == user.id)
                .order_by(SavedSearch.created_at, SavedSearch.id)
            )
        ).all()
        assert len(searches) == 2
        assert {item.name for item in searches} == {"first", "second"}
