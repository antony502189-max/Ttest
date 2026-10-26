"""AI-01 v1 intent/patch vocabulary. No SQL, fuzzy geography or inferred permissions."""

import json
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..spain_municipalities import MUNICIPALITIES
from ..spain_provinces import PROVINCE_CODES
from .ai_search_quota import StrictContract

Version = Annotated[int, Field(ge=0, le=2_147_483_647)]
PositiveQuantity = Annotated[int, Field(ge=1, le=2_147_483_647)]
Code = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")]
Amount = Annotated[str, Field(max_length=16, pattern=r"^(0|[1-9][0-9]*)(\.[0-9]{1,2})?$")]


class Criterion[Value](StrictContract):
    strength: Literal["hard", "soft"]
    value: Value


class Money(StrictContract):
    amount: Amount
    currency: Literal["EUR"]
    period: Literal["monthly", "nightly", "weekly"]


class DepositMoney(StrictContract):
    kind: Literal["money"]
    amount: Amount
    currency: Literal["EUR"]
    period: Literal["one_off"]


class DepositMonths(StrictContract):
    kind: Literal["quantity"]
    value: Annotated[int, Field(ge=0, le=2_147_483_647)]
    unit: Literal["months"]


class Geography(StrictContract):
    province_code: Annotated[str, Field(pattern=r"^[0-9]{2}$")]
    municipality_code: Annotated[str, Field(pattern=r"^[0-9]{5}$")] | None = None
    zone_id: Code | None = None

    @model_validator(mode="after")
    def local_identity(self):
        if self.province_code not in PROVINCE_CODES:
            raise ValueError("unknown INE province")
        if self.municipality_code is not None and (
            self.municipality_code not in MUNICIPALITIES or self.municipality_code[:2] != self.province_code
        ):
            raise ValueError("municipality does not belong to province")
        if self.zone_id is not None and self.municipality_code is None:
            raise ValueError("zone requires a municipality")
        return self


class Accommodation(StrictContract):
    kind: Literal["room", "shared_room", "studio", "one_bedroom", "catalog_other"]
    catalog_code: Code | None = None

    @model_validator(mode="after")
    def catalog_identity(self):
        if (self.kind == "catalog_other") != (self.catalog_code is not None):
            raise ValueError("only catalog_other requires catalog_code")
        return self


class Party(StrictContract):
    adults: Annotated[int, Field(ge=1, le=10)]
    children: Annotated[int, Field(ge=0, le=10)]
    relationship: Literal["couple", "friends", "family", "unspecified"]

    @model_validator(mode="after")
    def total(self):
        if self.adults + self.children > 10:
            raise ValueError("party total exceeds supported v1 boundary")
        return self


class Pet(StrictContract):
    species: Literal["dog", "cat", "other"]
    size: Literal["small", "medium", "large", "unspecified"]
    count: Annotated[int, Field(ge=1, le=10)]


class Smoking(StrictContract):
    scope: Literal["indoors", "outdoors", "balcony", "terrace"]


class Dates(StrictContract):
    check_in: Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]
    check_out: Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]

    @field_validator("check_in", "check_out")
    @classmethod
    def valid_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def order(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must follow check_in")
        return self


class Stay(StrictContract):
    value: PositiveQuantity
    unit: Literal["nights", "months"]


CriterionName = Literal[
    "rental_mode",
    "budget",
    "geography",
    "accommodation",
    "party",
    "pets",
    "smoking",
    "furnished",
    "bills_included",
    "deposit",
    "balcony",
    "terrace",
    "amenities",
    "dates",
    "stay",
]


class Criteria(StrictContract):
    rental_mode: Criterion[Literal["long", "holiday"]] | None = None
    budget: Criterion[Money] | None = None
    geography: Criterion[Geography] | None = None
    accommodation: Criterion[Accommodation] | None = None
    party: Criterion[Party] | None = None
    pets: Criterion[Annotated[tuple[Pet, ...], Field(max_length=10)]] | None = None
    smoking: Criterion[Smoking] | None = None
    furnished: Criterion[bool] | None = None
    bills_included: Criterion[bool] | None = None
    deposit: Criterion[Annotated[DepositMoney | DepositMonths, Field(discriminator="kind")]] | None = None
    balcony: Criterion[bool] | None = None
    terrace: Criterion[bool] | None = None
    amenities: Criterion[Annotated[tuple[Code, ...], Field(max_length=100)]] | None = None
    dates: Criterion[Dates] | None = None
    stay: Criterion[Stay] | None = None

    @model_validator(mode="after")
    def explicit_and_consistent(self):
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("null does not remove a criterion; use remove")
        if self.amenities and len(set(self.amenities.value)) != len(self.amenities.value):
            raise ValueError("duplicate amenities")
        if self.pets:
            pets = self.pets.value
            if len({(pet.species, pet.size) for pet in pets}) != len(pets) or sum(p.count for p in pets) > 10:
                raise ValueError("duplicate pet scopes or unsupported pet count")
        if (
            self.dates
            and self.stay
            and self.dates.strength == self.stay.strength == "hard"
            and self.stay.value.unit == "nights"
        ):
            nights = (
                date.fromisoformat(self.dates.value.check_out) - date.fromisoformat(self.dates.value.check_in)
            ).days
            if nights != self.stay.value.value:
                raise ValueError("dates contradict requested nights")
            # Months are never implicitly converted to 30 nights.
        return self


class SearchIntent(StrictContract):
    schema_version: Literal["ai-search.v1"]
    taxonomy_version: Literal["rental.v1"]
    session_id: UUID
    version: Version
    criteria: Criteria


class IntentPatch(StrictContract):
    schema_version: Literal["ai-search.v1"]
    session_id: UUID
    expected_version: Version
    set: Criteria = Field(default_factory=Criteria)
    remove: Annotated[tuple[CriterionName, ...], Field(max_length=20)] = ()

    @model_validator(mode="after")
    def allowed_changes(self):
        names = self.set.model_fields_set
        if len(set(self.remove)) != len(self.remove) or names.intersection(self.remove):
            raise ValueError("duplicate remove or criterion in both set and remove")
        if len(names) + len(self.remove) > 20:
            raise ValueError("too many changed criteria")
        return self


def apply_patch(current: SearchIntent, patch: IntentPatch) -> SearchIntent:
    if patch.session_id != current.session_id or patch.expected_version != current.version:
        raise ValueError("SESSION_VERSION_CONFLICT")
    criteria = current.criteria.model_dump(mode="json", exclude_none=True)
    criteria.update(patch.set.model_dump(mode="json", exclude_none=True))
    for name in patch.remove:
        criteria.pop(name, None)
    # Full criterion replacement, then validate the merged cross-field state.
    # JSON validation intentionally parses UUIDs/tuples from persisted JSON while
    # keeping booleans/numbers strict. model_copy(update=...) skips validation.
    return SearchIntent.model_validate_json(
        json.dumps(
            {
                "schema_version": current.schema_version,
                "taxonomy_version": current.taxonomy_version,
                "session_id": str(current.session_id),
                "version": current.version + 1,
                "criteria": criteria,
            }
        )
    )
