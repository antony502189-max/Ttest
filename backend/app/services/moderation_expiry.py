from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, Listing, User
from ..models.moderation import ListingRestriction, UserRestriction
from .catalog import touch_catalog
from .mail import enqueue_mail
from .moderation import SUPPORT_EMAIL, active_listing_restriction, active_user_restriction, add_notice


async def _expired_user_candidate(
    session: AsyncSession,
    restriction_id: UUID,
    user_id: UUID,
    now: datetime,
) -> tuple[UserRestriction, User] | None:
    # Admin user mutations lock the parent User first. Match that order here so
    # an expiry decision cannot race an uncommitted replacement restriction.
    user = await session.scalar(
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .with_for_update()
    )
    if not user:
        return None
    restriction = await session.scalar(
        select(UserRestriction)
        .where(
            UserRestriction.id == restriction_id,
            UserRestriction.user_id == user.id,
            UserRestriction.revoked_at.is_(None),
            UserRestriction.ends_at <= now,
            UserRestriction.expiry_notified_at.is_(None),
        )
        .with_for_update()
    )
    if not restriction:
        return None
    return restriction, user


async def _expired_listing_candidate(
    session: AsyncSession,
    restriction_id: UUID,
    listing_id: UUID,
    now: datetime,
) -> tuple[ListingRestriction, Listing, User] | None:
    # Listing moderation routes lock the parent Listing first. Preserve the same
    # lock order before revalidating the expired restriction.
    listing = await session.scalar(
        select(Listing)
        .where(Listing.id == listing_id, Listing.deleted_at.is_(None))
        .with_for_update()
    )
    if not listing:
        return None
    restriction = await session.scalar(
        select(ListingRestriction)
        .where(
            ListingRestriction.id == restriction_id,
            ListingRestriction.listing_id == listing.id,
            ListingRestriction.revoked_at.is_(None),
            ListingRestriction.ends_at <= now,
            ListingRestriction.expiry_notified_at.is_(None),
        )
        .with_for_update()
    )
    if not restriction:
        return None
    owner = await session.get(User, listing.owner_user_id)
    if not owner or owner.deleted_at is not None:
        return None
    return restriction, listing, owner


async def process_expired_moderation(session: AsyncSession, *, limit: int = 100) -> dict[str, int]:
    """Queue expiry notifications safely against concurrent moderation writes."""
    now = datetime.now(UTC)

    # Discovery is intentionally lock-free. Each candidate is then serialized
    # on its parent row and revalidated under lock before any notification is
    # decided. Multiple workers converge without duplicate notifications.
    user_candidates = (
        await session.execute(
            select(UserRestriction.id, UserRestriction.user_id)
            .join(User, User.id == UserRestriction.user_id)
            .where(
                UserRestriction.revoked_at.is_(None),
                UserRestriction.ends_at <= now,
                UserRestriction.expiry_notified_at.is_(None),
                User.deleted_at.is_(None),
            )
            .order_by(UserRestriction.ends_at, UserRestriction.id)
            .limit(limit)
        )
    ).all()

    user_notified = 0
    for restriction_id, user_id in user_candidates:
        candidate = await _expired_user_candidate(session, restriction_id, user_id, now)
        if not candidate:
            continue
        restriction, user = candidate
        restriction.expiry_notified_at = now
        active_user = await active_user_restriction(user.id, session)
        if active_user:
            # A newer restriction won the parent-row lock before us. Mark the old
            # expiry handled but never claim that access has been restored.
            continue
        add_notice(
            session,
            user.id,
            kind="user_restriction_expired",
            title="Tu restricción ha finalizado",
            body=f"El acceso correspondiente se ha restaurado automáticamente. Soporte: {SUPPORT_EMAIL}",
        )
        enqueue_mail(
            session,
            kind="moderation_restriction_expired",
            recipient=user.email,
            subject="Tu restricción ha finalizado",
            body=f"La restricción de tu cuenta ha finalizado automáticamente.\n\nSoporte: {SUPPORT_EMAIL}",
        )
        session.add(
            AuditLog(
                actor_id=None,
                action="user.restriction_expired",
                target_type="user",
                target_id=user.id,
                detail={"restrictionId": str(restriction.id)},
            )
        )
        await touch_catalog(session)
        user_notified += 1

    listing_candidates = (
        await session.execute(
            select(ListingRestriction.id, ListingRestriction.listing_id)
            .join(Listing, Listing.id == ListingRestriction.listing_id)
            .join(User, User.id == Listing.owner_user_id)
            .where(
                ListingRestriction.revoked_at.is_(None),
                ListingRestriction.ends_at <= now,
                ListingRestriction.expiry_notified_at.is_(None),
                Listing.deleted_at.is_(None),
                User.deleted_at.is_(None),
            )
            .order_by(ListingRestriction.ends_at, ListingRestriction.id)
            .limit(limit)
        )
    ).all()

    listing_notified = 0
    for restriction_id, listing_id in listing_candidates:
        candidate = await _expired_listing_candidate(session, restriction_id, listing_id, now)
        if not candidate:
            continue
        restriction, listing, owner = candidate
        restriction.expiry_notified_at = now
        active_listing = await active_listing_restriction(listing.id, session)
        if active_listing:
            continue
        add_notice(
            session,
            owner.id,
            kind="listing_restriction_expired",
            title="La restricción de tu anuncio ha finalizado",
            body=f"El anuncio «{listing.title}» vuelve a regirse por su estado normal.",
        )
        enqueue_mail(
            session,
            kind="listing_restriction_expired",
            recipient=owner.email,
            subject="La restricción de tu anuncio ha finalizado",
            body=(
                f"La restricción administrativa del anuncio «{listing.title}» ha finalizado automáticamente.\n\n"
                f"Soporte: {SUPPORT_EMAIL}"
            ),
        )
        session.add(
            AuditLog(
                actor_id=None,
                action="listing.restriction_expired",
                target_type="listing",
                target_id=listing.id,
                detail={"restrictionId": str(restriction.id)},
            )
        )
        await touch_catalog(session)
        listing_notified += 1

    await session.commit()
    return {"users": user_notified, "listings": listing_notified}
