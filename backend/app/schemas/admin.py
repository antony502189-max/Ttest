from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ListingStatusRequest(BaseModel):
    status: Literal["draft", "pending", "published", "hidden", "closed", "rejected"]


class BlockUserRequest(BaseModel):
    blocked: bool


class AdminStatsResponse(BaseModel):
    users: int
    listings: int
    pendingListings: int
    openReports: int


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    blocked: bool
    phone: str
    whatsapp: str
    telegram: str
    about: str
    initials: str
    showPhone: bool
    showWhatsApp: bool
    allowContactForm: bool
    avatarUrl: str | None = None


class AdminListingResponse(BaseModel):
    id: UUID
    ownerUserId: UUID
    title: str
    city: str
    area: str
    status: str
    rentalMode: str


class ExternalImportRunResponse(BaseModel):
    runId: str
    source: str
    startedAt: datetime
    finishedAt: datetime | None
    result: str
    counters: dict
    lastError: str | None
    challengeType: str | None = None
    httpStatus: int | None = None
    finalUrl: str | None = None
    nextCheckAt: datetime | None = None
    diagnosticPaths: dict = Field(default_factory=dict)
    discoveryComplete: bool | None = None
    discoveryPages: int | None = None
    discoveryFailedPages: list[str] = Field(default_factory=list)


class ExternalWorkerStateResponse(BaseModel):
    health: str
    lastStartedAt: datetime | None
    lastFinishedAt: datetime | None
    lastSuccessAt: datetime | None
    nextRunAt: datetime | None
    heartbeatAt: datetime | None
    lastError: str | None
    lastRunId: str | None
