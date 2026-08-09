from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import User
from ...schemas.reports import CreateReportRequest, ReportResponse, ReportStatusRequest
from ...services.reports import create_report, list_reports, update_report
from ..dependencies import optional_user, require_admin

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report_route(
    payload: CreateReportRequest,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_report(payload, user, session)


@router.get("", response_model=list[ReportResponse])
async def list_reports_route(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10_000),
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await list_reports(session, limit=limit, offset=offset)


@router.patch("/{report_id}", response_model=ReportResponse)
async def update_report_route(
    report_id: UUID,
    payload: ReportStatusRequest,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await update_report(report_id, payload.status, user, session)
