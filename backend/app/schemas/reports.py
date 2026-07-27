from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateReportRequest(BaseModel):
    listingId: UUID
    reason: str = Field(min_length=2, max_length=120)
    comment: str = Field(default="", max_length=4_000)


class ReportStatusRequest(BaseModel):
    status: str


class ReportResponse(BaseModel):
    id: UUID
    publicReference: str
    listingId: UUID
    reporterId: UUID | None
    reason: str
    comment: str
    status: str
    handledBy: UUID | None
    handledAt: datetime | None
    createdAt: datetime
