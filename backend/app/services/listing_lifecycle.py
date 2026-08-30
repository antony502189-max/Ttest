from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Listing, ListingStatusHistory, User
from .catalog import touch_catalog
from .notifications import create_notification, notify_favorited_listing_unavailable


async def expire_due_listings(session: AsyncSession, *, limit: int = 100) -> int:
    """Close expired internal listings and emit durable product notifications.

    Public queries already exclude rows past ``expires_at``. This worker-facing
    transition makes persisted lifecycle state catch up with that visibility
    rule and guarantees owner/favorite notifications instead of relying on a
    landlord reopening the browser.

    Stateful listing mutations use the same User -> Listing lock order as
    account deletion and moderation. ``SKIP LOCKED`` keeps the lifecycle worker
    non-blocking: if an account/listing is already being changed, the next cycle
    will re-evaluate it from durable state instead of racing that transaction.
    """
    now = datetime.now(UTC)
    candidates = list(
        (
            await session.execute(
                select(Listing.id, Listing.owner_user_id)
                .where(
                    Listing.status == "published",
                    Listing.deleted_at.is_(None),
                    Listing.is_external.is_(False),
                    Listing.expires_at.is_not(None),
                    Listing.expires_at <= now,
                )
                .order_by(Listing.expires_at, Listing.id)
                .limit(limit)
            )
        ).all()
    )

    expired = 0
    for listing_id, owner_user_id in candidates:
        owner = await session.scalar(
            select(User)
            .where(User.id == owner_user_id, User.deleted_at.is_(None))
            .execution_options(populate_existing=True)
            .with_for_update(skip_locked=True)
        )
        if not owner:
            continue

        listing = await session.scalar(
            select(Listing)
            .where(
                Listing.id == listing_id,
                Listing.owner_user_id == owner.id,
                Listing.status == "published",
                Listing.deleted_at.is_(None),
                Listing.is_external.is_(False),
                Listing.expires_at.is_not(None),
                Listing.expires_at <= now,
            )
            .execution_options(populate_existing=True)
            .with_for_update(skip_locked=True)
        )
        if not listing:
            continue

        listing.status = "closed"
        listing.closed_reason = "expired"
        history = ListingStatusHistory(
            listing_id=listing.id,
            from_status="published",
            to_status="closed",
            changed_by=None,
        )
        session.add(history)
        await session.flush()

        if not owner.blocked:
            await create_notification(
                session,
                recipient=owner,
                kind="listing_expired",
                title="Tu anuncio ha finalizado",
                body=f"«{listing.title}» ha finalizado por vencimiento. Puedes renovarlo desde Mis anuncios.",
                entity_listing_id=listing.id,
                idempotency_key=f"listing-expired:{history.id}",
                email_path="/mis-anuncios",
            )

        await notify_favorited_listing_unavailable(session, listing, event_key=f"expired:{history.id}")
        expired += 1

    if expired:
        await touch_catalog(session)
    await session.commit()
    return expired
