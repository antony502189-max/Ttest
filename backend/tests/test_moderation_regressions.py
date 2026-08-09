from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models import Favorite, Listing, User
from app.services import admin as admin_service
from app.services import admin_listings, admin_users, listing_limits, messages, moderation_expiry, reports, search_state
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
    owner = SimpleNamespace(id=owner_id, email="owner@example.com", deleted_at=None)
    actor = SimpleNamespace(id=actor_id)
    session = SimpleNamespace(
        get=AsyncMock(return_value=listing),
        scalar=AsyncMock(return_value=owner),
        add=MagicMock(),
        commit=AsyncMock(),
    )
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
    owner_lock = str(session.scalar.await_args.args[0])
    assert "FROM users" in owner_lock
    assert "FOR UPDATE" in owner_lock
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
async def test_revoked_legacy_admin_role_no_longer_bypasses_listing_quotas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id=uuid4(), role="admin")
    admin_check = AsyncMock(return_value=False)
    monkeypatch.setattr(listing_limits, "is_admin", admin_check)
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                None,
                SimpleNamespace(one=lambda: (0, 0)),
            ]
        )
    )

    await listing_limits.enforce_listing_creation_limits(user, session)

    admin_check.assert_awaited_once_with(user, session)
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_active_allowlisted_admin_bypasses_listing_quotas(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=uuid4(), role="tenant")
    admin_check = AsyncMock(return_value=True)
    monkeypatch.setattr(listing_limits, "is_admin", admin_check)
    session = SimpleNamespace(execute=AsyncMock())

    await listing_limits.enforce_listing_creation_limits(user, session)

    admin_check.assert_awaited_once_with(user, session)
    session.execute.assert_not_awaited()


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
async def test_listing_expiry_locks_listing_restriction_and_owner() -> None:
    listing_id = uuid4()
    restriction_id = uuid4()
    owner_id = uuid4()
    listing = SimpleNamespace(id=listing_id, owner_user_id=owner_id)
    restriction = SimpleNamespace(id=restriction_id)
    owner = SimpleNamespace(id=owner_id, deleted_at=None)
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[listing, restriction, owner]))

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
    assert "FROM users" in statements[2]
    assert "FOR UPDATE" in statements[2]


@pytest.mark.asyncio
async def test_expiry_batch_touches_catalog_once_after_all_parent_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    user_ids = [uuid4(), uuid4()]
    listing_id = uuid4()
    user_restrictions = [
        SimpleNamespace(id=uuid4(), expiry_notified_at=None),
        SimpleNamespace(id=uuid4(), expiry_notified_at=None),
    ]
    users = [
        SimpleNamespace(id=user_ids[0], email="u1@example.com"),
        SimpleNamespace(id=user_ids[1], email="u2@example.com"),
    ]
    listing_restriction = SimpleNamespace(id=uuid4(), expiry_notified_at=None)
    listing = SimpleNamespace(id=listing_id, title="Historical room")
    owner = SimpleNamespace(id=uuid4(), email="owner@example.com")

    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(all=lambda: [(user_restrictions[0].id, user_ids[0]), (user_restrictions[1].id, user_ids[1])]),
                SimpleNamespace(all=lambda: [(listing_restriction.id, listing_id)]),
            ]
        ),
        add=MagicMock(),
        commit=AsyncMock(),
    )
    monkeypatch.setattr(
        moderation_expiry,
        "_expired_user_candidate",
        AsyncMock(side_effect=[(user_restrictions[0], users[0]), (user_restrictions[1], users[1])]),
    )
    monkeypatch.setattr(
        moderation_expiry,
        "_expired_listing_candidate",
        AsyncMock(return_value=(listing_restriction, listing, owner)),
    )
    monkeypatch.setattr(moderation_expiry, "active_user_restriction", AsyncMock(return_value=None))
    monkeypatch.setattr(moderation_expiry, "active_listing_restriction", AsyncMock(return_value=None))
    catalog_touch = AsyncMock()
    monkeypatch.setattr(moderation_expiry, "touch_catalog", catalog_touch)

    result = await moderation_expiry.process_expired_moderation(session)

    assert result == {"users": 2, "listings": 1}
    catalog_touch.assert_awaited_once_with(session)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_listing_query_excludes_deleted_owners() -> None:
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=list)))

    result = await admin_listings.list_listings(
        session,
        None,
        None,
        limit=100,
        offset=0,
    )

    assert result == []
    sql = str(session.execute.await_args.args[0])
    assert "users.deleted_at IS NULL" in sql


@pytest.mark.asyncio
async def test_listing_admin_mutation_locks_and_rejects_deleted_owner() -> None:
    listing = SimpleNamespace(id=uuid4(), owner_user_id=uuid4(), deleted_at=None)
    owner = SimpleNamespace(id=listing.owner_user_id, deleted_at=datetime.now(UTC))
    session = SimpleNamespace(
        get=AsyncMock(return_value=listing),
        scalar=AsyncMock(return_value=owner),
    )

    with pytest.raises(HTTPException) as exc:
        await admin_service._actionable_listing(listing.id, session)

    assert exc.value.status_code == 404
    owner_lock = str(session.scalar.await_args.args[0])
    assert "FROM users" in owner_lock
    assert "FOR UPDATE" in owner_lock


def test_saved_listing_visibility_includes_active_moderation_predicates() -> None:
    query = select(Listing.id).join(User, User.id == Listing.owner_user_id).where(
        *search_state.visible_listing_conditions()
    )
    sql = str(query.compile(dialect=postgresql.dialect()))

    assert "user_restrictions" in sql
    assert "listing_restrictions" in sql
    assert "NOT (EXISTS" in sql
    assert "user_restrictions.ends_at IS NULL" in sql


@pytest.mark.asyncio
async def test_saved_listing_collections_enforce_requester_view_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=uuid4())
    session = SimpleNamespace(scalars=AsyncMock())
    denied = HTTPException(403, "view restricted")
    policy = AsyncMock(side_effect=denied)
    monkeypatch.setattr(search_state, "enforce_listing_view_access", policy)

    with pytest.raises(HTTPException) as exc:
        await search_state.list_collection(Favorite, user, session)

    assert exc.value.status_code == 403
    policy.assert_awaited_once_with(user, session)
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_saved_listing_add_and_import_check_view_policy_before_visibility_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id=uuid4())
    session = SimpleNamespace()
    listing_id = uuid4()
    denied = HTTPException(403, "view restricted")
    policy = AsyncMock(side_effect=denied)
    require_listing = AsyncMock()
    monkeypatch.setattr(search_state, "enforce_listing_view_access", policy)
    monkeypatch.setattr(search_state, "require_listing", require_listing)

    with pytest.raises(HTTPException):
        await search_state.add_collection_item(Favorite, "uq_favorites_user_listing", listing_id, user, session)
    require_listing.assert_not_awaited()

    payload = SimpleNamespace(favoriteIds=[str(listing_id)], savedSearches=[])
    with pytest.raises(HTTPException):
        await search_state.import_guest_state(payload, user, session)

    assert policy.await_count == 2


def test_report_response_preserves_historical_listing_and_owner_context() -> None:
    listing_id = uuid4()
    owner_id = uuid4()
    report = SimpleNamespace(
        id=uuid4(),
        public_reference="R-HISTORY",
        listing_id=listing_id,
        reporter_id=None,
        reason="Historical report",
        comment="",
        status="open",
        handled_by=None,
        handled_at=None,
        created_at=datetime.now(UTC),
    )

    response = reports.public_report(
        report,
        owner_id,
        listing_title="Deleted listing title",
        owner_user_id=owner_id,
        owner_name="Deleted owner name",
    )

    assert response.listingTitle == "Deleted listing title"
    assert response.ownerUserId == owner_id
    assert response.ownerName == "Deleted owner name"
    assert response.targetUserId == owner_id
