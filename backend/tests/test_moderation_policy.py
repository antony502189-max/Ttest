from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
import pytest

from app.api.v1 import auth as auth_api
from app.services import moderation
from app.services.moderation import (
    enforce_listing_view_access,
    enforce_publish_access,
    is_admin,
    normalize_email,
    restriction_error,
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
async def test_full_restriction_revokes_newly_issued_login_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace()
    result = SimpleNamespace(user=SimpleNamespace(id="user-id"), refresh_token="new-refresh-token")
    blocked = HTTPException(403, detail={"code": "ACCOUNT_RESTRICTED"})
    enforce = AsyncMock(side_effect=blocked)
    revoke = AsyncMock()
    monkeypatch.setattr(auth_api, "enforce_full_access", enforce)
    monkeypatch.setattr(auth_api, "revoke_session", revoke)

    with pytest.raises(HTTPException) as exc:
        await auth_api.enforce_session_moderation(result, session)

    assert exc.value is blocked
    revoke.assert_awaited_once_with("new-refresh-token", session)


@pytest.mark.asyncio
async def test_non_full_login_session_is_not_revoked(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace()
    result = SimpleNamespace(user=SimpleNamespace(id="user-id"), refresh_token="new-refresh-token")
    enforce = AsyncMock(return_value=None)
    revoke = AsyncMock()
    monkeypatch.setattr(auth_api, "enforce_full_access", enforce)
    monkeypatch.setattr(auth_api, "revoke_session", revoke)

    await auth_api.enforce_session_moderation(result, session)

    revoke.assert_not_awaited()
