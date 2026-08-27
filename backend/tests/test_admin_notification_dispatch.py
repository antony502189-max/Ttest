from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.services.admin as admin_service


def listing(status: str):
    return SimpleNamespace(
        id=uuid4(),
        owner_user_id=uuid4(),
        title="Customer delivery listing",
        city="Adeje",
        area="Centro",
        status=status,
        rental_mode="long",
        views=0,
        created_at=datetime.now(UTC),
        deleted_at=None,
        published_at=None,
        closed_reason=None,
    )


def owner(listing_owner_id):
    return SimpleNamespace(
        id=listing_owner_id,
        name="Listing owner",
        email="owner@example.test",
        email_verified=True,
    )


def session_stub():
    return SimpleNamespace(
        add=MagicMock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        scalar=AsyncMock(return_value=None),
    )


@pytest.mark.asyncio
async def test_admin_publish_dispatches_saved_search_and_owner_notifications(monkeypatch) -> None:
    row = listing("pending")
    recipient = owner(row.owner_user_id)
    session = session_stub()

    monkeypatch.setattr(admin_service, "_actionable_listing", AsyncMock(return_value=(row, recipient)))
    monkeypatch.setattr(admin_service, "active_listing_restriction", AsyncMock(return_value=None))
    monkeypatch.setattr(admin_service, "active_user_restriction", AsyncMock(return_value=None))
    monkeypatch.setattr(admin_service, "touch_catalog", AsyncMock())
    create_notification = AsyncMock(return_value=True)
    saved_search = AsyncMock()
    favorite_unavailable = AsyncMock()
    monkeypatch.setattr(admin_service, "create_notification", create_notification)
    monkeypatch.setattr(admin_service, "notify_saved_search_matches", saved_search)
    monkeypatch.setattr(admin_service, "notify_favorited_listing_unavailable", favorite_unavailable)

    result = await admin_service.change_listing_status(row.id, "published", SimpleNamespace(id=uuid4()), session)

    assert result.status == "published"
    create_notification.assert_awaited_once()
    assert create_notification.await_args.kwargs["recipient"] is recipient
    assert create_notification.await_args.kwargs["kind"] == "listing_published"
    saved_search.assert_awaited_once_with(session, row)
    favorite_unavailable.assert_not_awaited()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_status_change_preserves_existing_promotion_metadata(monkeypatch) -> None:
    row = listing("pending")
    recipient = owner(row.owner_user_id)
    session = session_stub()
    promotion = SimpleNamespace(boosted_at=datetime.now(UTC))
    session.scalar.return_value = promotion

    monkeypatch.setattr(admin_service, "_actionable_listing", AsyncMock(return_value=(row, recipient)))
    monkeypatch.setattr(admin_service, "active_listing_restriction", AsyncMock(return_value=None))
    monkeypatch.setattr(admin_service, "active_user_restriction", AsyncMock(return_value=None))
    monkeypatch.setattr(admin_service, "touch_catalog", AsyncMock())
    monkeypatch.setattr(admin_service, "create_notification", AsyncMock(return_value=True))
    monkeypatch.setattr(admin_service, "notify_saved_search_matches", AsyncMock())

    result = await admin_service.change_listing_status(row.id, "published", SimpleNamespace(id=uuid4()), session)

    assert result.promoted is True
    assert result.boostedAt == promotion.boosted_at


@pytest.mark.asyncio
async def test_admin_hiding_public_listing_dispatches_favorite_unavailable_once(monkeypatch) -> None:
    row = listing("published")
    row.published_at = datetime.now(UTC)
    recipient = owner(row.owner_user_id)
    session = session_stub()

    monkeypatch.setattr(admin_service, "_actionable_listing", AsyncMock(return_value=(row, recipient)))
    monkeypatch.setattr(admin_service, "active_listing_restriction", AsyncMock(return_value=None))
    monkeypatch.setattr(admin_service, "touch_catalog", AsyncMock())
    monkeypatch.setattr(admin_service, "create_notification", AsyncMock(return_value=True))
    saved_search = AsyncMock()
    favorite_unavailable = AsyncMock()
    monkeypatch.setattr(admin_service, "notify_saved_search_matches", saved_search)
    monkeypatch.setattr(admin_service, "notify_favorited_listing_unavailable", favorite_unavailable)

    result = await admin_service.change_listing_status(row.id, "hidden", SimpleNamespace(id=uuid4()), session)

    assert result.status == "hidden"
    saved_search.assert_not_awaited()
    favorite_unavailable.assert_awaited_once()
    assert favorite_unavailable.await_args.args[:2] == (session, row)
    assert favorite_unavailable.await_args.kwargs["event_key"]


@pytest.mark.asyncio
async def test_admin_noop_status_does_not_emit_duplicate_product_alerts(monkeypatch) -> None:
    row = listing("published")
    row.published_at = datetime.now(UTC)
    recipient = owner(row.owner_user_id)
    session = session_stub()

    monkeypatch.setattr(admin_service, "_actionable_listing", AsyncMock(return_value=(row, recipient)))
    monkeypatch.setattr(admin_service, "active_listing_restriction", AsyncMock(return_value=None))
    touch_catalog = AsyncMock()
    create_notification = AsyncMock()
    saved_search = AsyncMock()
    favorite_unavailable = AsyncMock()
    monkeypatch.setattr(admin_service, "touch_catalog", touch_catalog)
    monkeypatch.setattr(admin_service, "create_notification", create_notification)
    monkeypatch.setattr(admin_service, "notify_saved_search_matches", saved_search)
    monkeypatch.setattr(admin_service, "notify_favorited_listing_unavailable", favorite_unavailable)

    await admin_service.change_listing_status(row.id, "published", SimpleNamespace(id=uuid4()), session)

    create_notification.assert_not_awaited()
    saved_search.assert_not_awaited()
    favorite_unavailable.assert_not_awaited()
    touch_catalog.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_cannot_publish_a_listing_while_it_is_moderation_restricted(monkeypatch) -> None:
    row = listing("pending")
    recipient = owner(row.owner_user_id)
    session = session_stub()
    restriction = SimpleNamespace(id=uuid4())

    monkeypatch.setattr(admin_service, "_actionable_listing", AsyncMock(return_value=(row, recipient)))
    monkeypatch.setattr(admin_service, "active_listing_restriction", AsyncMock(return_value=restriction))
    monkeypatch.setattr(admin_service, "active_user_restriction", AsyncMock(return_value=None))
    create_notification = AsyncMock()
    saved_search = AsyncMock()
    monkeypatch.setattr(admin_service, "create_notification", create_notification)
    monkeypatch.setattr(admin_service, "notify_saved_search_matches", saved_search)

    with pytest.raises(HTTPException) as error:
        await admin_service.change_listing_status(row.id, "published", SimpleNamespace(id=uuid4()), session)

    assert error.value.status_code == 409
    assert error.value.detail["code"] == "PUBLICATION_RESTRICTED"
    assert row.status == "pending"
    create_notification.assert_not_awaited()
    saved_search.assert_not_awaited()
    session.commit.assert_not_awaited()
