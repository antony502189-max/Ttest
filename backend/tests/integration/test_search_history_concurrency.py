from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import SearchHistory, User
from app.services.search_state import MAX_HISTORY, add_history

pytestmark = pytest.mark.integration


async def create_user() -> User:
    async with SessionLocal() as session:
        user = User(
            email=f"history-{uuid4()}@example.test",
            password_hash="unused",
            name="History Test",
            role="tenant",
            initials="HT",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def write_history(user_id: UUID, query: str) -> None:
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        assert user is not None
        await add_history(query, user, session)


async def test_concurrent_history_writes_keep_a_strict_bound_and_deduplicate():
    user = await create_user()
    await asyncio.gather(*(write_history(user.id, f"query-{index}") for index in range(40)))
    await asyncio.gather(*(write_history(user.id, "same query") for _ in range(12)))

    async with SessionLocal() as session:
        total = await session.scalar(
            select(func.count()).select_from(SearchHistory).where(SearchHistory.user_id == user.id)
        )
        duplicates = await session.scalar(
            select(func.count())
            .select_from(SearchHistory)
            .where(SearchHistory.user_id == user.id, SearchHistory.normalized_query == "same query")
        )
    assert total == MAX_HISTORY
    assert duplicates == 1
