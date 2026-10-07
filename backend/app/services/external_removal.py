"""Direct-state reconciliation and confirmed purge, without discovery/media I/O."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..external_sources import ExternalListingSource, SourceBlocked
from ..models import ExternalListingSource as SourceRecord
from ..models import Listing, ListingImage
from .catalog import touch_catalog
from .external_import import promote_best_active_source, require_no_active_transaction
from .listings import mark_orphaned_media
from .media_lifecycle import lock_media_assets
from .notifications import notify_favorited_listing_unavailable

logger = logging.getLogger(__name__)
BATCH_SIZE = 100
GLOBAL_CONCURRENCY = 4
LOCK_TTL_SECONDS = 1800
CIRCUIT_FAILURES = 5
COUNTERS = (
    "candidate_records",
    "checked",
    "active",
    "confirmed_removed",
    "expired",
    "not_found",
    "blocked",
    "temporary_error",
    "unknown",
    "source_rows_purged",
    "canonical_listings_purged",
    "canonical_sources_promoted",
    "media_assets_orphaned",
    "storage_deletions_enqueued",
    "deferred_by_circuit_breaker",
    "failed",
    "batches",
)


def new_report() -> dict:
    return dict.fromkeys(COUNTERS, 0)


async def purge_confirmed_removed_source(session: AsyncSession, source_id: UUID, state: str) -> dict[str, int]:
    """Caller owns the shared import lease and commits this short transaction."""
    if state not in {"removed", "expired", "not_found"}:
        raise ValueError("Physical purge requires authoritative direct removal evidence")
    outcome = dict.fromkeys(
        (
            "source_rows_purged",
            "canonical_listings_purged",
            "canonical_sources_promoted",
            "media_assets_orphaned",
            "storage_deletions_enqueued",
        ),
        0,
    )
    canonical_id = await session.scalar(select(SourceRecord.canonical_listing_id).where(SourceRecord.id == source_id))
    if canonical_id is None:
        return outcome
    listing = await session.scalar(
        select(Listing).where(Listing.id == canonical_id).with_for_update().execution_options(populate_existing=True)
    )
    if listing is None or not listing.is_external:
        logger.error("external_removal_native_relation_refused source_record_id=%s", source_id)
        raise ValueError("Confirmed removal cannot mutate a native canonical listing")
    row = await session.scalar(
        select(SourceRecord)
        .where(SourceRecord.id == source_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or row.current_status != "active" or row.canonical_listing_id != canonical_id:
        return outcome
    primary_removed = listing.primary_source == row.source_name and listing.primary_source_url == row.source_url
    await session.execute(delete(SourceRecord).where(SourceRecord.id == source_id))
    await session.flush()
    outcome["source_rows_purged"] = 1
    active = await session.scalar(
        select(func.count())
        .select_from(SourceRecord)
        .where(SourceRecord.canonical_listing_id == canonical_id, SourceRecord.current_status == "active")
    )
    if active:
        if primary_removed:
            if not await promote_best_active_source(session, canonical_id, lifecycle_only=True):
                raise RuntimeError("Active alternative has no usable normalized source snapshot")
            outcome["canonical_sources_promoted"] = 1
    else:
        asset_ids = set(
            (
                await session.scalars(
                    select(ListingImage.media_asset_id).where(ListingImage.listing_id == canonical_id)
                )
            ).all()
        )
        if listing.video_asset_id:
            asset_ids.add(listing.video_asset_id)
        await lock_media_assets(session, asset_ids)
        await notify_favorited_listing_unavailable(session, listing, event_key=f"external-purge:{source_id}:{state}")
        remaining = await session.scalar(
            select(func.count()).select_from(SourceRecord).where(SourceRecord.canonical_listing_id == canonical_id)
        )
        outcome["source_rows_purged"] += int(remaining or 0)
        await session.execute(delete(Listing).where(Listing.id == canonical_id, Listing.is_external.is_(True)))
        await session.flush()
        outcome["canonical_listings_purged"] = 1
        outcome["media_assets_orphaned"] = await mark_orphaned_media(session, asset_ids)
        outcome["storage_deletions_enqueued"] = outcome["media_assets_orphaned"]
    await touch_catalog(session)
    return outcome


async def reconcile_source(
    session: AsyncSession,
    source: ExternalListingSource,
    *,
    report: dict | None = None,
    started_at: datetime | None = None,
    global_limit: asyncio.Semaphore | None = None,
) -> int:
    """One finite keyset snapshot; at most one bounded batch per provider in memory."""
    report = report if report is not None else new_report()
    started_at = started_at or datetime.now(UTC)
    started = monotonic()
    eligible = (
        SourceRecord.source_name == source.name,
        SourceRecord.current_status == "active",
        SourceRecord.first_seen_at <= started_at,
    )
    report["candidate_records"] = int(
        await session.scalar(select(func.count()).select_from(SourceRecord).where(*eligible)) or 0
    )
    await session.commit()
    provider_limit = asyncio.Semaphore(min(3, get_settings().external_import_max_concurrency_per_source))
    global_limit = global_limit or asyncio.Semaphore(GLOBAL_CONCURRENCY)
    cursor = None
    failure_streak = 0
    circuit = False

    async def probe(url: str) -> str:
        nonlocal failure_streak, circuit
        async with provider_limit, global_limit:
            if circuit:
                return "deferred"
            require_no_active_transaction(session, "external removal direct state probe")
            try:
                state = await source.check_listing_state(url)
            except SourceBlocked:
                state = "blocked"
            except Exception:
                logger.exception("external_removal_adapter_failed source=%s", source.name)
                report["failed"] += 1
                state = "temporary_error"
            if state not in {"active", "removed", "expired", "not_found", "blocked", "temporary_error", "unknown"}:
                state = "unknown"
            failure_streak = failure_streak + 1 if state in {"blocked", "temporary_error"} else 0
            if failure_streak >= CIRCUIT_FAILURES:
                circuit = True
                report["circuit_reason"] = state
            return state

    while not circuit:
        query = (
            select(SourceRecord.id, SourceRecord.source_url)
            .where(*eligible)
            .order_by(SourceRecord.id)
            .limit(BATCH_SIZE)
        )
        if cursor is not None:
            query = query.where(SourceRecord.id > cursor)
        batch = (await session.execute(query)).all()
        await session.commit()
        if not batch:
            break
        cursor = batch[-1].id
        report["batches"] += 1
        states = await asyncio.gather(*(probe(row.source_url) for row in batch))
        for candidate, state in zip(batch, states):
            if state == "deferred":
                report["deferred_by_circuit_breaker"] += 1
                continue
            report["checked"] += 1
            if state in {"removed", "expired", "not_found"}:
                report["confirmed_removed"] += 1
                if state != "removed":
                    report[state] += 1
            else:
                report[state] += 1
            canonical_id = await session.scalar(
                select(SourceRecord.canonical_listing_id).where(SourceRecord.id == candidate.id)
            )
            listing = await session.scalar(
                select(Listing)
                .where(Listing.id == canonical_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            row = await session.scalar(
                select(SourceRecord)
                .where(SourceRecord.id == candidate.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                row is None
                or row.current_status != "active"
                or row.canonical_listing_id != canonical_id
                or row.source_url != candidate.source_url
                or (row.last_seen_at is not None and row.last_seen_at > started_at)
            ):
                await session.rollback()
                continue
            if listing is None or not listing.is_external:
                logger.error("external_removal_native_relation_refused source_record_id=%s", candidate.id)
                report["failed"] += 1
                await session.rollback()
                continue
            row.last_checked_at = row.last_state_check_at = datetime.now(UTC)
            row.last_state_check_result = state
            if state in {"removed", "expired", "not_found"}:
                report.update(
                    {
                        key: report[key] + count
                        for key, count in (await purge_confirmed_removed_source(session, candidate.id, state)).items()
                    }
                )
            elif state == "active":
                row.last_success_at = row.last_seen_at = row.last_checked_at
                row.consecutive_missing_runs = row.consecutive_unknown_state_runs = 0
                row.last_error = None
            else:
                row.last_error = state
                if state == "unknown":
                    row.consecutive_unknown_state_runs += 1
            await session.commit()
        if circuit:
            remaining = await session.scalar(
                select(func.count()).select_from(SourceRecord).where(*eligible, SourceRecord.id > cursor)
            )
            report["deferred_by_circuit_breaker"] += int(remaining or 0)
            await session.commit()
    report["duration_seconds"] = round(monotonic() - started, 3)
    report["result"] = (
        "partial"
        if any(
            report[key] for key in ("blocked", "temporary_error", "unknown", "failed", "deferred_by_circuit_breaker")
        )
        else "success"
    )
    logger.info("external_removal_source_summary %s", json.dumps({"source": source.name, **report}))
    return report["canonical_listings_purged"]
