from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MyRestrictionResponse(BaseModel):
    restrictionType: str
    reason: str
    until: datetime | None
    supportEmail: str


class ModerationNoticeResponse(BaseModel):
    id: UUID
    kind: str
    title: str
    body: str
    createdAt: datetime
    readAt: datetime | None
