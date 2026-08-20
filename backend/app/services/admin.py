from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, Listing, ListingStatusHistory, Report, User
from ..models.moderation import AdminAccess, AdminNote, ListingPromotion, ListingRestriction
from ..schemas.admin import (
    AdminAccessResponse,
    AdminListingResponse,
    AdminNoteResponse,
    AdminStatsResponse,
    AuditLogResponse,
    ListingRestrictionResponse,
)
from .catalog import touch_catalog
from .moderation import (
    active_listing_restriction,
    active_user_restriction,
    add_notice,
    enqueue_listing_restriction_email,
    enqueue_listing_unrestriction_email,
    normalize_email,
)


def audit(actor_id: UUID, action: str, target_type: str, target_id: UUID | None, detail: dict) -> AuditLog:
    return AuditLog(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id, detail=detail)


def listing_restriction_response(row: ListingRestriction) -> ListingRestrictionResponse:
    now = datetime.now(UTC)
    return ListingRestrictionResponse(
        id=row.id,
        reason=row.reason,
        startsAt=row.starts_at,
        endsAt=row.ends_at,
        revokedAt=row.revoked_at,
        active=row.revoked_at is None and row.starts_at <= now < row.ends_at,
    )


def public_listing(
    listing: Listing,
    *,
    owner: User | None = None,
    restriction: ListingRestriction | None = None,
    promotion: ListingPromotion | None = None,
) -> AdminListingResponse:
    return AdminListingResponse(
        id=listing.id,
        ownerUserId=listing.owner_user_id,
        ownerName=owner.name if owner else None,
        ownerEmail=owner.email if owner else None,
        title=listing.title,
        city=listing.city,
        area=listing.area,
        status=listing.status,
        rentalMode=listing.rental_mode,
        views=listing.views,
        createdAt=listing.created_at,
        deletedAt=listing.deleted_at,
        activeRestriction=listing_restriction_response(restriction) if restriction else None,
        promoted=promotion is not None,
        boostedAt=promotion.boosted_at if promotion else None,
    )


async def _actionable_listing(listing_id: UUID, session: AsyncSession) -> tuple[Listing, User]:
    """Lock one actionable listing using the account-deletion lock order.

    `delete_account()` serializes User -> owned Listings. Listing moderation must
    use the same order or concurrent deletion can form a User/Listing deadlock.
    The initial owner-id lookup is intentionally lock-free; ownership is
    immutable, and the final locked Listing lookup revalidates id, owner and
    deletion state before any mutation is accepted.
    """
    owner_id = await session.scalar(
        select(Listing.owner_user_id).where(Listing.id == listing_id, Listing.deleted_at.is_(None))
    )
    if not owner_id:
        raise HTTPException(404, "Listing not found")

    owner = await session.scalar(select(User).where(User.id == owner_id).with_for_update())
    if not owner or owner.deleted_at is not None:
        raise HTTPException(404, "Listing not found")

    listing = await session.scalar(
        select(Listing)
        .where(
            Listing.id == listing_id,
            Listing.owner_user_id == owner.id,
            Listing.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if not listing:
        raise HTTPException(404, "Listing not found")
    return listing, owner


async def dashboard_stats(session: AsyncSession) -> AdminStatsResponse:
    users, listings, pending, reports = (
        await session.execute(
            select(
                select(func.count()).select_from(User).where(User.deleted_at.is_(None)).scalar_subquery(),
                select(func.count())
                .select_from(Listing)
                .join(User, User.id == Listing.owner_user_id)
                .where(Listing.deleted_at.is_(None), User.deleted_at.is_(None))
                .scalar_subquery(),
                select(func.count())
                .select_from(Listing)
                .join(User, User.id == Listing.owner_user_id)
                .where(
                    Listing.status == "pending",
                    Listing.deleted_at.is_(None),
                    User.deleted_at.is_(None),
                )
                .scalar_subquery(),
                select(func.count())
                .select_from(Report)
                .where(Report.status.in_(["open", "in_review"]))
                .scalar_subquery(),
            )
        )
    ).one()
    return AdminStatsResponse(users=users, listings=listings, pendingListings=pending, openReports=reports)


async def change_listing_status(
    listing_id: UUID,
    new_status: str,
    actor: User,
    session: AsyncSession,
) -> AdminListingResponse:
    if new_status not in {"draft", "pending", "published", "hidden", "closed", "rejected"}:
        raise HTTPException(422, "Invalid listing status")
    listing, owner = await _actionable_listing(listing_id, session)
    if new_status == "published" and not owner.email_verified:
        raise HTTPException(
            409,
            detail={
                "code": "EMAIL_VERIFICATION_REQUIRED",
                "message": "The listing owner must confirm their email before publication.",
                "fieldErrors": {},
            },
        )
    previous = listing.status
    listing.status = new_status
    if new_status == "published" and listing.published_at is None:
        listing.published_at = datetime.now(UTC)
    if new_status != "closed":
        listing.closed_reason = None
    session.add(
        ListingStatusHistory(
            listing_id=listing.id,
            from_status=previous,
            to_status=listing.status,
            changed_by=actor.id,
        )
    )
    session.add(audit(actor.id, "listing.status_changed", "listing", listing.id, {"from": previous, "to": new_status}))
    if previous != new_status:
        await touch_catalog(session)
    await session.commit()
    return public_listing(listing, owner=owner, restriction=await active_listing_restriction(listing.id, session))


async def promote_listing(listing_id: UUID, actor: User, session: AsyncSession) -> AdminListingResponse:
    listing, owner = await _actionable_listing(listing_id, session)
    if listing.status != "published":
        raise HTTPException(409, "Only published listings can be promoted")
    row = await session.scalar(
        select(ListingPromotion).where(ListingPromotion.listing_id == listing.id).with_for_update()
    )
    previous_boosted_at = row.boosted_at if row else None
    now = datetime.now(UTC)
    if row is None:
        row = ListingPromotion(listing_id=listing.id, boosted_at=now, boosted_by=actor.id)
        session.add(row)
    else:
        row.boosted_at = now
        row.boosted_by = actor.id
    session.add(
        audit(
            actor.id,
            "listing.promoted",
            "listing",
            listing.id,
            {
                "previousBoostedAt": previous_boosted_at.isoformat() if previous_boosted_at else None,
                "boostedAt": now.isoformat(),
            },
        )
    )
    await touch_catalog(session)
    await session.commit()
    return public_listing(listing, owner=owner, promotion=row)


async def remove_listing_promotion(listing_id: UUID, actor: User, session: AsyncSession) -> AdminListingResponse:
    listing, owner = await _actionable_listing(listing_id, session)
    row = await session.scalar(
        select(ListingPromotion).where(ListingPromotion.listing_id == listing.id).with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Listing is not promoted")
    previous_boosted_at = row.boosted_at
    await session.delete(row)
    session.add(
        audit(
            actor.id,
            "listing.unpromoted",
            "listing",
            listing.id,
            {"previousBoostedAt": previous_boosted_at.isoformat()},
        )
    )
    await touch_catalog(session)
    await session.commit()
    return public_listing(listing, owner=owner)


async def restrict_listing(
    listing_id: UUID,
    *,
    until: datetime,
    reason: str,
    actor: User,
    session: AsyncSession,
) -> AdminListingResponse:
    listing, owner = await _actionable_listing(listing_id, session)
    if until.tzinfo is None:
        until = until.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if until <= now:
        raise HTTPException(422, "Restriction end date must be in the future")
    clean_reason = reason.strip()
    if len(clean_reason) < 2:
        raise HTTPException(422, "Moderation reason must contain at least two non-space characters")
    current = await active_listing_restriction(listing.id, session)
    if current:
        current.revoked_at = now
        current.revoked_by = actor.id
    row = ListingRestriction(
        listing_id=listing.id,
        reason=clean_reason,
        starts_at=now,
        ends_at=until,
        created_by=actor.id,
    )
    session.add(row)
    add_notice(
        session,
        owner.id,
        kind="listing_restricted",
        title="Uno de tus anuncios se ha ocultado",
        body=f"{listing.title}: {clean_reason} · Hasta {until.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
    )
    enqueue_listing_restriction_email(
        session,
        owner.email,
        listing_title=listing.title,
        reason=clean_reason,
        until=until,
    )
    session.add(
        audit(
            actor.id,
            "listing.restricted",
            "listing",
            listing.id,
            {"until": until.isoformat(), "reason": clean_reason},
        )
    )
    await touch_catalog(session)
    await session.commit()
    return public_listing(listing, owner=owner, restriction=row)


async def unrestrict_listing(listing_id: UUID, actor: User, session: AsyncSession) -> AdminListingResponse:
    listing, owner = await _actionable_listing(listing_id, session)
    current = await active_listing_restriction(listing.id, session)
    if not current:
        raise HTTPException(409, "Listing has no active restriction")
    current.revoked_at = datetime.now(UTC)
    current.revoked_by = actor.id
    add_notice(
        session,
        owner.id,
        kind="listing_unrestricted",
        title="La restricción de tu anuncio se ha retirado",
        body=f"El anuncio «{listing.title}» vuelve a estar disponible.",
    )
    enqueue_listing_unrestriction_email(session, owner.email, listing_title=listing.title)
    session.add(audit(actor.id, "listing.unrestricted", "listing", listing.id, {"restrictionId": str(current.id)}))
    await touch_catalog(session)
    await session.commit()
    return public_listing(listing, owner=owner)


async def list_notes(user_id: UUID, session: AsyncSession) -> list[AdminNoteResponse]:
    rows = (
        await session.execute(
            select(AdminNote, User.name)
            .outerjoin(User, User.id == AdminNote.created_by)
            .where(AdminNote.user_id == user_id)
            .order_by(AdminNote.created_at.desc(), AdminNote.id.desc())
        )
    ).all()
    return [
        AdminNoteResponse(
            id=note.id,
            userId=note.user_id,
            body=note.body,
            createdBy=note.created_by,
            createdByName=name,
            createdAt=note.created_at,
        )
        for note, name in rows
    ]


async def add_note(user_id: UUID, body: str, actor: User, session: AsyncSession) -> AdminNoteResponse:
    # Serialize with soft-delete before deciding whether this historical record
    # is still writable. The deletion path locks the same User row first.
    target = await session.scalar(select(User).where(User.id == user_id).with_for_update())
    if not target or target.deleted_at is not None:
        raise HTTPException(404, "User not found")
    clean_body = body.strip()
    if not clean_body:
        raise HTTPException(422, "Note cannot be empty")
    note = AdminNote(user_id=user_id, body=clean_body, created_by=actor.id)
    session.add(note)
    await session.flush()
    session.add(audit(actor.id, "user.note_added", "user", user_id, {"noteId": str(note.id)}))
    await session.commit()
    return AdminNoteResponse(
        id=note.id,
        userId=note.user_id,
        body=note.body,
        createdBy=note.created_by,
        createdByName=actor.name,
        createdAt=note.created_at,
    )


async def list_admins(session: AsyncSession) -> list[AdminAccessResponse]:
    rows = (await session.scalars(select(AdminAccess).where(AdminAccess.active.is_(True)).order_by(AdminAccess.email))).all()
    return [
        AdminAccessResponse(email=row.email, active=row.active, createdBy=row.created_by, createdAt=row.created_at)
        for row in rows
    ]


async def add_admin(email: str, actor: User, session: AsyncSession) -> AdminAccessResponse:
    normalized = normalize_email(email)
    target = await session.scalar(select(User).where(func.lower(User.email) == normalized).with_for_update())
    if target:
        if target.deleted_at is not None or target.blocked:
            raise HTTPException(422, "Restore the account before granting administrator access")
        if await active_user_restriction(target.id, session):
            raise HTTPException(422, "Remove the account restriction before granting administrator access")

    row = await session.get(AdminAccess, normalized)
    if row:
        row.active = True
        if row.created_by is None:
            row.created_by = actor.id
    else:
        row = AdminAccess(email=normalized, active=True, created_by=actor.id)
        session.add(row)
    session.add(audit(actor.id, "admin.granted", "admin", None, {"email": normalized}))
    await session.commit()
    await session.refresh(row)
    return AdminAccessResponse(email=row.email, active=row.active, createdBy=row.created_by, createdAt=row.created_at)


async def revoke_admin(email: str, actor: User, session: AsyncSession) -> None:
    normalized = normalize_email(email)
    if normalized == normalize_email(actor.email):
        raise HTTPException(422, "Administrators cannot revoke their own access")
    row = await session.get(AdminAccess, normalized)
    if not row or not row.active:
        raise HTTPException(404, "Administrator not found")
    active_count = await session.scalar(select(func.count()).select_from(AdminAccess).where(AdminAccess.active.is_(True)))
    if int(active_count or 0) <= 1:
        raise HTTPException(409, "At least one administrator must remain active")
    row.active = False
    session.add(audit(actor.id, "admin.revoked", "admin", None, {"email": normalized}))
    await session.commit()


async def list_audit_logs(session: AsyncSession, *, limit: int, offset: int) -> list[AuditLogResponse]:
    rows = (
        await session.execute(
            select(AuditLog, User.name)
            .outerjoin(User, User.id == AuditLog.actor_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [
        AuditLogResponse(
            id=row.id,
            actorId=row.actor_id,
            actorName=actor_name,
            action=row.action,
            targetType=row.target_type,
            targetId=row.target_id,
            detail=row.detail,
            createdAt=row.created_at,
        )
        for row, actor_name in rows
    ]
