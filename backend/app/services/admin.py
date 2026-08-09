from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, Listing, ListingStatusHistory, Report, User
from ..models.moderation import AdminAccess, AdminNote, ListingRestriction
from ..schemas.admin import (
    AdminAccessResponse,
    AdminListingResponse,
    AdminNoteResponse,
    AdminStatsResponse,
    AuditLogResponse,
    ListingRestrictionResponse,
)
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
    )


async def dashboard_stats(session: AsyncSession) -> AdminStatsResponse:
    users, listings, pending, reports = (
        await session.execute(
            select(
                select(func.count()).select_from(User).where(User.deleted_at.is_(None)).scalar_subquery(),
                select(func.count()).select_from(Listing).where(Listing.deleted_at.is_(None)).scalar_subquery(),
                select(func.count())
                .select_from(Listing)
                .where(Listing.status == "pending", Listing.deleted_at.is_(None))
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
    listing = await session.get(Listing, listing_id)
    if not listing or listing.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
    if new_status == "published":
        owner = await session.get(User, listing.owner_user_id)
        if not owner or not owner.email_verified:
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
    await session.commit()
    owner = await session.get(User, listing.owner_user_id)
    return public_listing(listing, owner=owner, restriction=await active_listing_restriction(listing.id, session))


async def restrict_listing(
    listing_id: UUID,
    *,
    until: datetime,
    reason: str,
    actor: User,
    session: AsyncSession,
) -> AdminListingResponse:
    listing = await session.get(Listing, listing_id)
    if not listing or listing.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
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
    owner = await session.get(User, listing.owner_user_id)
    if owner:
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
    await session.commit()
    return public_listing(listing, owner=owner, restriction=row)


async def unrestrict_listing(listing_id: UUID, actor: User, session: AsyncSession) -> AdminListingResponse:
    listing = await session.get(Listing, listing_id)
    if not listing or listing.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
    current = await active_listing_restriction(listing.id, session)
    if not current:
        raise HTTPException(409, "Listing has no active restriction")
    current.revoked_at = datetime.now(UTC)
    current.revoked_by = actor.id
    owner = await session.get(User, listing.owner_user_id)
    if owner:
        add_notice(
            session,
            owner.id,
            kind="listing_unrestricted",
            title="La restricción de tu anuncio se ha retirado",
            body=f"El anuncio «{listing.title}» vuelve a estar disponible.",
        )
        enqueue_listing_unrestriction_email(session, owner.email, listing_title=listing.title)
    session.add(audit(actor.id, "listing.unrestricted", "listing", listing.id, {"restrictionId": str(current.id)}))
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
    target = await session.get(User, user_id)
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
    # If the account already exists, lock it in the same order used by user
    # moderation and refuse contradictory states such as "restricted admin".
    # A not-yet-registered email is still allowed so future Google sign-in can
    # activate the pre-authorized administrator identity.
    target = await session.scalar(
        select(User).where(func.lower(User.email) == normalized).with_for_update()
    )
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
