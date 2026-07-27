from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateReportRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    listingId: UUID
    reason: str = Field(min_length=2, max_length=120)
    comment: str = Field(default="", max_length=4_000)


class ReportStatusRequest(BaseModel):
    status: Literal["open", "in_review", "resolved", "rejected"]


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
