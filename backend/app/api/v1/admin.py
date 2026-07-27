from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import AuditLog, Listing, ListingStatusHistory, Report, User
from ...schemas.admin import (
    AdminListingResponse,
    AdminStatsResponse,
    AdminUserResponse,
    BlockUserRequest,
    ListingStatusRequest,
)
from ..dependencies import require_role

router = APIRouter(prefix="/admin", tags=["admin"])


def audit(actor_id: UUID, action: str, target_type: str, target_id: UUID, detail: dict) -> AuditLog:
    return AuditLog(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id, detail=detail)


@router.get("/stats", response_model=AdminStatsResponse)
async def stats(user: User = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    users, listings, pending, reports = (await session.execute(
        select(
            select(func.count()).select_from(User).scalar_subquery(),
            select(func.count()).select_from(Listing).scalar_subquery(),
            select(func.count()).select_from(Listing).where(Listing.status == "pending").scalar_subquery(),
            select(func.count()).select_from(Report).where(Report.status.in_(["open", "in_review"])).scalar_subquery(),
        )
    )).one()
    return AdminStatsResponse(users=users, listings=listings, pendingListings=pending, openReports=reports)


@router.get("/listings", response_model=list[AdminListingResponse])
async def list_listings(
    status: str | None = None, search: str | None = None, user: User = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)
):
    query = select(Listing).order_by(Listing.created_at.desc())
    if status:
        query = query.where(Listing.status == status)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(Listing.title.ilike(term) | Listing.city.ilike(term) | Listing.area.ilike(term))
    listings = (await session.scalars(query)).all()
    return [
        AdminListingResponse(
            id=listing.id, ownerUserId=listing.owner_user_id, title=listing.title, city=listing.city, area=listing.area,
            status=listing.status, rentalMode=listing.rental_mode,
        ) for listing in listings
    ]


@router.patch("/listings/{listing_id}/status", response_model=AdminListingResponse)
async def change_listing_status(
    listing_id: UUID, payload: ListingStatusRequest, user: User = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)
):
    if payload.status not in {"draft", "pending", "published", "hidden", "closed", "rejected"}:
        raise HTTPException(422, "Invalid listing status")
    listing = await session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    previous = listing.status
    listing.status = payload.status
    session.add(ListingStatusHistory(listing_id=listing.id, from_status=previous, to_status=listing.status, changed_by=user.id))
    session.add(audit(user.id, "listing.status_changed", "listing", listing.id, {"from": previous, "to": listing.status}))
    await session.commit()
    return AdminListingResponse(
        id=listing.id, ownerUserId=listing.owner_user_id, title=listing.title, city=listing.city, area=listing.area,
        status=listing.status, rentalMode=listing.rental_mode,
    )


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    search: str | None = Query(default=None), user: User = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)
):
    query = select(User).order_by(User.created_at.desc())
    if search:
        term = f"%{search.strip()}%"
        query = query.where(User.name.ilike(term) | User.email.ilike(term))
    users = (await session.scalars(query)).all()
    return [AdminUserResponse(id=item.id, email=item.email, name=item.name, role=item.role, blocked=item.blocked) for item in users]


@router.patch("/users/{user_id}/blocked", response_model=AdminUserResponse)
async def set_user_blocked(
    user_id: UUID, payload: BlockUserRequest, user: User = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)
):
    target = await session.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == user.id and payload.blocked:
        raise HTTPException(422, "Administrators cannot block themselves")
    target.blocked = payload.blocked
    session.add(audit(user.id, "user.block_changed", "user", target.id, {"blocked": target.blocked}))
    await session.commit()
    return AdminUserResponse(id=target.id, email=target.email, name=target.name, role=target.role, blocked=target.blocked)
