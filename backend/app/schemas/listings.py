from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ListingWrite(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    city: str = Field(min_length=2, max_length=120)
    area: str = Field(min_length=1, max_length=120)
    street: str = Field(default="", max_length=160)
    postcode: str = Field(default="", max_length=32)
    approximateAddress: str = Field(min_length=2, max_length=240)
    rentalMode: str
    monthlyPrice: int | None = Field(default=None, ge=0)
    nightlyPrice: int | None = Field(default=None, ge=0)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    exactLatitude: float | None = Field(default=None, ge=-90, le=90)
    exactLongitude: float | None = Field(default=None, ge=-180, le=180)
    description: str = Field(default="", max_length=10_000)

    @model_validator(mode="after")
    def validate_price_for_mode(self):
        if self.rentalMode not in {"long", "holiday"}:
            raise ValueError("rentalMode must be long or holiday")
        if self.rentalMode == "long" and self.monthlyPrice is None:
            raise ValueError("monthlyPrice is required for long rentals")
        if self.rentalMode == "holiday" and self.nightlyPrice is None:
            raise ValueError("nightlyPrice is required for holiday rentals")
        if (self.exactLatitude is None) != (self.exactLongitude is None):
            raise ValueError("exactLatitude and exactLongitude must be provided together")
        return self


class ListingPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=240)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    area: str | None = Field(default=None, min_length=1, max_length=120)
    street: str | None = Field(default=None, max_length=160)
    postcode: str | None = Field(default=None, max_length=32)
    approximateAddress: str | None = Field(default=None, min_length=2, max_length=240)
    monthlyPrice: int | None = Field(default=None, ge=0)
    nightlyPrice: int | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    exactLatitude: float | None = Field(default=None, ge=-90, le=90)
    exactLongitude: float | None = Field(default=None, ge=-180, le=180)
    description: str | None = Field(default=None, max_length=10_000)
    status: str | None = None


class ListingResponse(BaseModel):
    id: str
    ownerUserId: str
    title: str
    city: str
    area: str
    approximateAddress: str
    rentalMode: str
    monthlyPrice: int | None
    nightlyPrice: int | None
    status: str
    latitude: float
    longitude: float
    description: str
    createdAt: datetime
    updatedAt: datetime | None


class OwnedListingResponse(ListingResponse):
    """Private fields exposed only from owner/admin endpoints."""

    street: str
    postcode: str
    exactLatitude: float | None
    exactLongitude: float | None


class ListingImagesRequest(BaseModel):
    assetIds: list[UUID] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_assets(self):
        if len(set(self.assetIds)) != len(self.assetIds):
            raise ValueError("assetIds must be unique")
        return self


class ListingImageResponse(BaseModel):
    assetId: UUID
    url: str
    sortOrder: int
    isCover: bool
