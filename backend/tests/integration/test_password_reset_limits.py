from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models import MailOutbox, PasswordResetToken, User
from app.services import auth, mail

pytestmark = pytest.mark.integration
GENERIC_RESPONSE = {
    "message": "If the account exists, password reset instructions have been sent."
}


def reset_settings() -> Settings:
    return Settings(
        app_env="production",
        frontend_app_url="https://app.example.test",
        password_reset_minutes=30,
    )


async def create_user(email: str) -> User:
    async with SessionLocal() as session:
        user = User(
            email=email,
            password_hash="unused",
            name="Password Reset Test",
            role="tenant",
            initials="PR",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def request_once(email: str) -> dict[str, str]:
    async with SessionLocal() as session:
        return await auth.request_password_reset(email, session)


async def test_concurrent_reset_requests_create_only_one_token_and_email(monkeypatch):
    settings = reset_settings()
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(mail, "get_settings", lambda: settings)
    user = await create_user("reset-race@example.test")

    responses = await asyncio.gather(
        request_once(user.email),
        request_once(user.email),
    )
    assert responses == [GENERIC_RESPONSE, GENERIC_RESPONSE]

    async with SessionLocal() as check:
        token_count = await check.scalar(
            select(func.count())
            .select_from(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id)
        )
        mail_count = await check.scalar(
            select(func.count())
            .select_from(MailOutbox)
            .where(
                MailOutbox.kind == "password_reset",
                MailOutbox.recipient == user.email,
            )
        )
        assert token_count == 1
        assert mail_count == 1


async def test_hourly_reset_quota_is_silent_and_non_enumerating(monkeypatch):
    settings = reset_settings()
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(mail, "get_settings", lambda: settings)
    user = await create_user("reset-hourly@example.test")
    now = datetime.now(UTC)

    async with SessionLocal() as setup:
        setup.add_all(
            [
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=f"{index + 1:064x}",
                    expires_at=now + timedelta(minutes=30),
                    consumed_at=now - timedelta(minutes=1),
                    created_at=now - timedelta(minutes=10 + index * 5),
                )
                for index in range(auth.MAX_PASSWORD_RESETS_PER_HOUR)
            ]
        )
        await setup.commit()

    limited = await request_once(user.email)
    unknown = await request_once("missing-reset-account@example.test")
    assert limited == unknown == GENERIC_RESPONSE

    async with SessionLocal() as check:
        token_count = await check.scalar(
            select(func.count())
            .select_from(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id)
        )
        mail_count = await check.scalar(
            select(func.count())
            .select_from(MailOutbox)
            .where(
                MailOutbox.kind == "password_reset",
                MailOutbox.recipient == user.email,
            )
        )
        assert token_count == auth.MAX_PASSWORD_RESETS_PER_HOUR
        assert mail_count == 0


async def test_forgot_password_response_does_not_enumerate_unknown_blocked_or_deleted_accounts(monkeypatch):
    settings = reset_settings()
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(mail, "get_settings", lambda: settings)

    active = await create_user("reset-active@example.test")
    blocked = await create_user("reset-blocked@example.test")
    deleted = await create_user("reset-deleted@example.test")

    async with SessionLocal() as session:
        blocked_row = await session.get(User, blocked.id)
        deleted_row = await session.get(User, deleted.id)
        assert blocked_row is not None and deleted_row is not None
        blocked_row.blocked = True
        deleted_row.deleted_at = datetime.now(UTC)
        await session.commit()

    active_response = await request_once(active.email)
    unknown_response = await request_once("reset-missing@example.test")
    blocked_response = await request_once(blocked.email)
    deleted_response = await request_once(deleted.email)

    assert active_response == unknown_response == blocked_response == deleted_response == GENERIC_RESPONSE

    async with SessionLocal() as check:
        token_users = set((await check.scalars(select(PasswordResetToken.user_id))).all())
        mail_recipients = set(
            (
                await check.scalars(
                    select(MailOutbox.recipient).where(MailOutbox.kind == "password_reset")
                )
            ).all()
        )
    assert token_users == {active.id}
    assert mail_recipients == {active.email}
