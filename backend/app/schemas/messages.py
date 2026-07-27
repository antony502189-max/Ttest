from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    listingId: UUID
    body: str = Field(min_length=1, max_length=4_000)


class ReplyMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4_000)


class MessageResponse(BaseModel):
    id: UUID
    threadId: UUID
    senderId: UUID
    body: str
    createdAt: datetime
    readAt: datetime | None


class ThreadResponse(BaseModel):
    id: UUID
    listingId: UUID
    tenantId: UUID
    hostId: UUID
    lastMessageAt: datetime
    createdAt: datetime
    updatedAt: datetime | None
    lastMessagePreview: str | None = None
