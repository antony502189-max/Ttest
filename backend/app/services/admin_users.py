from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, AuthSession, Listing, User
from ..models.moderation import AdminAccess, UserRestriction
from ..schemas.admin import AdminUserDetailResponse, AdminUserResponse, RestrictionResponse
from .catalog import touch_catalog
from .mail import enqueue_mail
from .moderation import (
    RESTRICTION_TYPES,
    SUPPORT_EMAIL,
    active_user_restriction,
    active_window,
    add_notice,
    enqueue_restriction_email,
    enqueue_unrestriction_email,
    normalize_email,
    restriction_period_text,
)


def restriction_response(row: UserRestriction) -> RestrictionResponse:
    now = datetime.now(UTC)
    return RestrictionResponse(
        id=row.id,
        restrictionType=row.restriction_type,
        reason=row.reason,
        startsAt=row.starts_at,
        endsAt=row.ends_at,
        revokedAt=row.revoked_at,
        active=(
            row.revoked_at is None
            and row.starts_at <= now
            and (row.ends_at is None or now < row.ends_at)
        ),
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


async def _active_admin_emails(session: AsyncSession) -> set[str]:
    return set((await session.scalars(select(AdminAccess.email).where(AdminAccess.active.is_(True)))).all())


def _active_restriction_exists(*, restriction_type: str | None = None):
    query = select(UserRestriction.id).where(
        UserRestriction.user_id == User.id,
        *active_window(UserRestriction),
    )
    if restriction_type:
        query = query.where(UserRestriction.restriction_type == restriction_type)
    return query.correlate(User).exists()


async def _active_restrictions_by_user(
    session: AsyncSession,
    user_ids: list[UUID],
) -> dict[UUID, UserRestriction]:
    if not user_ids:
        return {}
    priority = case(
        (UserRestriction.restriction_type == "full", 0),
        (UserRestriction.restriction_type == "publish", 1),
        else_=2,
    )
    rows = (
        await session.scalars(
            select(UserRestriction)
            .where(UserRestriction.user_id.in_(user_ids), *active_window(UserRestriction))
            .order_by(
                UserRestriction.user_id,
                priority,
                UserRestriction.ends_at.asc().nullsfirst(),
                UserRestriction.starts_at.desc(),
            )
        )
    ).all()
    result: dict[UUID, UserRestriction] = {}
    for row in rows:
        result.setdefault(row.user_id, row)
    return result


def _clean_reason(reason: str) -> str:
    value = reason.strip()
    if len(value) < 2:
        raise HTTPException(422, "Moderation reason must contain at least two non-space characters")
    return value


async def list_users(
    session: AsyncSession,
    search: str | None,
    *,
    status_filter: str | None = None,
    limit: int,
    offset: int,
    after_created_at: datetime | None = None,
    after_id: UUID | None = None,
) -> list[AdminUserResponse]:
    listing_count = (
        select(func.count(Listing.id))
        .where(Listing.owner_user_id == User.id, Listing.deleted_at.is_(None))
        .correlate(User)
        .scalar_subquery()
    )
    last_login = (
        select(func.max(AuthSession.issued_at))
        .where(AuthSession.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    query = select(User, listing_count, last_login).order_by(User.created_at.desc(), User.id.desc())
    if search:
        query = query.where(User.name.ilike(f"%{search.strip()}%"))

    if status_filter == "deleted":
        query = query.where(User.deleted_at.is_not(None))
    else:
        query = query.where(User.deleted_at.is_(None))
        if status_filter == "restricted":
            query = query.where(_active_restriction_exists())
        elif status_filter in RESTRICTION_TYPES:
            query = query.where(_active_restriction_exists(restriction_type=status_filter))
        elif status_filter == "active":
            query = query.where(~_active_restriction_exists(), User.blocked.is_(False))

    if after_created_at is not None and after_id is not None:
        query = query.where(
            or_(
                User.created_at < after_created_at,
                and_(User.created_at == after_created_at, User.id < after_id),
            )
        )
        offset = 0

    rows = (await session.execute(query.limit(limit).offset(offset))).all()
    admin_emails = await _active_admin_emails(session)
    restrictions = await _active_restrictions_by_user(session, [user.id for user, _, _ in rows])
    return [
        public_user(
            user,
            listing_count=int(count or 0),
            last_login=last_seen,
            restriction=restrictions.get(user.id),
            is_admin=normalize_email(user.email) in admin_emails,
        )
        for user, count, last_seen in rows
    ]


async def get_user_detail(user_id: UUID, session: AsyncSession) -> AdminUserDetailResponse:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    count = await session.scalar(
        select(func.count()).select_from(Listing).where(
            Listing.owner_user_id == user.id,
            Listing.deleted_at.is_(None),
        )
    )
    last_login = await session.scalar(select(func.max(AuthSession.issued_at)).where(AuthSession.user_id == user.id))
    history = (
        await session.scalars(
            select(UserRestriction)
            .where(UserRestriction.user_id == user.id)
            .order_by(UserRestriction.starts_at.desc(), UserRestriction.id.desc())
            .limit(100)
        )
    ).all()
    active = await active_user_restriction(user.id, session)
    admin_row = await session.get(AdminAccess, normalize_email(user.email))
    base = public_user(
        user,
        listing_count=int(count or 0),
        last_login=last_login,
        restriction=active,
        is_admin=bool(admin_row and admin_row.active),
    )
    return AdminUserDetailResponse(
        **base.model_dump(),
        restrictions=[restriction_response(row) for row in history],
    )


async def restrict_user(
    user_id: UUID,
    *,
    restriction_type: str,
    until: datetime | None,
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
    if restriction_type not in RESTRICTION_TYPES:
        raise HTTPException(422, "Invalid restriction type")

    clean_reason = _clean_reason(reason)
    now = datetime.now(UTC)
    if until is not None:
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
        reason=clean_reason,
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
        body=f"{clean_reason} · {restriction_period_text(until).capitalize()} · Soporte: {SUPPORT_EMAIL}",
    )
    enqueue_restriction_email(
        session,
        target.email,
        restriction_type=restriction_type,
        reason=clean_reason,
        until=until,
    )
    if restriction_type == "full":
        sessions = (
            await session.scalars(
                select(AuthSession).where(
                    AuthSession.user_id == target.id,
                    AuthSession.revoked_at.is_(None),
                )
            )
        ).all()
        for auth_session in sessions:
            auth_session.revoked_at = now

    session.add(
        AuditLog(
            actor_id=actor.id,
            action="user.restricted",
            target_type="user",
            target_id=target.id,
            detail={
                "restrictionType": restriction_type,
                "until": until.isoformat() if until else None,
                "reason": clean_reason,
            },
        )
    )
    await touch_catalog(session)
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
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="user.unrestricted",
            target_type="user",
            target_id=target.id,
            detail={"restrictionId": str(current.id)},
        )
    )
    await touch_catalog(session)
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

    clean_reason = _clean_reason(reason)
    now = datetime.now(UTC)
    target.deleted_at = now
    sessions = (
        await session.scalars(
            select(AuthSession).where(
                AuthSession.user_id == target.id,
                AuthSession.revoked_at.is_(None),
            )
        )
    ).all()
    for auth_session in sessions:
        auth_session.revoked_at = now

    session.add(
        AuditLog(
            actor_id=actor.id,
            action="user.deleted",
            target_type="user",
            target_id=target.id,
            detail={"reason": clean_reason},
        )
    )
    enqueue_mail(
        session,
        kind="account_deleted_by_admin",
        recipient=target.email,
        subject="Tu cuenta ha sido eliminada",
        body=f"Tu cuenta se ha eliminado. Motivo: {clean_reason}\n\nSoporte: {SUPPORT_EMAIL}",
    )
    await touch_catalog(session)
    await session.commit()
