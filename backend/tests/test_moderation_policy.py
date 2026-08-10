from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.repositories.listings import visible_query
from app.services import listings as listings_service
from app.services import moderation
from app.services.moderation import (
    enforce_full_access,
    enforce_listing_view_access,
    enforce_publish_access,
    is_admin,
    normalize_email,
    restriction_error,
    restriction_period_text,
)


def test_normalize_email_is_case_and_whitespace_insensitive() -> None:
    assert normalize_email("  Antony502189@GMAIL.COM  ") == "antony502189@gmail.com"


@pytest.mark.asyncio
async def test_admin_access_requires_google_link_and_active_allowlist() -> None:
    session = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(active=True)))
    user = SimpleNamespace(email="tf.shuler@gmail.com", google_subject=None)

    assert await is_admin(user, session) is False
    session.get.assert_not_awaited()

    user.google_subject = "google-subject"
    assert await is_admin(user, session) is True
    session.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_inactive_allowlist_entry_is_not_admin() -> None:
    session = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(active=False)))
    user = SimpleNamespace(email="antony502189@gmail.com", google_subject="google-subject")

    assert await is_admin(user, session) is False


def test_restriction_error_exposes_reason_expiry_and_support_address() -> None:
    restriction = SimpleNamespace(
        restriction_type="publish",
        reason="Repeated spam",
        ends_at=SimpleNamespace(isoformat=lambda: "2026-08-20T12:00:00+00:00"),
    )

    error = restriction_error(restriction, code="PUBLISHING_RESTRICTED")

    assert error.status_code == 403
    assert error.detail["code"] == "PUBLISHING_RESTRICTED"
    assert error.detail["restriction"] == {
        "type": "publish",
        "reason": "Repeated spam",
        "until": "2026-08-20T12:00:00+00:00",
        "supportEmail": "tf.shuler@gmail.com",
    }


def test_permanent_restriction_has_no_fake_expiry() -> None:
    restriction = SimpleNamespace(
        restriction_type="full",
        reason="Permanent moderation decision",
        ends_at=None,
    )

    error = restriction_error(restriction, code="ACCOUNT_RESTRICTED")

    assert error.detail["restriction"]["until"] is None
    assert restriction_period_text(None) == "de forma indefinida"


def test_public_listing_visibility_includes_permanent_user_restrictions() -> None:
    sql = str(visible_query())
    assert "user_restrictions.ends_at IS NULL" in sql
    assert "user_restrictions.ends_at > now()" in sql


@pytest.mark.asyncio
async def test_revoked_legacy_admin_role_cannot_mutate_other_users_listings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id="legacy-admin", role="admin")
    listing = SimpleNamespace(owner_user_id="owner")
    session = SimpleNamespace()
    allowlist_check = AsyncMock(return_value=False)
    monkeypatch.setattr(listings_service, "is_admin", allowlist_check)

    with pytest.raises(HTTPException) as exc:
        await listings_service.ensure_owner_or_admin(listing, user, session)

    assert exc.value.status_code == 403
    allowlist_check.assert_awaited_once_with(user, session)


@pytest.mark.asyncio
async def test_allowlisted_admin_can_mutate_other_users_listings(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id="admin", role="tenant")
    listing = SimpleNamespace(owner_user_id="owner")
    session = SimpleNamespace()
    monkeypatch.setattr(listings_service, "is_admin", AsyncMock(return_value=True))

    assert await listings_service.ensure_owner_or_admin(listing, user, session) is True


@pytest.mark.asyncio
async def test_publish_restriction_blocks_publication_but_allows_listing_view(monkeypatch: pytest.MonkeyPatch) -> None:
    restriction = SimpleNamespace(
        restriction_type="publish",
        reason="Publication suspended",
        ends_at=SimpleNamespace(isoformat=lambda: "2026-08-20T12:00:00+00:00"),
    )
    active = AsyncMock(return_value=restriction)
    monkeypatch.setattr(moderation, "active_user_restriction", active)
    user = SimpleNamespace(id="user-id")
    session = SimpleNamespace()

    with pytest.raises(HTTPException) as exc:
        await enforce_publish_access(user, session)
    assert exc.value.detail["code"] == "PUBLISHING_RESTRICTED"

    await enforce_listing_view_access(user, session)


@pytest.mark.asyncio
async def test_view_restriction_blocks_listing_view_but_not_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    restriction = SimpleNamespace(
        restriction_type="view_listings",
        reason="Listing access suspended",
        ends_at=SimpleNamespace(isoformat=lambda: "2026-08-20T12:00:00+00:00"),
    )
    active = AsyncMock(return_value=restriction)
    monkeypatch.setattr(moderation, "active_user_restriction", active)
    user = SimpleNamespace(id="user-id")
    session = SimpleNamespace()

    with pytest.raises(HTTPException) as exc:
        await enforce_listing_view_access(user, session)
    assert exc.value.detail["code"] == "LISTING_ACCESS_RESTRICTED"

    await enforce_publish_access(user, session)


@pytest.mark.asyncio
async def test_full_restriction_blocks_normal_application_policies(monkeypatch: pytest.MonkeyPatch) -> None:
    restriction = SimpleNamespace(
        restriction_type="full",
        reason="Account suspended",
        ends_at=None,
    )
    active = AsyncMock(return_value=restriction)
    monkeypatch.setattr(moderation, "active_user_restriction", active)
    user = SimpleNamespace(id="user-id")
    session = SimpleNamespace()

    for policy in (enforce_full_access, enforce_publish_access, enforce_listing_view_access):
        with pytest.raises(HTTPException) as exc:
            await policy(user, session)
        assert exc.value.status_code == 403
        assert exc.value.detail["restriction"]["reason"] == "Account suspended"
