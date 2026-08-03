import json
import math
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ..core.config import get_settings

MAX_FILTER_DEPTH = 8
MAX_FILTER_CONTAINER_ITEMS = 100
MAX_FILTER_STRING_LENGTH = 1_000
MAX_FILTER_KEY_LENGTH = 128


def validate_filter_payload(value: dict | None) -> dict | None:
    if value is None:
        return None
    settings = get_settings()
    nodes = 0

    def visit(node: object, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > settings.max_saved_search_filter_nodes:
            raise ValueError("filters contain too many values")
        if depth > MAX_FILTER_DEPTH:
            raise ValueError("filters are nested too deeply")

        if isinstance(node, dict):
            if len(node) > MAX_FILTER_CONTAINER_ITEMS:
                raise ValueError("filters contain too many keys")
            for key, item in node.items():
                if not isinstance(key, str) or len(key) > MAX_FILTER_KEY_LENGTH:
                    raise ValueError("filter keys must be short strings")
                visit(item, depth + 1)
        elif isinstance(node, list):
            if len(node) > MAX_FILTER_CONTAINER_ITEMS:
                raise ValueError("filter lists are too long")
            for item in node:
                visit(item, depth + 1)
        elif isinstance(node, str):
            if len(node) > MAX_FILTER_STRING_LENGTH:
                raise ValueError("filter strings are too long")
        elif isinstance(node, float):
            if not math.isfinite(node):
                raise ValueError("filter numbers must be finite")
        elif node is None or isinstance(node, (bool, int)):
            return
        else:
            raise ValueError("filters contain an unsupported value")

    visit(value, 0)
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > settings.max_saved_search_filter_bytes:
        raise ValueError("filters exceed the storage limit")
    return value


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

    @field_validator("filters")
    @classmethod
    def valid_filters(cls, value: dict) -> dict:
        return validate_filter_payload(value) or {}


class SavedSearchPatch(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    query: str | None = Field(default=None, max_length=240)
    filters: dict | None = None
    polygon: list[PolygonPoint] | None = Field(default=None, max_length=100)
    alertsEnabled: bool | None = None

    @field_validator("filters")
    @classmethod
    def valid_filters(cls, value: dict | None) -> dict | None:
        return validate_filter_payload(value)


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


class GuestStateImport(BaseModel):
    # Older frontend builds stored slug-like listing ids. The service validates
    # and imports only UUIDs that exist in the current database.
    favoriteIds: list[str] = Field(default_factory=list, max_length=500)
    savedSearches: list[SavedSearchWrite] = Field(default_factory=list, max_length=100)
