from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

DestinationType = Literal["website", "phone", "whatsapp", "email"]


class AdvertisementWrite(BaseModel):
    title: str = Field(min_length=3, max_length=90)
    description: str = Field(min_length=10, max_length=300)
    imageAssetId: UUID
    destinationType: DestinationType
    destination: str = Field(min_length=3, max_length=2048)
    packageId: Literal["test_homepage_30d"] = "test_homepage_30d"

    @field_validator("title", "description")
    @classmethod
    def plain_text(cls, value: str, info) -> str:
        value = value.strip()
        if len(value) < (3 if info.field_name == "title" else 10):
            raise ValueError("Advertising text is too short")
        if any(ord(char) < 32 and char not in "\n\t" for char in value) or "<" in value or ">" in value:
            raise ValueError("Plain text only")
        return value

    @model_validator(mode="after")
    def validate_destination(self) -> "AdvertisementWrite":
        from ..services.commercial_advertisements import normalize_destination

        self.destination = normalize_destination(self.destinationType, self.destination)
        return self


class AdvertisementPublic(BaseModel):
    id: UUID
    title: str
    description: str
    imageUrl: str
    imageWidth: int
    imageHeight: int
    destinationType: DestinationType
    destinationUrl: str
    placement: str


class AdvertisementDetail(BaseModel):
    id: UUID
    ownerUserId: UUID
    title: str
    description: str
    imageAssetId: UUID
    imageUrl: str
    destinationType: DestinationType
    destination: str
    status: str
    paymentStatus: str
    packageId: str
    placement: str
    createdAt: datetime
    startsAt: datetime | None
    endsAt: datetime | None
    moderationNote: str | None


class AdvertisementAdminDetail(AdvertisementDetail):
    ownerEmail: str
    adminPriority: int


class ModerationDecision(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
    startsAt: datetime | None = None
    endsAt: datetime | None = None


class CheckoutResponse(BaseModel):
    advertisementId: UUID
    packageId: str
    displayPrice: str
    paymentMode: Literal["test"] = "test"
