from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PolygonPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class SavedSearchWrite(BaseModel):
    name: str = Field(default="", max_length=120)
    query: str = Field(default="", max_length=240)
    rentalMode: str
    filters: dict = Field(default_factory=dict)
    polygon: list[PolygonPoint] = Field(default_factory=list, max_length=100)
    alertsEnabled: bool = True

    @field_validator("rentalMode")
    @classmethod
    def valid_mode(cls, value: str) -> str:
        if value not in {"long", "holiday"}:
            raise ValueError("rentalMode must be long or holiday")
        return value


class SavedSearchPatch(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    query: str | None = Field(default=None, max_length=240)
    filters: dict | None = None
    polygon: list[PolygonPoint] | None = Field(default=None, max_length=100)
    alertsEnabled: bool | None = None


class SavedSearchResponse(BaseModel):
    id: UUID
    name: str
    query: str
    rentalMode: str
    filters: dict
    polygon: list[PolygonPoint]
    alertsEnabled: bool
    createdAt: datetime
    updatedAt: datetime | None
