from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    AuthSession,
    EmailVerificationToken,
    ExternalImportRun,
    MailOutbox,
    PasswordResetToken,
    User,
)
from app.services.data_retention import prune_expired_records

pytestmark = pytest.mark.integration


async def test_retention_removes_only_old_completed_or_expired_records():
    now = datetime.now(UTC)
    async with SessionLocal() as setup:
        user = User(
            email="retention@example.test",
            password_hash=None,
            name="Retention",
            role="tenant",
            initials="R",
        )
        setup.add(user)
        await setup.flush()

        old_sent = MailOutbox(
            kind="new_message",
            recipient=user.email,
            subject="Old sent",
            body="old",
            status="sent",
            created_at=now - timedelta(days=31),
            sent_at=now - timedelta(days=31),
        )
        old_failed = MailOutbox(
            kind="new_message",
            recipient=user.email,
            subject="Old failed",
            body="old",
            status="failed",
            created_at=now - timedelta(days=31),
        )
        old_pending = MailOutbox(
            kind="new_message",
            recipient=user.email,
            subject="Old pending",
            body="must remain",
            status="pending",
            created_at=now - timedelta(days=31),
        )
        fresh_sent = MailOutbox(
            kind="new_message",
            recipient=user.email,
            subject="Fresh sent",
            body="fresh",
            status="sent",
            created_at=now - timedelta(days=1),
            sent_at=now - timedelta(days=1),
        )
        old_session = AuthSession(
            user_id=user.id,
            token_hash="a" * 64,
            expires_at=now - timedelta(days=8),
        )
        recent_expired_session = AuthSession(
            user_id=user.id,
            token_hash="b" * 64,
            expires_at=now - timedelta(days=1),
        )
        old_reset = PasswordResetToken(
            user_id=user.id,
            token_hash="c" * 64,
            expires_at=now - timedelta(days=8),
        )
        recent_reset = PasswordResetToken(
            user_id=user.id,
            token_hash="d" * 64,
            expires_at=now - timedelta(days=1),
        )
        old_verification = EmailVerificationToken(
            user_id=user.id,
            token_hash="e" * 64,
            expires_at=now - timedelta(days=8),
        )
        recent_verification = EmailVerificationToken(
            user_id=user.id,
            token_hash="f" * 64,
            expires_at=now - timedelta(days=1),
        )
        setup.add_all(
            [
                old_sent,
                old_failed,
                old_pending,
                fresh_sent,
                old_session,
                recent_expired_session,
                old_reset,
                recent_reset,
                old_verification,
                recent_verification,
            ]
        )
        await setup.commit()
        retained_ids = {
            old_pending.id,
            fresh_sent.id,
            recent_expired_session.id,
            recent_reset.id,
            recent_verification.id,
        }

    async with SessionLocal() as maintenance:
        counts = await prune_expired_records(maintenance, now=now, batch_size=100)

    assert counts == {
        "mail_outbox": 2,
        "auth_sessions": 1,
        "password_reset_tokens": 1,
        "email_verification_tokens": 1,
        "external_import_runs": 0,
    }

    async with SessionLocal() as check:
        remaining = set((await check.scalars(select(MailOutbox.id))).all())
        remaining.update((await check.scalars(select(AuthSession.id))).all())
        remaining.update((await check.scalars(select(PasswordResetToken.id))).all())
        remaining.update((await check.scalars(select(EmailVerificationToken.id))).all())
        assert remaining == retained_ids


async def test_retention_batch_size_is_enforced_per_table():
    now = datetime.now(UTC)
    async with SessionLocal() as setup:
        setup.add_all(
            [
                MailOutbox(
                    kind="new_message",
                    recipient=f"person-{index}@example.test",
                    subject="Completed",
                    body="old",
                    status="sent",
                    created_at=now - timedelta(days=31),
                    sent_at=now - timedelta(days=31),
                )
                for index in range(3)
            ]
        )
        await setup.commit()

    async with SessionLocal() as maintenance:
        counts = await prune_expired_records(maintenance, now=now, batch_size=1)
    assert counts["mail_outbox"] == 1

    async with SessionLocal() as check:
        assert len((await check.scalars(select(MailOutbox.id))).all()) == 2


async def test_external_import_retention_keeps_latest_success_and_active_backoff():
    now = datetime.now(UTC)
    old = now - timedelta(days=31)
    async with SessionLocal() as setup:
        older_success = ExternalImportRun(
            run_id="retention-older-success",
            source_name="idealista",
            started_at=old - timedelta(hours=1),
            finished_at=old - timedelta(hours=1),
            result="success",
            counters={"discovered_urls": 120},
        )
        latest_success = ExternalImportRun(
            run_id="retention-latest-success",
            source_name="idealista",
            started_at=old,
            finished_at=old,
            result="success",
            counters={"discovered_urls": 100},
        )
        old_failed = ExternalImportRun(
            run_id="retention-old-failed",
            source_name="idealista",
            started_at=old,
            finished_at=old,
            result="failed",
            last_error="old failure",
        )
        active_block = ExternalImportRun(
            run_id="retention-active-block",
            source_name="fotocasa",
            started_at=old,
            finished_at=old,
            result="blocked",
            next_check_at=now + timedelta(hours=1),
        )
        expired_block = ExternalImportRun(
            run_id="retention-expired-block",
            source_name="fotocasa",
            started_at=old,
            finished_at=old,
            result="blocked",
            next_check_at=now - timedelta(hours=1),
        )
        recent_failed = ExternalImportRun(
            run_id="retention-recent-failed",
            source_name="pisos",
            started_at=now - timedelta(days=1),
            finished_at=now - timedelta(days=1),
            result="failed",
        )
        setup.add_all(
            [
                older_success,
                latest_success,
                old_failed,
                active_block,
                expired_block,
                recent_failed,
            ]
        )
        await setup.commit()
        retained_ids = {latest_success.id, active_block.id, recent_failed.id}

    async with SessionLocal() as maintenance:
        counts = await prune_expired_records(maintenance, now=now, batch_size=100)
    assert counts["external_import_runs"] == 3

    async with SessionLocal() as check:
        remaining = set((await check.scalars(select(ExternalImportRun.id))).all())
        assert remaining == retained_ids
