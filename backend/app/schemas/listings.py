from datetime import date, datetime
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
    weeklyPrice: int | None = Field(default=None, ge=0)
    roomType: str = Field(default="Habitación individual", max_length=64)
    availableFrom: date | None = None
    availableUntil: date | None = None
    minimumStayMonths: int = Field(default=0, ge=0)
    minimumNights: int | None = Field(default=None, ge=0)
    depositAmount: int = Field(default=0, ge=0)
    billsIncluded: bool = False
    bathroom: str = Field(default="Baño compartido", max_length=64)
    kitchen: str = Field(default="Cocina compartida", max_length=64)
    furnished: bool = True
    roomSizeM2: int = Field(default=1, ge=1, le=10_000)
    bedroomCount: int | None = Field(default=None, ge=1, le=99)
    currentResidents: int = Field(default=0, ge=0)
    roomCapacity: int = Field(default=1, ge=1, le=2)
    shower: str = Field(default="Ducha compartida", max_length=64)
    tenantRequirement: str = Field(default="any", max_length=32)
    smokingAllowed: bool = False
    petsAllowed: bool = False
    childrenAllowed: bool = False
    empadronamientoAllowed: bool = False
    restrictions: list[str] = Field(default_factory=list, max_length=100)
    amenities: list[str] = Field(default_factory=list, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    exactLatitude: float | None = Field(default=None, ge=-90, le=90)
    exactLongitude: float | None = Field(default=None, ge=-180, le=180)
    description: str = Field(default="", max_length=10_000)
    homeDescription: str = Field(default="", max_length=10_000)
    advertiserType: str = Field(default="Particular", max_length=32)
    source: str | None = Field(default=None, max_length=120)
    expiresAt: datetime | None = None

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
        if self.availableFrom and self.availableUntil and self.availableUntil < self.availableFrom:
            raise ValueError("availableUntil cannot be before availableFrom")
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
    weeklyPrice: int | None = Field(default=None, ge=0)
    roomType: str | None = Field(default=None, max_length=64)
    availableFrom: date | None = None
    availableUntil: date | None = None
    minimumStayMonths: int | None = Field(default=None, ge=0)
    minimumNights: int | None = Field(default=None, ge=0)
    depositAmount: int | None = Field(default=None, ge=0)
    billsIncluded: bool | None = None
    bathroom: str | None = Field(default=None, max_length=64)
    kitchen: str | None = Field(default=None, max_length=64)
    furnished: bool | None = None
    roomSizeM2: int | None = Field(default=None, ge=1, le=10_000)
    bedroomCount: int | None = Field(default=None, ge=1, le=99)
    currentResidents: int | None = Field(default=None, ge=0)
    roomCapacity: int | None = Field(default=None, ge=1, le=2)
    shower: str | None = Field(default=None, max_length=64)
    tenantRequirement: str | None = Field(default=None, max_length=32)
    smokingAllowed: bool | None = None
    petsAllowed: bool | None = None
    childrenAllowed: bool | None = None
    empadronamientoAllowed: bool | None = None
    restrictions: list[str] | None = Field(default=None, max_length=100)
    amenities: list[str] | None = Field(default=None, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    exactLatitude: float | None = Field(default=None, ge=-90, le=90)
    exactLongitude: float | None = Field(default=None, ge=-180, le=180)
    description: str | None = Field(default=None, max_length=10_000)
    homeDescription: str | None = Field(default=None, max_length=10_000)
    advertiserType: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=120)
    expiresAt: datetime | None = None
    status: str | None = None


class ListingResponse(BaseModel):
    id: str
    ownerUserId: str
    owner: "ListingOwnerResponse"
    contactPhone: str | None
    contactWhatsapp: str | None
    contactEmail: str | None
    showPhone: bool
    showWhatsApp: bool
    allowContactForm: bool
    coverImageUrl: str | None
    imageUrls: list[str]
    title: str
    city: str
    area: str
    approximateAddress: str
    rentalMode: str
    monthlyPrice: int | None
    nightlyPrice: int | None
    weeklyPrice: int | None
    price: int | None
    cadence: str
    roomType: str
    availableFrom: date | None
    availableUntil: date | None
    minimumStayMonths: int
    minimumNights: int | None
    depositAmount: int
    billsIncluded: bool
    bathroom: str
    kitchen: str
    furnished: bool
    roomSizeM2: int
    bedroomCount: int | None
    currentResidents: int
    roomCapacity: int
    shower: str
    tenantRequirement: str
    smokingAllowed: bool
    petsAllowed: bool
    childrenAllowed: bool
    empadronamientoAllowed: bool
    restrictions: list[str]
    amenities: list[str]
    status: str
    latitude: float
    longitude: float
    description: str
    homeDescription: str
    advertiserType: str
    source: str | None
    publishedAt: datetime | None
    expiresAt: datetime | None
    views: int
    closedReason: str | None
    createdAt: datetime
    updatedAt: datetime | None


class ListingOwnerResponse(BaseModel):
    name: str
    initials: str
    since: datetime | None
    response: str
    verified: bool


class OwnedListingResponse(ListingResponse):
    """Private fields exposed only from owner/admin endpoints."""

    street: str
    postcode: str
    exactLatitude: float | None
    exactLongitude: float | None


class SearchPoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ListingSearchRequest(BaseModel):
    city: str | None = Field(default=None, max_length=120)
    area: str | None = Field(default=None, max_length=120)
    rentalMode: str | None = None
    minPrice: int | None = Field(default=None, ge=0)
    maxPrice: int | None = Field(default=None, ge=0)
    minLatitude: float | None = Field(default=None, ge=-90, le=90)
    maxLatitude: float | None = Field(default=None, ge=-90, le=90)
    minLongitude: float | None = Field(default=None, ge=-180, le=180)
    maxLongitude: float | None = Field(default=None, ge=-180, le=180)
    center: SearchPoint | None = None
    radiusKm: float | None = Field(default=None, gt=0, le=100)
    polygon: list[SearchPoint] = Field(default_factory=list, max_length=100)
    sort: str = "newest"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_geo_filters(self):
        bounds = (self.minLatitude, self.maxLatitude, self.minLongitude, self.maxLongitude)
        if any(value is not None for value in bounds) and any(value is None for value in bounds):
            raise ValueError("all bounding-box coordinates are required")
        if self.minLatitude is not None and (self.minLatitude >= self.maxLatitude or self.minLongitude >= self.maxLongitude):
            raise ValueError("bounding-box minimums must be below maximums")
        if (self.center is None) != (self.radiusKm is None):
            raise ValueError("center and radiusKm must be provided together")
        if self.rentalMode not in {None, "long", "holiday"}:
            raise ValueError("rentalMode must be long or holiday")
        if self.sort not in {"newest", "price_asc", "price_desc"}:
            raise ValueError("sort must be newest, price_asc, or price_desc")
        if self.polygon:
            if len(self.polygon) < 3:
                raise ValueError("polygon needs at least three points")
            if self.polygon[0] != self.polygon[-1]:
                self.polygon.append(self.polygon[0])
        return self


class ListingSearchResponse(BaseModel):
    items: list[ListingResponse]
    total: int
    limit: int
    offset: int


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
