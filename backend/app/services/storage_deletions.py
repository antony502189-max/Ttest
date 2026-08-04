from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.storage_deletion import StorageDeletionJob
from ..storage import get_storage

logger = logging.getLogger(__name__)
STORAGE_DELETION_BATCH_SIZE = 50
STORAGE_DELETION_LEASE_SECONDS = 900
STORAGE_DELETION_RETRY_BASE_SECONDS = 30
STORAGE_DELETION_RETRY_MAX_SECONDS = 86_400


@dataclass(frozen=True)
class ClaimedStorageDeletion:
    id: UUID
    storage_key: str
    lease_token: str
    attempts: int


def retry_delay_seconds(attempts: int) -> int:
    exponent = min(20, max(0, attempts - 1))
    return min(STORAGE_DELETION_RETRY_MAX_SECONDS, STORAGE_DELETION_RETRY_BASE_SECONDS * (2**exponent))


async def enqueue_storage_deletion(session: AsyncSession, storage_key: str) -> None:
    """Idempotently persist deletion intent in the caller's current transaction."""
    if not storage_key:
        return
    await session.execute(
        pg_insert(StorageDeletionJob)
        .values(storage_key=storage_key)
        .on_conflict_do_nothing(index_elements=[StorageDeletionJob.storage_key])
    )


async def enqueue_storage_deletions(session: AsyncSession, storage_keys: list[str] | set[str]) -> None:
    for storage_key in sorted(set(storage_keys)):
        await enqueue_storage_deletion(session, storage_key)


async def claim_storage_deletions(
    session: AsyncSession,
    *,
    batch_size: int = STORAGE_DELETION_BATCH_SIZE,
) -> list[ClaimedStorageDeletion]:
    """Lease a bounded batch and release row locks before object-storage I/O."""
    now = datetime.now(UTC)
    lease_token = str(uuid4())
    jobs = (
        await session.scalars(
            select(StorageDeletionJob)
            .where(
                StorageDeletionJob.next_attempt_at <= now,
                or_(
                    StorageDeletionJob.lease_expires_at.is_(None),
                    StorageDeletionJob.lease_expires_at <= now,
                ),
            )
            .order_by(StorageDeletionJob.next_attempt_at, StorageDeletionJob.created_at, StorageDeletionJob.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    ).all()
    lease_expires_at = now + timedelta(seconds=STORAGE_DELETION_LEASE_SECONDS)
    claims: list[ClaimedStorageDeletion] = []
    for job in jobs:
        job.attempts += 1
        job.lease_token = lease_token
        job.lease_expires_at = lease_expires_at
        claims.append(
            ClaimedStorageDeletion(
                id=job.id,
                storage_key=job.storage_key,
                lease_token=lease_token,
                attempts=job.attempts,
            )
        )
    await session.commit()
    return claims


async def finalize_storage_deletion(
    session: AsyncSession,
    claim: ClaimedStorageDeletion,
    *,
    deleted: bool,
    error: str | None = None,
) -> bool:
    """Finalize only a lease that is still owned by this worker."""
    if deleted:
        result = await session.execute(
            delete(StorageDeletionJob)
            .where(
                StorageDeletionJob.id == claim.id,
                StorageDeletionJob.lease_token == claim.lease_token,
            )
            .returning(StorageDeletionJob.id)
        )
    else:
        result = await session.execute(
            update(StorageDeletionJob)
            .where(
                StorageDeletionJob.id == claim.id,
                StorageDeletionJob.lease_token == claim.lease_token,
            )
            .values(
                lease_token=None,
                lease_expires_at=None,
                last_error=(error or "storage deletion failed")[:2_000],
                next_attempt_at=datetime.now(UTC) + timedelta(seconds=retry_delay_seconds(claim.attempts)),
            )
            .returning(StorageDeletionJob.id)
        )
    updated_id = result.scalar_one_or_none()
    await session.commit()
    return updated_id is not None


async def process_storage_deletions(
    session: AsyncSession,
    *,
    limit: int = STORAGE_DELETION_BATCH_SIZE,
) -> dict[str, int]:
    claims = await claim_storage_deletions(session, batch_size=limit)
    storage = get_storage()
    deleted_count = 0
    failed_count = 0
    for claim in claims:
        deleted = False
        error: str | None = None
        try:
            await asyncio.to_thread(storage.delete, claim.storage_key)
            deleted = True
        except (OSError, BotoCoreError, ClientError) as exc:
            error = str(exc)
            logger.warning(
                "storage_deletion_failed",
                extra={"storage_deletion_id": str(claim.id), "attempts": claim.attempts},
            )

        if not await finalize_storage_deletion(session, claim, deleted=deleted, error=error):
            logger.warning("storage_deletion_lease_lost", extra={"storage_deletion_id": str(claim.id)})
            continue
        deleted_count += int(deleted)
        failed_count += int(not deleted)
    return {"deleted": deleted_count, "failed": failed_count}
