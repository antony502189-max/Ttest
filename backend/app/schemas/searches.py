import json
import math
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ..core.config import get_settings

MAX_FILTER_DEPTH = 8
MAX_FILTER_CONTAINER_ITEMS = 100
MAX_FILTER_STRING_LENGTH = 1_000
MAX_FILTER_KEY_LENGTH = 128


def has_ai_metadata(value: object) -> bool:
    """Legacy filters must never smuggle a typed matcher the legacy SQL ignores."""
    reserved = {"ai", "aiintent", "aisearch", "aisearchintent", "intent", "searchintent", "intenthash", "schemaversion",
                "taxonomyversion", "matcher", "matcherkind", "matcherversion", "sessionid", "resultref", "criteria",
                "strength", "expectedversion", "expectedsessionversion"}
    stack = [value]
    nodes = 0
    while stack:
        node = stack.pop()
        nodes += 1
        if nodes > 10_000:  # Corrupt persisted containers fail closed too.
            return True
        if isinstance(node, dict):
            for key, item in node.items():
                if not isinstance(key, str):
                    return True
                normalized = key.replace("_", "").replace("-", "").lower()
                if normalized in reserved or key.lower().startswith("ai_"):
                    return True
                stack.append(item)
        elif isinstance(node, list):
            stack.extend(node)
    return False


def validate_filter_payload(value: dict | None) -> dict | None:
    if value is None:
        return None
    if has_ai_metadata(value):
        raise ValueError("AI metadata is not a manual search filter")
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


class ManualSearchBody(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def reject_ai_metadata(cls, value):
        # Preserve historical handling of unrelated legacy extension fields,
        # but never silently ignore a caller's matcher/typed-intent metadata.
        if has_ai_metadata(value):
            raise ValueError("AI metadata is not a manual saved search")
        return value


class SavedSearchWrite(ManualSearchBody):
    provinceCode: str | None = Field(default=None, pattern=r"^(0[1-9]|[1-4][0-9]|5[0-2])$")
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


class SavedSearchPatch(ManualSearchBody):
    provinceCode: str | None = Field(default=None, pattern=r"^(0[1-9]|[1-4][0-9]|5[0-2])$")
    name: str | None = Field(default=None, max_length=120)
    query: str | None = Field(default=None, max_length=240)
    filters: dict | None = None
    polygon: list[PolygonPoint] | None = Field(default=None, max_length=100)
    alertsEnabled: bool | None = None

    @field_validator("filters")
    @classmethod
    def valid_filters(cls, value: dict | None) -> dict | None:
        return validate_filter_payload(value)

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for field in self.model_fields_set:
            if field != "provinceCode" and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class SavedSearchResponse(BaseModel):
    provinceCode: str | None = None
    id: UUID
    name: str
    query: str
    rentalMode: str
    filters: dict
    polygon: list[PolygonPoint]
    alertsEnabled: bool
    createdAt: datetime
    updatedAt: datetime | None


class GuestStateImport(ManualSearchBody):
    # Older frontend builds stored slug-like listing ids. The service validates
    # and imports only UUIDs that exist in the current database.
    favoriteIds: list[str] = Field(default_factory=list, max_length=500)
    savedSearches: list[SavedSearchWrite] = Field(default_factory=list, max_length=100)
