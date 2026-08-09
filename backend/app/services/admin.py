from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, AuthSession, Listing, ListingStatusHistory, Report, User
from ..models.moderation import AdminAccess, AdminNote, ListingRestriction, UserRestriction
from ..schemas.admin import (
    AdminAccessResponse,
    AdminListingResponse,
    AdminNoteResponse,
    AdminStatsResponse,
    AdminUserDetailResponse,
    AdminUserResponse,
    AuditLogResponse,
    ListingRestrictionResponse,
    RestrictionResponse,
)
from .mail import enqueue_mail
from .moderation import (
    SUPPORT_EMAIL,
    active_listing_restriction,
    active_user_restriction,
    active_window,
    add_notice,
    enqueue_listing_restriction_email,
    enqueue_listing_unrestriction_email,
    enqueue_restriction_email,
    enqueue_unrestriction_email,
    normalize_email,
)


def audit(actor_id: UUID, action: str, target_type: str, target_id: UUID | None, detail: dict) -> AuditLog:
    return AuditLog(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id, detail=detail)


def restriction_response(row: UserRestriction) -> RestrictionResponse:
    now = datetime.now(UTC)
    return RestrictionResponse(
        id=row.id,
        restrictionType=row.restriction_type,
        reason=row.reason,
        startsAt=row.starts_at,
        endsAt=row.ends_at,
        revokedAt=row.revoked_at,
        active=row.revoked_at is None and row.starts_at <= now < row.ends_at,
    )


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


def public_user(
    user: User,
    *,
    listing_count: int = 0,
    last_login: datetime | None = None,
    restriction: UserRestriction | None = None,
    is_admin: bool = False,
) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        blocked=user.blocked,
        phone=user.phone,
        whatsapp=user.whatsapp,
        telegram=user.telegram,
        about=user.about,
        initials=user.initials,
        showPhone=user.show_phone,
        showWhatsApp=user.show_whatsapp,
        allowContactForm=user.allow_contact_form,
        avatarUrl=f"/api/v1/media/{user.avatar_asset_id}" if user.avatar_asset_id else None,
        createdAt=user.created_at,
        deletedAt=user.deleted_at,
        lastLoginAt=last_login,
        listingCount=listing_count,
        activeRestriction=restriction_response(restriction) if restriction else None,
        isAdmin=is_admin,
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


async def list_listings(
    session: AsyncSession,
    status: str | None,
    search: str | None,
    *,
    restricted: bool | None = None,
    limit: int,
    offset: int,
) -> list[AdminListingResponse]:
    query = select(Listing, User).join(User, User.id == Listing.owner_user_id).order_by(Listing.created_at.desc())
    if status:
        query = query.where(Listing.status == status)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(Listing.title.ilike(term) | User.name.ilike(term))
    if restricted is True:
        query = query.where(
            select(ListingRestriction.id)
            .where(ListingRestriction.listing_id == Listing.id, *active_window(ListingRestriction))
            .exists()
        )
    elif restricted is False:
        query = query.where(
            ~select(ListingRestriction.id)
            .where(ListingRestriction.listing_id == Listing.id, *active_window(ListingRestriction))
            .exists()
        )
    rows = (await session.execute(query.limit(limit).offset(offset))).all()
    result: list[AdminListingResponse] = []
    for listing, owner in rows:
        restriction = await active_listing_restriction(listing.id, session)
        result.append(public_listing(listing, owner=owner, restriction=restriction))
    return result


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


async def _active_admin_emails(session: AsyncSession) -> set[str]:
    return set((await session.scalars(select(AdminAccess.email).where(AdminAccess.active.is_(True)))).all())


async def list_users(
    session: AsyncSession,
    search: str | None,
    *,
    status_filter: str | None = None,
    limit: int,
    offset: int,
) -> list[AdminUserResponse]:
    listing_count = (
        select(func.count(Listing.id))
        .where(Listing.owner_user_id == User.id, Listing.deleted_at.is_(None))
        .correlate(User)
        .scalar_subquery()
    )
    last_login = (
        select(func.max(AuthSession.issued_at)).where(AuthSession.user_id == User.id).correlate(User).scalar_subquery()
    )
    query = select(User, listing_count, last_login).order_by(User.created_at.desc())
    if search:
        query = query.where(User.name.ilike(f"%{search.strip()}%"))
    if status_filter == "deleted":
        query = query.where(User.deleted_at.is_not(None))
    else:
        query = query.where(User.deleted_at.is_(None))
    rows = (await session.execute(query.limit(limit).offset(offset))).all()
    admin_emails = await _active_admin_emails(session)
    result: list[AdminUserResponse] = []
    for user, count, last_seen in rows:
        restriction = await active_user_restriction(user.id, session)
        if status_filter in {"restricted", "full", "publish", "view_listings"}:
            if not restriction:
                continue
            if status_filter != "restricted" and restriction.restriction_type != status_filter:
                continue
        elif status_filter == "active" and restriction:
            continue
        result.append(
            public_user(
                user,
                listing_count=int(count or 0),
                last_login=last_seen,
                restriction=restriction,
                is_admin=normalize_email(user.email) in admin_emails,
            )
        )
    return result


async def get_user_detail(user_id: UUID, session: AsyncSession) -> AdminUserDetailResponse:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    count = await session.scalar(
        select(func.count()).select_from(Listing).where(Listing.owner_user_id == user.id, Listing.deleted_at.is_(None))
    )
    last_login = await session.scalar(select(func.max(AuthSession.issued_at)).where(AuthSession.user_id == user.id))
    rows = (
        await session.scalars(
            select(UserRestriction)
            .where(UserRestriction.user_id == user.id)
            .order_by(UserRestriction.starts_at.desc())
            .limit(100)
        )
    ).all()
    active = next((row for row in rows if restriction_response(row).active), None)
    base = public_user(
        user,
        listing_count=int(count or 0),
        last_login=last_login,
        restriction=active,
        is_admin=bool(await session.get(AdminAccess, normalize_email(user.email))),
    )
    return AdminUserDetailResponse(**base.model_dump(), restrictions=[restriction_response(row) for row in rows])


async def restrict_user(
    user_id: UUID,
    *,
    restriction_type: str,
    until: datetime,
    reason: str,
    actor: User,
    session: AsyncSession,
) -> AdminUserDetailResponse:
    target = await session.get(User, user_id)
    if not target or target.deleted_at is not None:
        raise HTTPException(404, "User not found")
    if target.id == actor.id:
        raise HTTPException(422, "Administrators cannot restrict themselves")
    admin = await session.get(AdminAccess, normalize_email(target.email))
    if admin and admin.active:
        raise HTTPException(422, "Revoke administrator access before restricting this account")
    now = datetime.now(UTC)
    if until.tzinfo is None:
        until = until.replace(tzinfo=UTC)
    if until <= now:
        raise HTTPException(422, "Restriction end date must be in the future")
    current = await active_user_restriction(target.id, session)
    if current:
        current.revoked_at = now
        current.revoked_by = actor.id
    row = UserRestriction(
        user_id=target.id,
        restriction_type=restriction_type,
        reason=reason.strip(),
        starts_at=now,
        ends_at=until,
        created_by=actor.id,
    )
    session.add(row)
    add_notice(
        session,
        target.id,
        kind="user_restricted",
        title="Tu cuenta tiene una restricción",
        body=f"{reason.strip()} · Hasta {until.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')} · Soporte: {SUPPORT_EMAIL}",
    )
    enqueue_restriction_email(
        session,
        target.email,
        restriction_type=restriction_type,
        reason=reason.strip(),
        until=until,
    )
    session.add(
        audit(
            actor.id,
            "user.restricted",
            "user",
            target.id,
            {"restrictionType": restriction_type, "until": until.isoformat(), "reason": reason.strip()},
        )
    )
    await session.commit()
    return await get_user_detail(target.id, session)


async def unrestrict_user(user_id: UUID, actor: User, session: AsyncSession) -> AdminUserDetailResponse:
    target = await session.get(User, user_id)
    if not target or target.deleted_at is not None:
        raise HTTPException(404, "User not found")
    current = await active_user_restriction(target.id, session)
    if not current:
        raise HTTPException(409, "User has no active restriction")
    current.revoked_at = datetime.now(UTC)
    current.revoked_by = actor.id
    add_notice(
        session,
        target.id,
        kind="user_unrestricted",
        title="La restricción se ha retirado",
        body=f"Tu cuenta vuelve a estar disponible. Soporte: {SUPPORT_EMAIL}",
    )
    enqueue_unrestriction_email(session, target.email)
    session.add(audit(actor.id, "user.unrestricted", "user", target.id, {"restrictionId": str(current.id)}))
    await session.commit()
    return await get_user_detail(target.id, session)


async def soft_delete_user(
    user_id: UUID,
    *,
    reason: str,
    actor: User,
    session: AsyncSession,
) -> None:
    target = await session.get(User, user_id)
    if not target or target.deleted_at is not None:
        raise HTTPException(404, "User not found")
    if target.id == actor.id:
        raise HTTPException(422, "Administrators cannot delete themselves")
    admin = await session.get(AdminAccess, normalize_email(target.email))
    if admin and admin.active:
        raise HTTPException(422, "Revoke administrator access before deleting this account")
    target.deleted_at = datetime.now(UTC)
    session.add(audit(actor.id, "user.deleted", "user", target.id, {"reason": reason.strip()}))
    enqueue_mail(
        session,
        kind="account_deleted_by_admin",
        recipient=target.email,
        subject="Tu cuenta ha sido eliminada",
        body=f"Tu cuenta se ha eliminado. Motivo: {reason.strip()}\n\nSoporte: {SUPPORT_EMAIL}",
    )
    await session.commit()


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
    current = await active_listing_restriction(listing.id, session)
    if current:
        current.revoked_at = now
        current.revoked_by = actor.id
    row = ListingRestriction(
        listing_id=listing.id,
        reason=reason.strip(),
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
            body=f"{listing.title}: {reason.strip()} · Hasta {until.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        )
        enqueue_listing_restriction_email(
            session,
            owner.email,
            listing_title=listing.title,
            reason=reason.strip(),
            until=until,
        )
    session.add(
        audit(
            actor.id,
            "listing.restricted",
            "listing",
            listing.id,
            {"until": until.isoformat(), "reason": reason.strip()},
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
            .order_by(AdminNote.created_at.desc())
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
    if not await session.get(User, user_id):
        raise HTTPException(404, "User not found")
    note = AdminNote(user_id=user_id, body=body.strip(), created_by=actor.id)
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
            .order_by(AuditLog.created_at.desc())
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
