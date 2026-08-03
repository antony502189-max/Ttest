from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models import MailOutbox
from app.services import mail

pytestmark = pytest.mark.integration


def mail_settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "smtp_host": "smtp.example.test",
        "smtp_timeout_seconds": 1,
        "mail_worker_batch_size": 2,
        "mail_max_attempts": 3,
        "mail_lease_seconds": 120,
        "mail_retry_base_seconds": 30,
        "mail_retry_max_seconds": 300,
    }
    values.update(overrides)
    return Settings(**values)


async def test_claim_commits_before_network_io_and_redacts_sensitive_mail(monkeypatch):
    settings = mail_settings()
    async with SessionLocal() as setup:
        setup.add(
            MailOutbox(
                kind="password_reset",
                recipient="person@example.test",
                subject="Reset",
                body="secret reset token",
            )
        )
        await setup.commit()

    async with SessionLocal() as session:
        network_observations: list[bool] = []

        def fake_send(*_args) -> None:
            return None

        async def inline_thread(function, *args):
            network_observations.append(session.in_transaction())
            return function(*args)

        monkeypatch.setattr(mail, "get_settings", lambda: settings)
        monkeypatch.setattr(mail, "send_smtp", fake_send)
        monkeypatch.setattr(mail.asyncio, "to_thread", inline_thread)

        assert await mail.deliver_pending_mail(session) == 1
        assert network_observations == [False]

    async with SessionLocal() as check:
        item = await check.scalar(select(MailOutbox))
        assert item is not None
        assert item.status == "sent"
        assert item.attempts == 1
        assert item.lease_token is None
        assert item.lease_expires_at is None
        assert item.body == mail.REDACTED_BODY


async def test_expired_lease_is_recoverable_but_active_lease_is_not():
    settings = mail_settings()
    async with SessionLocal() as setup:
        setup.add(
            MailOutbox(
                kind="new_message",
                recipient="person@example.test",
                subject="Message",
                body="New message",
            )
        )
        await setup.commit()

    async with SessionLocal() as first_session:
        first = await mail.claim_pending_mail(first_session, batch_size=1, settings=settings)
        assert len(first) == 1

    async with SessionLocal() as second_session:
        assert await mail.claim_pending_mail(second_session, batch_size=1, settings=settings) == []
        item = await second_session.get(MailOutbox, first[0].id)
        assert item is not None
        item.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await second_session.commit()
        recovered = await mail.claim_pending_mail(second_session, batch_size=1, settings=settings)
        assert len(recovered) == 1
        assert recovered[0].attempts == 2
        assert recovered[0].lease_token != first[0].lease_token


async def test_failed_delivery_uses_backoff_and_terminally_redacts_secret(monkeypatch):
    settings = mail_settings(mail_max_attempts=2)
    async with SessionLocal() as setup:
        setup.add(
            MailOutbox(
                kind="email_verification",
                recipient="person@example.test",
                subject="Verify",
                body="six digit secret",
            )
        )
        await setup.commit()

    def fail_send(*_args) -> None:
        raise OSError("smtp unavailable")

    async def inline_thread(function, *args):
        return function(*args)

    monkeypatch.setattr(mail, "get_settings", lambda: settings)
    monkeypatch.setattr(mail, "send_smtp", fail_send)
    monkeypatch.setattr(mail.asyncio, "to_thread", inline_thread)

    async with SessionLocal() as first:
        assert await mail.deliver_pending_mail(first) == 0

    async with SessionLocal() as inspect_first:
        item = await inspect_first.scalar(select(MailOutbox))
        assert item is not None
        assert item.status == "pending"
        assert item.attempts == 1
        assert item.next_attempt_at > datetime.now(UTC)
        assert item.body == "six digit secret"
        item.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        await inspect_first.commit()

    async with SessionLocal() as second:
        assert await mail.deliver_pending_mail(second) == 0

    async with SessionLocal() as inspect_second:
        item = await inspect_second.scalar(select(MailOutbox))
        assert item is not None
        assert item.status == "failed"
        assert item.attempts == 2
        assert item.lease_token is None
        assert item.body == mail.REDACTED_BODY
