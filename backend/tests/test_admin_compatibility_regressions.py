from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import dependencies
from app.api.v1 import reports as reports_api
from app.services import admin as admin_service


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


@pytest.mark.asyncio
async def test_admin_authorization_enforces_full_access_before_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=uuid4())
    session = SimpleNamespace()
    full_access = AsyncMock(side_effect=HTTPException(403, "full restriction"))
    admin_check = AsyncMock(return_value=True)
    monkeypatch.setattr(dependencies, "enforce_full_access", full_access)
    monkeypatch.setattr(dependencies, "is_admin", admin_check)

    with pytest.raises(HTTPException) as exc:
        await dependencies.require_admin(user, session)

    assert exc.value.status_code == 403
    full_access.assert_awaited_once_with(user, session)
    admin_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_protected_user_policy_remains_enforced_after_identity_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=uuid4())
    session = SimpleNamespace()
    full_access = AsyncMock(side_effect=HTTPException(403, "full restriction"))
    monkeypatch.setattr(dependencies, "enforce_full_access", full_access)

    with pytest.raises(HTTPException) as exc:
        await dependencies.current_user(user, session)

    assert exc.value.status_code == 403
    full_access.assert_awaited_once_with(user, session)


def test_auth_router_preserves_identity_session_for_restriction_ux() -> None:
    auth_source = (Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "auth.py").read_text(encoding="utf-8")

    assert "enforce_session_moderation" not in auth_source
    assert "from ...services.moderation import enforce_full_access" not in auth_source
    assert "@router.post(\"/refresh\")" in auth_source
    assert "return set_refresh_cookie(response, result)" in auth_source
    assert "ModerationGate" in auth_source


@pytest.mark.asyncio
async def test_admin_note_locks_user_before_deleted_check() -> None:
    user_id = uuid4()
    actor = SimpleNamespace(id=uuid4(), name="Admin")
    deleted = SimpleNamespace(id=user_id, deleted_at=object())
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=deleted),
        add=MagicMock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
    )

    with pytest.raises(HTTPException) as exc:
        await admin_service.add_note(user_id, "historical write", actor, session)

    assert exc.value.status_code == 404
    statement = str(session.scalar.await_args.args[0])
    assert "FROM users" in statement
    assert "FOR UPDATE" in statement
    session.add.assert_not_called()
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_admin_migration_converts_legacy_blocks_and_skips_their_admin_seed() -> None:
    migration = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0033_admin_moderation.py"
    ).read_text(encoding="utf-8")

    assert 'SELECT id, lower(email) AS email FROM users WHERE blocked IS TRUE' in migration
    assert "'full'" in migration
    assert 'LEGACY_BLOCK_MIGRATION_REASON = "Migrated from legacy blocked account"' in migration
    assert 'UPDATE users SET blocked = FALSE WHERE blocked IS TRUE' in migration
    assert 'email.lower() not in legacy_blocked_emails' in migration
    assert 'SET blocked = TRUE' in migration
    assert 'AND revoked_at IS NULL' in migration
    assert 'AND (ends_at IS NULL OR ends_at > now())' in migration


def test_deleted_admin_user_detail_is_rendered_read_only() -> None:
    admin_page = (Path(__file__).resolve().parents[2] / "src" / "pages" / "AdminPage.tsx").read_text(encoding="utf-8")

    assert 'const isDeleted = Boolean(user.deletedAt)' in admin_page
    assert '!isDeleted ? <div className="admin-user-actions">' in admin_page
    assert '!isDeleted ? <form className="admin-note-form"' in admin_page
    assert '!isDeleted ? <UserRestrictionDialog' in admin_page
    assert '!isDeleted ? <DeleteUserDialog' in admin_page
    assert 'La ficha se conserva únicamente como historial de moderación y es de solo lectura.' in admin_page
