from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...db.session import get_session
from ...models import ExternalImportRun, ExternalWorkerState, Listing, User
from ...models.moderation import AdminAccess
from ...schemas.admin import (
    AddAdminRequest,
    AdminAccessResponse,
    AdminListingResponse,
    AdminNoteRequest,
    AdminNoteResponse,
    AdminStatsResponse,
    AdminUserDetailResponse,
    AdminUserResponse,
    AuditLogResponse,
    DeleteUserRequest,
    ExternalImportRunResponse,
    ExternalWorkerStateResponse,
    ListingRestrictionRequest,
    ListingStatusRequest,
    UserRestrictionRequest,
)
from ...services.admin import (
    add_admin,
    add_note,
    change_listing_status,
    dashboard_stats,
    list_admins,
    list_audit_logs,
    list_notes,
    restrict_listing,
    revoke_admin,
    unrestrict_listing,
)
from ...services.admin_listings import list_listings
from ...services.admin_users import (
    get_user_detail,
    list_users,
    restrict_user,
    soft_delete_user,
    unrestrict_user,
)
from ...workers.external_listings import run_once
from ..dependencies import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


async def _lock_user_mutation(user_id: UUID, session: AsyncSession) -> None:
    """Serialize moderation writes for one user to prevent overlapping active restrictions."""
    await session.scalar(select(User.id).where(User.id == user_id).with_for_update())


async def _lock_listing_mutation(listing_id: UUID, session: AsyncSession) -> None:
    """Serialize moderation/status writes for one listing."""
    await session.scalar(select(Listing.id).where(Listing.id == listing_id).with_for_update())


async def _lock_admin_access(session: AsyncSession) -> None:
    """Serialize allowlist changes so concurrent revocations cannot remove every administrator."""
    (
        await session.scalars(
            select(AdminAccess.email)
            .where(AdminAccess.active.is_(True))
            .order_by(AdminAccess.email)
            .with_for_update()
        )
    ).all()


@router.get("/access")
async def admin_access(user: User = Depends(require_admin)):
    return {"isAdmin": True, "email": user.email}


@router.get("/stats", response_model=AdminStatsResponse)
async def stats(
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await dashboard_stats(session)


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users_route(
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await list_users(session, search, status_filter=status_filter, limit=limit, offset=offset)


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_route(
    user_id: UUID,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await get_user_detail(user_id, session)


@router.post("/users/{user_id}/restrictions", response_model=AdminUserDetailResponse)
async def restrict_user_route(
    user_id: UUID,
    payload: UserRestrictionRequest,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await _lock_user_mutation(user_id, session)
    return await restrict_user(
        user_id,
        restriction_type=payload.restrictionType,
        until=payload.until,
        reason=payload.reason,
        actor=user,
        session=session,
    )


@router.delete("/users/{user_id}/restrictions/active", response_model=AdminUserDetailResponse)
async def unrestrict_user_route(
    user_id: UUID,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await _lock_user_mutation(user_id, session)
    return await unrestrict_user(user_id, user, session)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_route(
    user_id: UUID,
    payload: DeleteUserRequest,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await _lock_user_mutation(user_id, session)
    await soft_delete_user(user_id, reason=payload.reason, actor=user, session=session)


@router.get("/users/{user_id}/notes", response_model=list[AdminNoteResponse])
async def list_notes_route(
    user_id: UUID,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await list_notes(user_id, session)


@router.post("/users/{user_id}/notes", response_model=AdminNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_note_route(
    user_id: UUID,
    payload: AdminNoteRequest,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await add_note(user_id, payload.body, user, session)


@router.get("/listings", response_model=list[AdminListingResponse])
async def list_listings_route(
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    restricted: bool | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await list_listings(
        session,
        status_filter,
        search,
        restricted=restricted,
        limit=limit,
        offset=offset,
    )


@router.patch("/listings/{listing_id}/status", response_model=AdminListingResponse)
async def change_listing_status_route(
    listing_id: UUID,
    payload: ListingStatusRequest,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await _lock_listing_mutation(listing_id, session)
    return await change_listing_status(listing_id, payload.status, user, session)


@router.post("/listings/{listing_id}/restrictions", response_model=AdminListingResponse)
async def restrict_listing_route(
    listing_id: UUID,
    payload: ListingRestrictionRequest,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await _lock_listing_mutation(listing_id, session)
    return await restrict_listing(
        listing_id,
        until=payload.until,
        reason=payload.reason,
        actor=user,
        session=session,
    )


@router.delete("/listings/{listing_id}/restrictions/active", response_model=AdminListingResponse)
async def unrestrict_listing_route(
    listing_id: UUID,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await _lock_listing_mutation(listing_id, session)
    return await unrestrict_listing(listing_id, user, session)


@router.get("/admins", response_model=list[AdminAccessResponse])
async def list_admins_route(
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await list_admins(session)


@router.post("/admins", response_model=AdminAccessResponse, status_code=status.HTTP_201_CREATED)
async def add_admin_route(
    payload: AddAdminRequest,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await _lock_admin_access(session)
    return await add_admin(str(payload.email), user, session)


@router.delete("/admins/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_admin_route(
    email: str,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await _lock_admin_access(session)
    await revoke_admin(email, user, session)


@router.get("/audit-log", response_model=list[AuditLogResponse])
async def audit_log_route(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await list_audit_logs(session, limit=limit, offset=offset)


@router.get("/external-import/runs", response_model=list[ExternalImportRunResponse])
async def external_import_runs(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.scalars(
            select(ExternalImportRun)
            .order_by(ExternalImportRun.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
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
            challengeType=row.challenge_type,
            httpStatus=row.http_status,
            finalUrl=row.final_url,
            nextCheckAt=row.next_check_at,
            diagnosticPaths=row.diagnostic_paths,
            discoveryComplete=row.discovery_complete,
            discoveryPages=row.discovery_pages,
            discoveryFailedPages=row.discovery_failed_pages,
        )
        for row in rows
    ]


@router.get("/external-import/worker", response_model=ExternalWorkerStateResponse)
async def external_import_worker_state(
    user: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    state = await session.get(ExternalWorkerState, 1)
    if not state:
        return ExternalWorkerStateResponse(
            health="delayed",
            lastStartedAt=None,
            lastFinishedAt=None,
            lastSuccessAt=None,
            nextRunAt=None,
            heartbeatAt=None,
            lastError=None,
            lastRunId=None,
        )
    heartbeat_deadline = datetime.now(UTC) - timedelta(
        seconds=get_settings().external_worker_stale_after_seconds
    )
    health = (
        "delayed"
        if state.health != "failed" and (state.heartbeat_at is None or state.heartbeat_at < heartbeat_deadline)
        else state.health
    )
    return ExternalWorkerStateResponse(
        health=health,
        lastStartedAt=state.last_started_at,
        lastFinishedAt=state.last_finished_at,
        lastSuccessAt=state.last_success_at,
        nextRunAt=state.next_run_at,
        heartbeatAt=state.heartbeat_at,
        lastError=state.last_error,
        lastRunId=state.last_run_id,
    )


@router.post("/external-import/run")
async def trigger_external_import(user: User = Depends(require_admin)):
    return await run_once()
