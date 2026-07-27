from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, Listing, ListingStatusHistory, Report, User
from ..schemas.admin import AdminListingResponse, AdminStatsResponse, AdminUserResponse


def audit(actor_id: UUID, action: str, target_type: str, target_id: UUID, detail: dict) -> AuditLog:
    return AuditLog(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id, detail=detail)


def public_listing(listing: Listing) -> AdminListingResponse:
    return AdminListingResponse(
        id=listing.id,
        ownerUserId=listing.owner_user_id,
        title=listing.title,
        city=listing.city,
        area=listing.area,
        status=listing.status,
        rentalMode=listing.rental_mode,
    )


def public_user(user: User) -> AdminUserResponse:
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


async def list_listings(session: AsyncSession, status: str | None, search: str | None) -> list[AdminListingResponse]:
    query = select(Listing).where(Listing.deleted_at.is_(None)).order_by(Listing.created_at.desc())
    if status:
        query = query.where(Listing.status == status)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(Listing.title.ilike(term) | Listing.city.ilike(term) | Listing.area.ilike(term))
    return [public_listing(listing) for listing in (await session.scalars(query)).all()]


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
    return public_listing(listing)


async def list_users(session: AsyncSession, search: str | None) -> list[AdminUserResponse]:
    query = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    if search:
        term = f"%{search.strip()}%"
        query = query.where(User.name.ilike(term) | User.email.ilike(term))
    return [public_user(user) for user in (await session.scalars(query)).all()]


async def set_user_blocked(
    user_id: UUID,
    blocked: bool,
    actor: User,
    session: AsyncSession,
) -> AdminUserResponse:
    target = await session.get(User, user_id)
    if not target or target.deleted_at is not None:
        raise HTTPException(404, "User not found")
    if target.id == actor.id and blocked:
        raise HTTPException(422, "Administrators cannot block themselves")
    target.blocked = blocked
    session.add(audit(actor.id, "user.block_changed", "user", target.id, {"blocked": blocked}))
    await session.commit()
    return public_user(target)
