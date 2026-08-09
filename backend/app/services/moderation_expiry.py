from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, Listing, User
from ..models.moderation import ListingRestriction, UserRestriction
from .mail import enqueue_mail
from .moderation import SUPPORT_EMAIL, active_listing_restriction, active_user_restriction, add_notice


async def process_expired_moderation(session: AsyncSession, *, limit: int = 100) -> dict[str, int]:
    """Queue one expiry notification per restriction without requiring a separate scheduler."""
    now = datetime.now(UTC)
    user_rows = (
        await session.execute(
            select(UserRestriction, User)
            .join(User, User.id == UserRestriction.user_id)
            .where(
                UserRestriction.revoked_at.is_(None),
                UserRestriction.ends_at <= now,
                UserRestriction.expiry_notified_at.is_(None),
                User.deleted_at.is_(None),
            )
            .order_by(UserRestriction.ends_at)
            .limit(limit)
            .with_for_update(of=UserRestriction, skip_locked=True)
        )
    ).all()

    user_notified = 0
    for restriction, user in user_rows:
        restriction.expiry_notified_at = now
        active_user = await active_user_restriction(user.id, session)
        if active_user:
            # A newer restriction supersedes the expired one; do not send a
            # misleading "access restored" message, but mark this expiry handled.
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
        user_notified += 1

    listing_rows = (
        await session.execute(
            select(ListingRestriction, Listing, User)
            .join(Listing, Listing.id == ListingRestriction.listing_id)
            .join(User, User.id == Listing.owner_user_id)
            .where(
                ListingRestriction.revoked_at.is_(None),
                ListingRestriction.ends_at <= now,
                ListingRestriction.expiry_notified_at.is_(None),
                Listing.deleted_at.is_(None),
                User.deleted_at.is_(None),
            )
            .order_by(ListingRestriction.ends_at)
            .limit(limit)
            .with_for_update(of=ListingRestriction, skip_locked=True)
        )
    ).all()

    listing_notified = 0
    for restriction, listing, owner in listing_rows:
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
        listing_notified += 1

    await session.commit()
    return {"users": user_notified, "listings": listing_notified}
