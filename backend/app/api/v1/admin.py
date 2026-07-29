from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import ExternalImportRun, User
from ...schemas.admin import (
    AdminListingResponse,
    AdminStatsResponse,
    AdminUserResponse,
    BlockUserRequest,
    ExternalImportRunResponse,
    ListingStatusRequest,
)
from ...services.admin import (
    change_listing_status,
    dashboard_stats,
    list_listings,
    list_users,
    set_user_blocked,
)
from ...workers.external_listings import run_once
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


@router.get("/external-import/runs", response_model=list[ExternalImportRunResponse])
async def external_import_runs(
    user: User = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)
):
    rows = (
        await session.scalars(select(ExternalImportRun).order_by(ExternalImportRun.started_at.desc()).limit(100))
    ).all()
    return [
        ExternalImportRunResponse(
            runId=row.run_id,
            source=row.source_name,
            startedAt=row.started_at,
            finishedAt=row.finished_at,
            result=row.result,
            counters=row.counters,
            lastError=row.last_error,
        )
        for row in rows
    ]


@router.post("/external-import/run")
async def trigger_external_import(user: User = Depends(require_role("admin"))):
    return await run_once()
