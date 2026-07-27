from __future__ import annotations

from datetime import UTC, datetime
from secrets import token_hex
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, Listing, Report, User
from ..schemas.reports import CreateReportRequest, ReportResponse


def public_report(report: Report) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        publicReference=report.public_reference,
        listingId=report.listing_id,
        reporterId=report.reporter_id,
        reason=report.reason,
        comment=report.comment,
        status=report.status,
        handledBy=report.handled_by,
        handledAt=report.handled_at,
        createdAt=report.created_at,
    )


async def create_report(payload: CreateReportRequest, user: User | None, session: AsyncSession) -> ReportResponse:
    listing = await session.get(Listing, payload.listingId)
    if not listing or listing.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
    report = Report(
        public_reference=f"R-{token_hex(5).upper()}",
        listing_id=payload.listingId,
        reporter_id=user.id if user else None,
        reason=payload.reason.strip(),
        comment=payload.comment.strip(),
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return public_report(report)


async def list_reports(session: AsyncSession) -> list[ReportResponse]:
    reports = (await session.scalars(select(Report).order_by(Report.created_at.desc()))).all()
    return [public_report(report) for report in reports]


async def update_report(report_id: UUID, new_status: str, user: User, session: AsyncSession) -> ReportResponse:
    if new_status not in {"open", "in_review", "resolved", "rejected"}:
        raise HTTPException(422, "Invalid report status")
    report = await session.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    report.status = new_status
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
