from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

RestrictionType = Literal["full", "publish", "view_listings"]


class ListingStatusRequest(BaseModel):
    status: Literal["draft", "pending", "published", "hidden", "closed", "rejected"]


class BlockUserRequest(BaseModel):
    """Legacy compatibility payload. New UI uses dated restrictions."""

    blocked: bool


class UserRestrictionRequest(BaseModel):
    restrictionType: RestrictionType
    until: datetime
    reason: str = Field(min_length=2, max_length=4_000)


class ListingRestrictionRequest(BaseModel):
    until: datetime
    reason: str = Field(min_length=2, max_length=4_000)


class DeleteUserRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=4_000)


class AdminNoteRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4_000)


class AddAdminRequest(BaseModel):
    email: EmailStr


class AdminStatsResponse(BaseModel):
    users: int
    listings: int
    pendingListings: int
    openReports: int


class RestrictionResponse(BaseModel):
    id: UUID
    restrictionType: str
    reason: str
    startsAt: datetime
    endsAt: datetime
    revokedAt: datetime | None
    active: bool


class ListingRestrictionResponse(BaseModel):
    id: UUID
    reason: str
    startsAt: datetime
    endsAt: datetime
    revokedAt: datetime | None
    active: bool


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
    createdAt: datetime
    deletedAt: datetime | None = None
    lastLoginAt: datetime | None = None
    listingCount: int = 0
    activeRestriction: RestrictionResponse | None = None
    isAdmin: bool = False


class AdminUserDetailResponse(AdminUserResponse):
    restrictions: list[RestrictionResponse] = Field(default_factory=list)


class AdminListingResponse(BaseModel):
    id: UUID
    ownerUserId: UUID
    ownerName: str | None = None
    ownerEmail: str | None = None
    title: str
    city: str
    area: str
    status: str
    rentalMode: str
    views: int = 0
    createdAt: datetime
    deletedAt: datetime | None = None
    activeRestriction: ListingRestrictionResponse | None = None


class AdminNoteResponse(BaseModel):
    id: UUID
    userId: UUID
    body: str
    createdBy: UUID | None
    createdByName: str | None = None
    createdAt: datetime


class AdminAccessResponse(BaseModel):
    email: str
    active: bool
    createdBy: UUID | None
    createdAt: datetime


class AuditLogResponse(BaseModel):
    id: UUID
    actorId: UUID | None
    actorName: str | None = None
    action: str
    targetType: str
    targetId: UUID | None
    detail: dict
    createdAt: datetime


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
