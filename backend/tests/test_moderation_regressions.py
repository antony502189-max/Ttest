from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.models import Listing, User
from app.services import admin as admin_service
from app.services import admin_users, messages, moderation_expiry
from app.services.catalog import touch_catalog


@pytest.mark.asyncio
async def test_initial_message_requires_canonical_public_listing_visibility(monkeypatch: pytest.MonkeyPatch) -> None:
    query = MagicMock()
    query.where.return_value = query
    visibility = MagicMock(return_value=query)
    enforce_view = AsyncMock()
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(one_or_none=lambda: None)))
    user = SimpleNamespace(id=uuid4())
    listing_id = uuid4()

    monkeypatch.setattr(messages, "visible_query", visibility)
    monkeypatch.setattr(messages, "enforce_listing_view_access", enforce_view)

    with pytest.raises(HTTPException) as exc:
        await messages.create_initial_message(listing_id, "hello", user, session)

    assert exc.value.status_code == 404
    enforce_view.assert_awaited_once_with(user, session)
    visibility.assert_called_once_with()
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_catalog_touch_is_atomic_postgres_upsert() -> None:
    session = SimpleNamespace(execute=AsyncMock())

    await touch_catalog(session)

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "INSERT INTO catalog_state" in sql
    assert "ON CONFLICT (id) DO UPDATE" in sql
    assert "catalog_state.version +" in sql


@pytest.mark.asyncio
async def test_listing_restriction_invalidates_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    listing_id = uuid4()
    owner_id = uuid4()
    actor_id = uuid4()
    listing = SimpleNamespace(id=listing_id, owner_user_id=owner_id, title="Room", deleted_at=None)
    owner = SimpleNamespace(id=owner_id, email="owner@example.com")
    actor = SimpleNamespace(id=actor_id)

    async def get(model, object_id):
        if model is Listing:
            return listing
        if model is User:
            return owner
        return None

    session = SimpleNamespace(get=AsyncMock(side_effect=get), add=MagicMock(), commit=AsyncMock())
    monkeypatch.setattr(admin_service, "active_listing_restriction", AsyncMock(return_value=None))
    catalog_touch = AsyncMock()
    monkeypatch.setattr(admin_service, "touch_catalog", catalog_touch)
    monkeypatch.setattr(admin_service, "public_listing", lambda *args, **kwargs: "ok")

    result = await admin_service.restrict_listing(
        listing_id,
        until=datetime.now(UTC) + timedelta(days=1),
        reason="moderation reason",
        actor=actor,
        session=session,
    )

    assert result == "ok"
    catalog_touch.assert_awaited_once_with(session)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_restriction_invalidates_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    actor = SimpleNamespace(id=uuid4())
    target = SimpleNamespace(id=user_id, deleted_at=None, email="user@example.com")

    async def get(model, object_id):
        if model is User:
            return target
        return None

    session = SimpleNamespace(get=AsyncMock(side_effect=get), add=MagicMock(), commit=AsyncMock())
    monkeypatch.setattr(admin_users, "active_user_restriction", AsyncMock(return_value=None))
    monkeypatch.setattr(admin_users, "get_user_detail", AsyncMock(return_value="detail"))
    catalog_touch = AsyncMock()
    monkeypatch.setattr(admin_users, "touch_catalog", catalog_touch)

    result = await admin_users.restrict_user(
        user_id,
        restriction_type="publish",
        until=datetime.now(UTC) + timedelta(days=1),
        reason="moderation reason",
        actor=actor,
        session=session,
    )

    assert result == "detail"
    catalog_touch.assert_awaited_once_with(session)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_expiry_locks_parent_before_restriction() -> None:
    user_id = uuid4()
    restriction_id = uuid4()
    user = SimpleNamespace(id=user_id)
    restriction = SimpleNamespace(id=restriction_id)
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[user, restriction]))

    result = await moderation_expiry._expired_user_candidate(
        session,
        restriction_id,
        user_id,
        datetime.now(UTC),
    )

    assert result == (restriction, user)
    statements = [str(call.args[0]) for call in session.scalar.await_args_list]
    assert "FROM users" in statements[0]
    assert "FOR UPDATE" in statements[0]
    assert "FROM user_restrictions" in statements[1]
    assert "FOR UPDATE" in statements[1]


@pytest.mark.asyncio
async def test_listing_expiry_locks_parent_before_restriction() -> None:
    listing_id = uuid4()
    restriction_id = uuid4()
    owner_id = uuid4()
    listing = SimpleNamespace(id=listing_id, owner_user_id=owner_id)
    restriction = SimpleNamespace(id=restriction_id)
    owner = SimpleNamespace(id=owner_id, deleted_at=None)
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[listing, restriction]),
        get=AsyncMock(return_value=owner),
    )

    result = await moderation_expiry._expired_listing_candidate(
        session,
        restriction_id,
        listing_id,
        datetime.now(UTC),
    )

    assert result == (restriction, listing, owner)
    statements = [str(call.args[0]) for call in session.scalar.await_args_list]
    assert "FROM listings" in statements[0]
    assert "FOR UPDATE" in statements[0]
    assert "FROM listing_restrictions" in statements[1]
    assert "FOR UPDATE" in statements[1]
