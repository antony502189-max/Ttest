import re
from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..content_safety import contains_listing_link
from ..core.media_limits import MAX_LISTING_PHOTOS

ALLOWED_ROOM_TYPES = {"Habitación individual", "Habitación compartida", "Estudio"}
ALLOWED_LISTING_STATUSES = {"draft", "pending", "published", "hidden", "closed", "rejected"}
ALLOWED_RENTAL_UNITS = {"room", "bed"}
ALLOWED_BED_TYPES = {"single", "double", "bunk"}
ALLOWED_TOILETS = {"Aseo privado", "Aseo compartido"}
ALLOWED_HOUSEHOLD_GENDERS = {"men", "women", "mixed", "unknown"}
ALLOWED_HEATING_TYPES = {"individual", "central", "none", "unknown"}
ALLOWED_FLOORS = {"basement", "1", "2", "3", "4+", "top"}
ALLOWED_TENANT_TYPES = {"man", "woman", "couple", "family"}
ALLOWED_TENANT_REQUIREMENTS = {"single-man", "single-woman", "single-person", "couple", "any"}
ALLOWED_ADVERTISER_TYPES = {"Particular", "Profesional"}
PHONE_PATTERN = re.compile(r"^\+?[\d\s-]{7,64}$")

LINK_BLOCKED_TEXT_FIELDS = (
    "title",
    "city",
    "area",
    "approximateAddress",
    "billsText",
    "bathroom",
    "kitchen",
    "shower",
    "description",
    "homeDescription",
)
LINK_BLOCKED_LIST_FIELDS = ("restrictions", "amenities")


def _validate_link_free_listing_fields(model: BaseModel, only_fields: set[str] | None = None) -> None:
    for field_name in LINK_BLOCKED_TEXT_FIELDS:
        if only_fields is not None and field_name not in only_fields:
            continue
        value = getattr(model, field_name, None)
        if isinstance(value, str) and contains_listing_link(value):
            raise ValueError(f"{field_name} must not contain links or URL-like text")

    for field_name in LINK_BLOCKED_LIST_FIELDS:
        if only_fields is not None and field_name not in only_fields:
            continue
        values = getattr(model, field_name, None)
        if values and any(isinstance(value, str) and contains_listing_link(value) for value in values):
            raise ValueError(f"{field_name} must not contain links or URL-like text")


class CatalogVersionResponse(BaseModel):
    version: str
    updatedAt: datetime


class ListingWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

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
    billsText: str | None = Field(default=None, max_length=240)
    bathroom: str = Field(default="Baño compartido", max_length=64)
    kitchen: str = Field(default="Cocina compartida", max_length=64)
    furnished: bool = True
    roomSizeM2: int = Field(default=1, ge=1, le=10_000)
    bedroomCount: int | None = Field(default=None, ge=1, le=99)
    currentResidents: int = Field(default=0, ge=0)
    roomCapacity: int = Field(default=1, ge=1, le=10)
    shower: str = Field(default="Ducha compartida", max_length=64)
    tenantRequirement: str = Field(default="any", max_length=32)
    smokingAllowed: bool = False
    petsAllowed: bool = False
    childrenAllowed: bool = False
    empadronamientoAllowed: bool = False
    homeSizeM2: int | None = Field(default=None, ge=1, le=10_000)
    bathroomCount: int | None = Field(default=None, ge=0, le=20)
    rentalUnit: str | None = Field(default=None, max_length=16)
    bedType: str | None = Field(default=None, max_length=16)
    bedCount: int | None = Field(default=None, ge=1, le=10)
    currentRoomResidents: int | None = Field(default=None, ge=0, le=10)
    toilet: str | None = Field(default=None, max_length=64)
    householdGender: str | None = Field(default=None, max_length=16)
    householdHasChildren: bool | None = None
    heatingType: str | None = Field(default=None, max_length=16)
    accessible: bool | None = None
    floor: str | None = Field(default=None, max_length=16)
    couplesAllowed: bool | None = None
    acceptedTenantTypes: list[str] = Field(default_factory=list, max_length=4)
    restrictions: list[str] = Field(default_factory=list, max_length=100)
    amenities: list[str] = Field(default_factory=list, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    exactLatitude: float | None = Field(default=None, ge=-90, le=90)
    exactLongitude: float | None = Field(default=None, ge=-180, le=180)
    description: str = Field(default="", max_length=10_000)
    homeDescription: str = Field(default="", max_length=10_000)
    advertiserType: str = Field(default="Particular", max_length=32)
    expiresAt: datetime | None = None
    # Publication contact changes are committed in the same transaction as
    # the listing.  Omitted fields preserve the current profile for API
    # clients that do not edit contact details during publication.
    contactName: str | None = Field(default=None, min_length=2, max_length=120)
    contactPhone: str | None = Field(default=None, max_length=64)
    contactWhatsapp: str | None = Field(default=None, max_length=64)
    assetIds: list[UUID] = Field(default_factory=list, max_length=MAX_LISTING_PHOTOS)
    videoAssetId: UUID | None = None
    showPhone: bool | None = None
    showWhatsApp: bool | None = None

    @model_validator(mode="after")
    def validate_write(self):
        if self.rentalMode not in {"long", "holiday"}:
            raise ValueError("rentalMode must be long or holiday")
        if self.rentalMode == "long" and self.monthlyPrice is None:
            raise ValueError("monthlyPrice is required for long rentals")
        if self.rentalMode == "holiday" and self.nightlyPrice is None:
            raise ValueError("nightlyPrice is required for holiday rentals")
        if self.roomType not in ALLOWED_ROOM_TYPES:
            raise ValueError("roomType contains an unsupported value")
        if self.rentalUnit is not None and self.rentalUnit not in ALLOWED_RENTAL_UNITS:
            raise ValueError("rentalUnit contains an unsupported value")
        if self.bedType is not None and self.bedType not in ALLOWED_BED_TYPES:
            raise ValueError("bedType contains an unsupported value")
        if self.toilet is not None and self.toilet not in ALLOWED_TOILETS:
            raise ValueError("toilet contains an unsupported value")
        if self.householdGender is not None and self.householdGender not in ALLOWED_HOUSEHOLD_GENDERS:
            raise ValueError("householdGender contains an unsupported value")
        if self.heatingType is not None and self.heatingType not in ALLOWED_HEATING_TYPES:
            raise ValueError("heatingType contains an unsupported value")
        if self.floor is not None and self.floor not in ALLOWED_FLOORS:
            raise ValueError("floor contains an unsupported value")
        if len(set(self.acceptedTenantTypes)) != len(self.acceptedTenantTypes) or any(
            value not in ALLOWED_TENANT_TYPES for value in self.acceptedTenantTypes
        ):
            raise ValueError("acceptedTenantTypes contains duplicate or unsupported values")
        if len(set(self.assetIds)) != len(self.assetIds):
            raise ValueError("assetIds must be unique")
        if self.tenantRequirement not in ALLOWED_TENANT_REQUIREMENTS:
            raise ValueError("tenantRequirement contains an unsupported value")
        if self.advertiserType not in ALLOWED_ADVERTISER_TYPES:
            raise ValueError("advertiserType contains an unsupported value")
        if self.rentalUnit == "bed" and self.roomType != "Habitación compartida":
            raise ValueError("rentalUnit=bed is only valid for shared rooms")
        if self.rentalUnit == "bed" and self.bedType not in {None, "single", "bunk"}:
            raise ValueError("bed-space listings must use single or bunk beds")
        if self.currentRoomResidents is not None and self.currentRoomResidents >= self.roomCapacity:
            raise ValueError("currentRoomResidents must leave at least one available place")
        if self.bedCount is not None and self.bedType is not None:
            sleeping_places = self.bedCount * (2 if self.bedType in {"double", "bunk"} else 1)
            if sleeping_places < self.roomCapacity:
                raise ValueError("bedCount and bedType do not provide enough sleeping places")
        if self.homeSizeM2 is not None and self.homeSizeM2 < self.roomSizeM2:
            raise ValueError("homeSizeM2 cannot be smaller than roomSizeM2")
        if (self.exactLatitude is None) != (self.exactLongitude is None):
            raise ValueError("exactLatitude and exactLongitude must be provided together")
        if self.availableFrom and self.availableUntil and self.availableUntil < self.availableFrom:
            raise ValueError("availableUntil cannot be before availableFrom")
        if self.expiresAt:
            expiry = self.expiresAt if self.expiresAt.tzinfo else self.expiresAt.replace(tzinfo=UTC)
            if expiry <= datetime.now(UTC):
                raise ValueError("expiresAt must be in the future")
        if self.contactPhone and not PHONE_PATTERN.fullmatch(self.contactPhone):
            raise ValueError("contactPhone contains an invalid phone number")
        if self.contactWhatsapp and not PHONE_PATTERN.fullmatch(self.contactWhatsapp):
            raise ValueError("contactWhatsapp contains an invalid phone number")
        if self.showPhone is True and not self.contactPhone:
            raise ValueError("contactPhone is required when showPhone is enabled")
        if self.showWhatsApp is True and not self.contactWhatsapp:
            raise ValueError("contactWhatsapp is required when showWhatsApp is enabled")
        _validate_link_free_listing_fields(self)
        return self


class ListingPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=240)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    area: str | None = Field(default=None, min_length=1, max_length=120)
    street: str | None = Field(default=None, max_length=160)
    postcode: str | None = Field(default=None, max_length=32)
    approximateAddress: str | None = Field(default=None, min_length=2, max_length=240)
    rentalMode: str | None = None
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
    billsText: str | None = Field(default=None, max_length=240)
    bathroom: str | None = Field(default=None, max_length=64)
    kitchen: str | None = Field(default=None, max_length=64)
    furnished: bool | None = None
    roomSizeM2: int | None = Field(default=None, ge=1, le=10_000)
    bedroomCount: int | None = Field(default=None, ge=1, le=99)
    currentResidents: int | None = Field(default=None, ge=0)
    roomCapacity: int | None = Field(default=None, ge=1, le=10)
    shower: str | None = Field(default=None, max_length=64)
    tenantRequirement: str | None = Field(default=None, max_length=32)
    smokingAllowed: bool | None = None
    petsAllowed: bool | None = None
    childrenAllowed: bool | None = None
    empadronamientoAllowed: bool | None = None
    homeSizeM2: int | None = Field(default=None, ge=1, le=10_000)
    bathroomCount: int | None = Field(default=None, ge=0, le=20)
    rentalUnit: str | None = Field(default=None, max_length=16)
    bedType: str | None = Field(default=None, max_length=16)
    bedCount: int | None = Field(default=None, ge=1, le=10)
    currentRoomResidents: int | None = Field(default=None, ge=0, le=10)
    toilet: str | None = Field(default=None, max_length=64)
    householdGender: str | None = Field(default=None, max_length=16)
    householdHasChildren: bool | None = None
    heatingType: str | None = Field(default=None, max_length=16)
    accessible: bool | None = None
    floor: str | None = Field(default=None, max_length=16)
    couplesAllowed: bool | None = None
    acceptedTenantTypes: list[str] | None = Field(default=None, max_length=4)
    restrictions: list[str] | None = Field(default=None, max_length=100)
    amenities: list[str] | None = Field(default=None, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    exactLatitude: float | None = Field(default=None, ge=-90, le=90)
    exactLongitude: float | None = Field(default=None, ge=-180, le=180)
    description: str | None = Field(default=None, max_length=10_000)
    homeDescription: str | None = Field(default=None, max_length=10_000)
    advertiserType: str | None = Field(default=None, max_length=32)
    expiresAt: datetime | None = None
    status: str | None = None
    assetIds: list[UUID] | None = Field(default=None, max_length=MAX_LISTING_PHOTOS)
    videoAssetId: UUID | None = None
    # Owner UI sets this only when an existing private address actually changes.
    # The service then applies the same location to this owner's sibling room
    # listings that shared the previous private street + postcode.
    syncAddressGroup: bool = False

    @model_validator(mode="after")
    def validate_patch(self):
        nullable_fields = {
            "monthlyPrice",
            "nightlyPrice",
            "weeklyPrice",
            "availableFrom",
            "availableUntil",
            "billsText",
            "minimumNights",
            "bedroomCount",
            "homeSizeM2",
            "bathroomCount",
            "rentalUnit",
            "bedType",
            "bedCount",
            "currentRoomResidents",
            "toilet",
            "householdGender",
            "householdHasChildren",
            "heatingType",
            "accessible",
            "floor",
            "couplesAllowed",
            "acceptedTenantTypes",
            "exactLatitude",
            "exactLongitude",
            "expiresAt",
            "videoAssetId",
        }
        for field in self.model_fields_set:
            if field not in nullable_fields and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        if "rentalMode" in self.model_fields_set and self.rentalMode not in {"long", "holiday"}:
            raise ValueError("rentalMode must be long or holiday")
        if "roomType" in self.model_fields_set and self.roomType not in ALLOWED_ROOM_TYPES:
            raise ValueError("roomType contains an unsupported value")
        if "status" in self.model_fields_set and self.status not in ALLOWED_LISTING_STATUSES:
            raise ValueError("status contains an unsupported value")
        if self.rentalUnit is not None and self.rentalUnit not in ALLOWED_RENTAL_UNITS:
            raise ValueError("rentalUnit contains an unsupported value")
        if self.bedType is not None and self.bedType not in ALLOWED_BED_TYPES:
            raise ValueError("bedType contains an unsupported value")
        if self.toilet is not None and self.toilet not in ALLOWED_TOILETS:
            raise ValueError("toilet contains an unsupported value")
        if self.householdGender is not None and self.householdGender not in ALLOWED_HOUSEHOLD_GENDERS:
            raise ValueError("householdGender contains an unsupported value")
        if self.heatingType is not None and self.heatingType not in ALLOWED_HEATING_TYPES:
            raise ValueError("heatingType contains an unsupported value")
        if self.floor is not None and self.floor not in ALLOWED_FLOORS:
            raise ValueError("floor contains an unsupported value")
        if self.acceptedTenantTypes is not None and (
            len(set(self.acceptedTenantTypes)) != len(self.acceptedTenantTypes)
            or any(value not in ALLOWED_TENANT_TYPES for value in self.acceptedTenantTypes)
        ):
            raise ValueError("acceptedTenantTypes contains duplicate or unsupported values")
        if self.assetIds is not None and len(set(self.assetIds)) != len(self.assetIds):
            raise ValueError("assetIds must be unique")
        if self.expiresAt is not None:
            expiry = self.expiresAt if self.expiresAt.tzinfo else self.expiresAt.replace(tzinfo=UTC)
            if expiry <= datetime.now(UTC):
                raise ValueError("expiresAt must be in the future")
        if self.tenantRequirement is not None and self.tenantRequirement not in ALLOWED_TENANT_REQUIREMENTS:
            raise ValueError("tenantRequirement contains an unsupported value")
        if self.advertiserType is not None and self.advertiserType not in ALLOWED_ADVERTISER_TYPES:
            raise ValueError("advertiserType contains an unsupported value")
        coordinate_fields = {"latitude", "longitude"}
        if self.model_fields_set & coordinate_fields and (
            not coordinate_fields.issubset(self.model_fields_set) or self.latitude is None or self.longitude is None
        ):
            raise ValueError("latitude and longitude must be changed together")
        exact_fields = {"exactLatitude", "exactLongitude"}
        if self.model_fields_set & exact_fields:
            if not exact_fields.issubset(self.model_fields_set):
                raise ValueError("exactLatitude and exactLongitude must be changed together")
            if (self.exactLatitude is None) != (self.exactLongitude is None):
                raise ValueError("exactLatitude and exactLongitude must both be values or both be null")
        if self.syncAddressGroup:
            required_location_fields = {
                "city", "area", "street", "postcode", "approximateAddress",
                "latitude", "longitude", "exactLatitude", "exactLongitude",
            }
            if not required_location_fields.issubset(self.model_fields_set):
                raise ValueError("syncAddressGroup requires the complete owner location payload")
        _validate_link_free_listing_fields(self, self.model_fields_set)
        return self


class ListingResponse(BaseModel):
    id: str
    ownerUserId: str
    owner: "ListingOwnerResponse"
    contactPhone: str | None
    contactWhatsapp: str | None
    contactEmail: str | None
    showPhone: bool
    showWhatsApp: bool
    coverImageUrl: str | None
    imageUrls: list[str]
    videoUrl: str | None = None
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
    minimumStayMonths: int | None
    minimumNights: int | None
    depositAmount: int | None
    depositText: str | None = None
    billsIncluded: bool | None
    billsText: str | None = None
    bathroom: str | None
    kitchen: str | None
    furnished: bool | None
    roomSizeM2: int | None
    bedroomCount: int | None
    currentResidents: int
    roomCapacity: int | None
    shower: str
    tenantRequirement: str | None
    smokingAllowed: bool | None
    petsAllowed: bool | None
    childrenAllowed: bool | None
    empadronamientoAllowed: bool | None
    homeSizeM2: int | None = None
    bathroomCount: int | None = None
    rentalUnit: str | None = None
    bedType: str | None = None
    bedCount: int | None = None
    currentRoomResidents: int | None = None
    availableSpots: int | None = None
    toilet: str | None = None
    householdGender: str | None = None
    householdHasChildren: bool | None = None
    heatingType: str | None = None
    accessible: bool | None = None
    floor: str | None = None
    couplesAllowed: bool | None = None
    acceptedTenantTypes: list[str] = Field(default_factory=list)
    restrictions: list[str]
    amenities: list[str]
    status: str
    latitude: float | None
    longitude: float | None
    description: str
    homeDescription: str
    advertiserName: str | None = None
    advertiserType: str | None
    source: str | None
    isExternal: bool = False
    primarySource: str | None = None
    sourceUrl: str | None = None
    sourcePriceText: str | None = None
    priceCurrency: str | None = None
    pricePeriod: str | None = None
    priceIsFrom: bool | None = None
    publishedAt: datetime | None
    expiresAt: datetime | None
    views: int
    closedReason: str | None
    createdAt: datetime
    updatedAt: datetime | None
    promoted: bool = False


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


RoomCountFilter = int | Literal["10+"]


class ListingSearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str | None = Field(default=None, max_length=240)
    city: str | None = Field(default=None, max_length=120)
    area: str | None = Field(default=None, max_length=120)
    rentalMode: str | None = None
    minPrice: int | None = Field(default=None, ge=0)
    maxPrice: int | None = Field(default=None, ge=0)
    roomType: str | None = Field(default=None, max_length=64)
    roomTypes: list[str] = Field(default_factory=list, max_length=3)
    bedroomCounts: list[RoomCountFilter] = Field(default_factory=list, max_length=11)
    availableFrom: date | None = None
    maxMinimumStayMonths: int | None = Field(default=None, ge=0)
    restrictions: list[str] = Field(default_factory=list, max_length=100)
    tenantRequirement: str | None = Field(default=None, max_length=32)
    bathroom: str | None = Field(default=None, max_length=64)
    kitchen: str | None = Field(default=None, max_length=64)
    furnished: bool | None = None
    billsIncluded: bool | None = None
    deposit: str | None = None
    minRoomSizeM2: int | None = Field(default=None, ge=0)
    maxRoomSizeM2: int | None = Field(default=None, ge=0)
    shower: str | None = Field(default=None, max_length=64)
    currentResidents: int | None = Field(default=None, ge=0)
    minCurrentResidents: int | None = Field(default=None, ge=0)
    roomCapacity: int | None = Field(default=None, ge=1, le=10)
    maxMinimumNights: int | None = Field(default=None, ge=0)
    availableUntil: date | None = None
    smokingAllowed: bool | None = None
    petsAllowed: bool | None = None
    childrenAllowed: bool | None = None
    empadronamientoAllowed: bool | None = None
    minHomeSizeM2: int | None = Field(default=None, ge=0)
    maxHomeSizeM2: int | None = Field(default=None, ge=0)
    minBathroomCount: int | None = Field(default=None, ge=0, le=20)
    rentalUnit: str | None = Field(default=None, max_length=16)
    bedType: str | None = Field(default=None, max_length=16)
    minBedCount: int | None = Field(default=None, ge=1, le=10)
    currentRoomResidents: int | None = Field(default=None, ge=0, le=10)
    maxCurrentRoomResidents: int | None = Field(default=None, ge=0, le=10)
    minAvailableSpots: int | None = Field(default=None, ge=1, le=10)
    toilet: str | None = Field(default=None, max_length=64)
    householdGender: str | None = Field(default=None, max_length=16)
    householdHasChildren: bool | None = None
    heatingType: str | None = Field(default=None, max_length=16)
    accessible: bool | None = None
    floor: str | None = Field(default=None, max_length=16)
    couplesAllowed: bool | None = None
    acceptedTenantTypes: list[str] = Field(default_factory=list, max_length=4)
    publishedWithinDays: int | None = Field(default=None, ge=1, le=365)
    advertiserType: str | None = Field(default=None, max_length=32)
    amenities: list[str] = Field(default_factory=list, max_length=100)
    minLatitude: float | None = Field(default=None, ge=-90, le=90)
    maxLatitude: float | None = Field(default=None, ge=-90, le=90)
    minLongitude: float | None = Field(default=None, ge=-180, le=180)
    maxLongitude: float | None = Field(default=None, ge=-180, le=180)
    center: SearchPoint | None = None
    radiusKm: float | None = Field(default=None, gt=0, le=100)
    polygon: list[SearchPoint] = Field(default_factory=list, max_length=100)
    sort: str = "newest"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10_000)

    @model_validator(mode="after")
    def validate_filters(self):
        bounds = (self.minLatitude, self.maxLatitude, self.minLongitude, self.maxLongitude)
        if any(value is not None for value in bounds) and any(value is None for value in bounds):
            raise ValueError("all bounding-box coordinates are required")
        if self.minLatitude is not None and (
            self.minLatitude >= self.maxLatitude or self.minLongitude >= self.maxLongitude
        ):
            raise ValueError("bounding-box minimums must be below maximums")
        if (self.center is None) != (self.radiusKm is None):
            raise ValueError("center and radiusKm must be provided together")
        if self.rentalMode not in {None, "long", "holiday"}:
            raise ValueError("rentalMode must be long or holiday")
        if self.sort not in {"newest", "oldest", "price_asc", "price_desc"}:
            raise ValueError("sort must be newest, oldest, price_asc, or price_desc")
        if self.minPrice is not None and self.maxPrice is not None and self.minPrice > self.maxPrice:
            raise ValueError("minPrice cannot exceed maxPrice")
        if (
            self.minRoomSizeM2 is not None
            and self.maxRoomSizeM2 is not None
            and self.minRoomSizeM2 > self.maxRoomSizeM2
        ):
            raise ValueError("minRoomSizeM2 cannot exceed maxRoomSizeM2")
        if (
            self.minHomeSizeM2 is not None
            and self.maxHomeSizeM2 is not None
            and self.minHomeSizeM2 > self.maxHomeSizeM2
        ):
            raise ValueError("minHomeSizeM2 cannot exceed maxHomeSizeM2")
        if self.availableFrom and self.availableUntil and self.availableUntil < self.availableFrom:
            raise ValueError("availableUntil cannot be before availableFrom")
        if self.deposit not in {None, "Sin fianza", "Hasta 1 mes", "Más de 1 mes"}:
            raise ValueError("deposit contains an unsupported value")
        if self.rentalUnit not in {None, *ALLOWED_RENTAL_UNITS}:
            raise ValueError("rentalUnit contains an unsupported value")
        if self.bedType not in {None, *ALLOWED_BED_TYPES}:
            raise ValueError("bedType contains an unsupported value")
        if self.toilet not in {None, *ALLOWED_TOILETS}:
            raise ValueError("toilet contains an unsupported value")
        if self.householdGender not in {None, *ALLOWED_HOUSEHOLD_GENDERS}:
            raise ValueError("householdGender contains an unsupported value")
        if self.heatingType not in {None, *ALLOWED_HEATING_TYPES}:
            raise ValueError("heatingType contains an unsupported value")
        if self.floor not in {None, *ALLOWED_FLOORS}:
            raise ValueError("floor contains an unsupported value")
        if len(set(self.acceptedTenantTypes)) != len(self.acceptedTenantTypes) or any(
            value not in ALLOWED_TENANT_TYPES for value in self.acceptedTenantTypes
        ):
            raise ValueError("acceptedTenantTypes contains duplicate or unsupported values")
        if self.currentRoomResidents is not None and self.maxCurrentRoomResidents is not None:
            raise ValueError("use currentRoomResidents or maxCurrentRoomResidents, not both")
        if self.roomType and self.roomTypes:
            raise ValueError("use roomType or roomTypes, not both")
        if self.roomType and self.roomType not in ALLOWED_ROOM_TYPES:
            raise ValueError("roomType contains an unsupported value")
        if len(set(self.roomTypes)) != len(self.roomTypes) or any(
            value not in ALLOWED_ROOM_TYPES for value in self.roomTypes
        ):
            raise ValueError("roomTypes contains duplicate or unsupported values")
        invalid_counts = [value for value in self.bedroomCounts if value != "10+" and not 1 <= int(value) <= 10]
        if invalid_counts or len(set(map(str, self.bedroomCounts))) != len(self.bedroomCounts):
            raise ValueError("bedroomCounts must contain unique values from 1 to 10 or 10+")
        if self.polygon:
            unique = {(point.latitude, point.longitude) for point in self.polygon}
            if len(unique) < 3:
                raise ValueError("polygon needs at least three unique points")
            if self.polygon[0] != self.polygon[-1]:
                self.polygon.append(self.polygon[0])
        return self


class ListingSearchResponse(BaseModel):
    items: list[ListingResponse]
    total: int
    limit: int
    offset: int


class ListingImagesRequest(BaseModel):
    assetIds: list[UUID] = Field(default_factory=list, max_length=MAX_LISTING_PHOTOS)

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
