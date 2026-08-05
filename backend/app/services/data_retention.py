from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    AuthSession,
    EmailVerificationToken,
    ExternalImportRun,
    MailOutbox,
    PasswordResetToken,
)

MAIL_OUTBOX_RETENTION_DAYS = 30
SECURITY_RECORD_RETENTION_DAYS = 7
EXTERNAL_IMPORT_RUN_RETENTION_DAYS = 30
RETENTION_BATCH_SIZE = 1_000
RETENTION_RUN_INTERVAL = timedelta(hours=1)


async def _delete_selected_ids(
    session: AsyncSession,
    model: Any,
    id_query: Any,
) -> int:
    ids = list((await session.scalars(id_query)).all())
    if not ids:
        return 0
    await session.execute(delete(model).where(model.id.in_(ids)))
    return len(ids)


def old_external_import_run_ids(current: datetime, cutoff: datetime, batch_size: int):
    """Select disposable history while preserving importer state-machine inputs."""
    # Reconciliation compares discovery volume with the most recent successful
    # run for each source. Keep that baseline even if a source has been blocked
    # or offline longer than the normal history-retention window.
    latest_success_ids = (
        select(ExternalImportRun.id)
        .where(
            ExternalImportRun.result == "success",
            ExternalImportRun.finished_at.is_not(None),
        )
        .distinct(ExternalImportRun.source_name)
        .order_by(
            ExternalImportRun.source_name,
            ExternalImportRun.finished_at.desc(),
            ExternalImportRun.id.desc(),
        )
    )
    return (
        select(ExternalImportRun.id)
        .where(
            ExternalImportRun.finished_at.is_not(None),
            ExternalImportRun.finished_at <= cutoff,
            ExternalImportRun.id.not_in(latest_success_ids),
            or_(
                ExternalImportRun.result != "blocked",
                ExternalImportRun.next_check_at.is_(None),
                ExternalImportRun.next_check_at <= current,
            ),
        )
        .order_by(ExternalImportRun.finished_at, ExternalImportRun.id)
        .limit(batch_size)
    )


async def prune_expired_records(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    batch_size: int = RETENTION_BATCH_SIZE,
) -> dict[str, int]:
    """Delete only records that have no remaining runtime or security value.

    Work is deliberately bounded per table so a long-neglected deployment does
    not turn one maintenance pass into an unbounded transaction. Subsequent
    hourly passes continue draining any backlog.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    current = now or datetime.now(UTC)
    mail_cutoff = current - timedelta(days=MAIL_OUTBOX_RETENTION_DAYS)
    security_cutoff = current - timedelta(days=SECURITY_RECORD_RETENTION_DAYS)
    external_run_cutoff = current - timedelta(days=EXTERNAL_IMPORT_RUN_RETENTION_DAYS)

    counts = {
        "mail_outbox": await _delete_selected_ids(
            session,
            MailOutbox,
            select(MailOutbox.id)
            .where(
                MailOutbox.status.in_(("sent", "failed")),
                MailOutbox.created_at <= mail_cutoff,
            )
            .order_by(MailOutbox.created_at, MailOutbox.id)
            .limit(batch_size),
        ),
        "auth_sessions": await _delete_selected_ids(
            session,
            AuthSession,
            select(AuthSession.id)
            .where(AuthSession.expires_at <= security_cutoff)
            .order_by(AuthSession.expires_at, AuthSession.id)
            .limit(batch_size),
        ),
        "password_reset_tokens": await _delete_selected_ids(
            session,
            PasswordResetToken,
            select(PasswordResetToken.id)
            .where(PasswordResetToken.expires_at <= security_cutoff)
            .order_by(PasswordResetToken.expires_at, PasswordResetToken.id)
            .limit(batch_size),
        ),
        "email_verification_tokens": await _delete_selected_ids(
            session,
            EmailVerificationToken,
            select(EmailVerificationToken.id)
            .where(EmailVerificationToken.expires_at <= security_cutoff)
            .order_by(EmailVerificationToken.expires_at, EmailVerificationToken.id)
            .limit(batch_size),
        ),
        "external_import_runs": await _delete_selected_ids(
            session,
            ExternalImportRun,
            old_external_import_run_ids(current, external_run_cutoff, batch_size),
        ),
    }
    await session.commit()
    return counts
