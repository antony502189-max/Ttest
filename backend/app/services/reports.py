from __future__ import annotations

from datetime import UTC, datetime
from secrets import token_hex
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, Listing, Report, User
from ..models.moderation import ListingRestriction, UserReportTarget, UserRestriction
from ..schemas.reports import CreateReportRequest, ReportResponse
from .moderation import active_window


def public_report(report: Report, target_user_id: UUID | None = None) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        publicReference=report.public_reference,
        listingId=report.listing_id,
        targetType="user" if target_user_id else "listing",
        targetUserId=target_user_id,
        reporterId=report.reporter_id,
        reason=report.reason,
        comment=report.comment,
        status=report.status,
        handledBy=report.handled_by,
        handledAt=report.handled_at,
        createdAt=report.created_at,
    )


async def create_report(payload: CreateReportRequest, user: User | None, session: AsyncSession) -> ReportResponse:
    active_owner_restriction = (
        select(UserRestriction.id)
        .where(UserRestriction.user_id == User.id, *active_window(UserRestriction))
        .correlate(User)
        .exists()
    )
    active_listing_restriction = (
        select(ListingRestriction.id)
        .where(ListingRestriction.listing_id == Listing.id, *active_window(ListingRestriction))
        .correlate(Listing)
        .exists()
    )
    row = (
        await session.execute(
            select(Listing, User)
            .join(User, User.id == Listing.owner_user_id)
            .where(
                Listing.id == payload.listingId,
                Listing.status == "published",
                Listing.deleted_at.is_(None),
                (Listing.expires_at.is_(None)) | (Listing.expires_at > func.now()),
                User.deleted_at.is_(None),
                User.blocked.is_(False),
                ~active_owner_restriction,
                ~active_listing_restriction,
            )
        )
    ).one_or_none()
    if not row:
        raise HTTPException(404, "Listing not found")
    listing, owner = row
    if user and owner.id == user.id:
        raise HTTPException(422, "You cannot report your own listing or account")

    report = Report(
        public_reference=f"R-{token_hex(5).upper()}",
        listing_id=listing.id,
        reporter_id=user.id if user else None,
        reason=payload.reason,
        comment=payload.comment,
    )
    session.add(report)
    await session.flush()

    target_user_id: UUID | None = None
    if payload.targetType == "user":
        target_user_id = owner.id
        session.add(UserReportTarget(report_id=report.id, target_user_id=owner.id))

    await session.commit()
    await session.refresh(report)
    return public_report(report, target_user_id)


async def list_reports(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    after_created_at: datetime | None = None,
    after_id: UUID | None = None,
) -> list[ReportResponse]:
    query = (
        select(Report, UserReportTarget.target_user_id)
        .outerjoin(UserReportTarget, UserReportTarget.report_id == Report.id)
        .order_by(Report.created_at.desc(), Report.id.desc())
    )
    if after_created_at is not None and after_id is not None:
        query = query.where(
            or_(
                Report.created_at < after_created_at,
                and_(Report.created_at == after_created_at, Report.id < after_id),
            )
        )
        offset = 0
    rows = (await session.execute(query.limit(limit).offset(offset))).all()
    return [public_report(report, target_user_id) for report, target_user_id in rows]


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
    target_user_id = await session.scalar(
        select(UserReportTarget.target_user_id).where(UserReportTarget.report_id == report.id)
    )
    return public_report(report, target_user_id)
