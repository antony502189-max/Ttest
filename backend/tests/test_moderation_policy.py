from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.moderation import is_admin, normalize_email, restriction_error


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
