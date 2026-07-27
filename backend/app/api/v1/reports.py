from datetime import UTC, datetime
from secrets import token_hex
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import AuditLog, Listing, Report, User
from ...schemas.reports import CreateReportRequest, ReportResponse, ReportStatusRequest
from ..dependencies import current_user, require_role

router = APIRouter(prefix="/reports", tags=["reports"])


def public_report(report: Report) -> ReportResponse:
    return ReportResponse(
        id=report.id, publicReference=report.public_reference, listingId=report.listing_id, reporterId=report.reporter_id,
        reason=report.reason, comment=report.comment, status=report.status, handledBy=report.handled_by,
        handledAt=report.handled_at, createdAt=report.created_at,
    )


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: CreateReportRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    if not await session.get(Listing, payload.listingId):
        raise HTTPException(404, "Listing not found")
    report = Report(
        public_reference=f"R-{token_hex(5).upper()}", listing_id=payload.listingId, reporter_id=user.id,
        reason=payload.reason.strip(), comment=payload.comment.strip(),
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return public_report(report)


@router.get("", response_model=list[ReportResponse])
async def list_reports(user: User = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    reports = (await session.scalars(select(Report).order_by(Report.created_at.desc()))).all()
    return [public_report(report) for report in reports]


@router.patch("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: UUID, payload: ReportStatusRequest, user: User = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)
):
    if payload.status not in {"open", "in_review", "resolved", "rejected"}:
        raise HTTPException(422, "Invalid report status")
    report = await session.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    report.status = payload.status
    report.handled_by = user.id
    report.handled_at = datetime.now(UTC)
    session.add(
        AuditLog(
            actor_id=user.id,
            action="report.status_changed",
            target_type="report",
            target_id=report.id,
            detail={"status": report.status},
        )
    )
    await session.commit()
    await session.refresh(report)
    return public_report(report)
