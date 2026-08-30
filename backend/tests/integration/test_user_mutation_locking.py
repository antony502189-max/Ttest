from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import SearchHistory, User
from app.schemas.auth import UserUpdateRequest
from app.services.search_state import add_history
from app.services.users import update_profile

pytestmark = pytest.mark.integration


async def test_profile_update_cannot_restore_pii_after_concurrent_account_deletion(
    client,
    register_user,
) -> None:
    """A stale request-scoped User must not overwrite deletion anonymization."""
    _token, body = await register_user(
        client,
        email="profile-delete-race@example.com",
        role="host",
    )
    user_id = UUID(body["id"])

    async with SessionLocal() as update_session, SessionLocal() as delete_session:
        stale_user = await update_session.get(User, user_id)
        assert stale_user is not None
        assert stale_user.deleted_at is None

        deleting_user = await delete_session.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )
        assert deleting_user is not None

        update_task = asyncio.create_task(
            update_profile(
                UserUpdateRequest(
                    name="PII must not return",
                    phone="+34 600 000 000",
                    about="stale profile write",
                ),
                stale_user,
                update_session,
            )
        )

        now = datetime.now(UTC)
        deleting_user.deleted_at = now
        deleting_user.blocked = True
        deleting_user.email_verified = False
        deleting_user.email = f"deleted-{deleting_user.id}@deleted.invalid"
        deleting_user.name = "Deleted user"
        deleting_user.phone = ""
        deleting_user.whatsapp = ""
        deleting_user.telegram = ""
        deleting_user.about = ""
        deleting_user.show_phone = False
        deleting_user.show_whatsapp = False
        await delete_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await asyncio.wait_for(update_task, timeout=5)
        assert exc_info.value.status_code == 404
        await update_session.rollback()

    async with SessionLocal() as verify_session:
        row = await verify_session.get(User, user_id)
        assert row is not None
        assert row.deleted_at is not None
        assert row.name == "Deleted user"
        assert row.phone == ""
        assert row.about == ""


async def test_search_state_write_cannot_reappear_after_concurrent_account_deletion(
    client,
    register_user,
) -> None:
    """Soft-deleted users must not regain durable state from a stale request."""
    _token, body = await register_user(
        client,
        email="search-state-delete-race@example.com",
        role="tenant",
    )
    user_id = UUID(body["id"])

    async with SessionLocal() as state_session, SessionLocal() as delete_session:
        stale_user = await state_session.get(User, user_id)
        assert stale_user is not None

        deleting_user = await delete_session.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )
        assert deleting_user is not None

        state_task = asyncio.create_task(
            add_history("must not survive account deletion", stale_user, state_session)
        )

        deleting_user.deleted_at = datetime.now(UTC)
        deleting_user.blocked = True
        await delete_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await asyncio.wait_for(state_task, timeout=5)
        assert exc_info.value.status_code == 404
        await state_session.rollback()

    async with SessionLocal() as verify_session:
        history_id = await verify_session.scalar(
            select(SearchHistory.id).where(SearchHistory.user_id == user_id)
        )
        assert history_id is None
