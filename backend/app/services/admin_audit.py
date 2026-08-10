from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, User
from ..schemas.admin import AuditLogResponse


async def list_audit_logs(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    after_created_at: datetime | None = None,
    after_id: UUID | None = None,
) -> list[AuditLogResponse]:
    query = (
        select(AuditLog, User.name)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    if after_created_at is not None and after_id is not None:
        query = query.where(
            or_(
                AuditLog.created_at < after_created_at,
                and_(AuditLog.created_at == after_created_at, AuditLog.id < after_id),
            )
        )
        offset = 0
    rows = (await session.execute(query.limit(limit).offset(offset))).all()
    return [
        AuditLogResponse(
            id=row.id,
            actorId=row.actor_id,
            actorName=actor_name,
            action=row.action,
            targetType=row.target_type,
            targetId=row.target_id,
            detail=row.detail,
            createdAt=row.created_at,
        )
        for row, actor_name in rows
    ]
