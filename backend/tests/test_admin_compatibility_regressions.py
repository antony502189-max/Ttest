from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import dependencies
from app.api.v1 import reports as reports_api
from app.services import admin as admin_service
from app.services import admin_users


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
async def test_full_restriction_does_not_revoke_existing_identity_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    target = SimpleNamespace(id=uuid4(), email="restricted@example.com", deleted_at=None)
    actor = SimpleNamespace(id=uuid4())
    session = SimpleNamespace(
        get=AsyncMock(side_effect=[target, None]),
        scalars=AsyncMock(),
        add=MagicMock(),
        commit=AsyncMock(),
    )
    monkeypatch.setattr(admin_users, "active_user_restriction", AsyncMock(return_value=None))
    monkeypatch.setattr(admin_users, "touch_catalog", AsyncMock())
    monkeypatch.setattr(admin_users, "get_user_detail", AsyncMock(return_value="detail"))

    result = await admin_users.restrict_user(
        target.id,
        restriction_type="full",
        until=None,
        reason="Account suspended",
        actor=actor,
        session=session,
    )

    assert result == "detail"
    session.scalars.assert_not_awaited()
    session.commit.assert_awaited_once()


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


def test_forward_admin_repair_restores_only_allowlist_grants_and_permanent_listing_schema() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0039_admin_grant_repair_and_permanent_listing_restrictions.py"
    ).read_text(encoding="utf-8")

    assert 'REQUIRED_ADMIN_EMAILS = ("antony502189@gmail.com", "tf.shuler@gmail.com")' in migration
    assert "ON CONFLICT (email) DO UPDATE SET active = TRUE" in migration
    assert 'nullable=True' in migration
    assert "three-valued CHECK semantics" in migration
    assert "UPDATE users" not in migration


def test_deleted_admin_user_detail_is_rendered_read_only() -> None:
    admin_page = (Path(__file__).resolve().parents[2] / "src" / "pages" / "AdminPage.tsx").read_text(encoding="utf-8")

    assert 'const isDeleted = Boolean(user.deletedAt)' in admin_page
    assert '!isDeleted ? <div className="admin-user-actions">' in admin_page
    assert '!isDeleted ? <form className="admin-note-form"' in admin_page
    assert '!isDeleted ? <UserRestrictionDialog' in admin_page
    assert '!isDeleted ? <DeleteUserDialog' in admin_page
    assert 'La ficha se conserva únicamente como historial de moderación y es de solo lectura.' in admin_page


def test_admin_navigation_is_server_authorized_on_profile_and_mobile_menu() -> None:
    project_root = Path(__file__).resolve().parents[2]
    hook = (project_root / "src" / "hooks" / "use-admin-access.ts").read_text(encoding="utf-8")
    layout = (project_root / "src" / "components" / "layout.tsx").read_text(encoding="utf-8")
    mobile_menu = (project_root / "src" / "components" / "mobile-app-v2.tsx").read_text(encoding="utf-8")
    profile = (project_root / "src" / "pages" / "ProfilePage.tsx").read_text(encoding="utf-8")
    app = (project_root / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "checkAdminAccess()" in hook
    assert "if (mockMode)" in hook
    assert "setState(productRole === 'admin' ? 'allowed' : 'denied')" in hook
    assert "GOOGLE_IDENTITY_REQUIRED" in hook

    assert 'to="/admin"' not in layout
    assert "useAdminAccess" not in layout
    assert "useAdminAccess" in mobile_menu
    assert "adminAllowed ?" in mobile_menu
    assert "onAdmin={() => navigate('/admin')}" in mobile_menu
    assert "Перейти в админ-панель" in mobile_menu
    assert "Open administration panel" in mobile_menu
    assert "Abrir panel de administración" in mobile_menu

    assert "const adminAccess = useAdminAccessState()" in profile
    assert "adminAccess === 'allowed'" in profile
    assert "linkGoogle: true" in profile
    assert "navigate('/admin')" in profile
    assert "Abrir panel de administración" in profile
    assert 'className="m2-account-admin"' in profile
    assert 'className="container profile-admin-entry"' in profile

    assert "<ProtectedRoute admin>" in app
    assert "checkAdminAccess()" in app


def test_admin_allowlist_grant_does_not_change_product_role() -> None:
    project_root = Path(__file__).resolve().parents[2]
    admin_service_source = (
        project_root / "backend" / "app" / "services" / "admin.py"
    ).read_text(encoding="utf-8")
    add_admin_body = admin_service_source.split("async def add_admin(", 1)[1].split("async def revoke_admin(", 1)[0]

    assert "AdminAccess(" in add_admin_body
    assert "target.role" not in add_admin_body
    assert ".role =" not in add_admin_body
