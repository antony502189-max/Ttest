from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    entityListingId: UUID | None
    title: str
    body: str
    createdAt: datetime
    readAt: datetime | None


class NotificationPage(BaseModel):
    items: list[NotificationResponse]
    unreadCount: int = Field(ge=0)
