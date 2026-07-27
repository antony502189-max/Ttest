from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import User
from ...schemas.admin import (
    AdminListingResponse,
    AdminStatsResponse,
    AdminUserResponse,
    BlockUserRequest,
    ListingStatusRequest,
)
from ...services.admin import (
    change_listing_status,
    dashboard_stats,
    list_listings,
    list_users,
    set_user_blocked,
)
from ..dependencies import require_role

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsResponse)
async def stats(
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
):
    return await dashboard_stats(session)


@router.get("/listings", response_model=list[AdminListingResponse])
async def list_listings_route(
    status: str | None = None,
    search: str | None = None,
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
):
    return await list_listings(session, status, search)


@router.patch("/listings/{listing_id}/status", response_model=AdminListingResponse)
async def change_listing_status_route(
    listing_id: UUID,
    payload: ListingStatusRequest,
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
):
    return await change_listing_status(listing_id, payload.status, user, session)


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users_route(
    search: str | None = Query(default=None),
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
):
    return await list_users(session, search)


@router.patch("/users/{user_id}/blocked", response_model=AdminUserResponse)
async def set_user_blocked_route(
    user_id: UUID,
    payload: BlockUserRequest,
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
):
    return await set_user_blocked(user_id, payload.blocked, user, session)
