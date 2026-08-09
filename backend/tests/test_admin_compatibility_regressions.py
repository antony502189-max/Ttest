from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1 import reports as reports_api


@pytest.mark.asyncio
async def test_report_creation_enforces_listing_view_policy_before_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=uuid4())
    session = SimpleNamespace()
    payload = SimpleNamespace(listingId=uuid4(), targetType="listing", reason="spam", comment="")
    policy = AsyncMock(side_effect=HTTPException(403, "view restricted"))
    create = AsyncMock()
    monkeypatch.setattr(reports_api, "enforce_listing_view_access", policy)
    monkeypatch.setattr(reports_api, "create_report", create)

    with pytest.raises(HTTPException) as exc:
        await reports_api.create_report_route(payload, user, session)

    assert exc.value.status_code == 403
    policy.assert_awaited_once_with(user, session)
    create.assert_not_awaited()


def test_admin_migration_converts_legacy_blocked_accounts_to_new_restrictions() -> None:
    migration = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0033_admin_moderation.py"
    ).read_text(encoding="utf-8")

    assert 'SELECT id FROM users WHERE blocked IS TRUE' in migration
    assert "'full'" in migration
    assert 'LEGACY_BLOCK_MIGRATION_REASON = "Migrated from legacy blocked account"' in migration
    assert 'UPDATE users SET blocked = FALSE WHERE blocked IS TRUE' in migration
    assert 'SET blocked = TRUE' in migration
    assert 'AND revoked_at IS NULL' in migration
