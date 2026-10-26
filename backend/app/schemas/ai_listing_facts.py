"""Offline AI-03 storage contracts; these types grant no provider/privacy authority."""

import hashlib
import json
from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..spain_municipalities import MUNICIPALITIES
from ..spain_provinces import PROVINCE_CODES

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Version = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")]
Code = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")]
FactKey = Literal[
    "pets", "smoking", "couples", "children", "tenant_groups", "capacity_total",
    "current_room_residents", "available_spots", "price", "deposit", "furnished",
    "bills_included", "balcony", "terrace", "amenity", "rental_mode", "accommodation",
    "geography", "availability", "minimum_stay", "maximum_stay",
]
FactStatus = Literal["explicit_allow", "explicit_deny", "conditional", "unknown", "conflict", "legacy_unverified"]
Origin = Literal["owner_explicit", "source_structured", "source_text", "model_extracted", "legacy_default"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class Policy(Contract):
    kind: Literal["policy"]
    allowed: bool


class BooleanValue(Contract):
    kind: Literal["boolean"]
    value: bool


class Quantity(Contract):
    kind: Literal["quantity"]
    value: Annotated[int, Field(ge=0, le=2_147_483_647)]
    unit: Literal["persons", "months", "nights"]


class Money(Contract):
    kind: Literal["money"]
    amount: Annotated[str, Field(max_length=16, pattern=r"^(0|[1-9][0-9]*)(\.[0-9]{1,2})?$")]
    currency: Literal["EUR"]
    period: Literal["monthly", "nightly", "weekly", "one_off"]


class Category(Contract):
    kind: Literal["category"]
    value: Literal["long", "holiday", "room", "shared_room", "studio", "one_bedroom", "catalog_other"]
    catalog_code: Code | None = None

    @model_validator(mode="after")
    def catalog_identity(self) -> Self:
        if (self.value == "catalog_other") != (self.catalog_code is not None):
            raise ValueError("only catalog_other requires catalog_code")
        return self


class Geography(Contract):
    kind: Literal["geography"]
    province_code: Annotated[str, Field(pattern=r"^[0-9]{2}$")]
    municipality_code: Annotated[str, Field(pattern=r"^[0-9]{5}$")] | None = None
    zone_id: Code | None = None

    @model_validator(mode="after")
    def local_identity(self) -> Self:
        if self.province_code not in PROVINCE_CODES:
            raise ValueError("unknown INE province")
        if self.municipality_code is not None and (
            self.municipality_code not in MUNICIPALITIES or self.municipality_code[:2] != self.province_code
        ):
            raise ValueError("municipality does not belong to province")
        if self.zone_id is not None and self.municipality_code is None:
            raise ValueError("zone requires municipality")
        return self


class DateRange(Contract):
    kind: Literal["date_range"]
    start: Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]
    end: Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]

    @model_validator(mode="after")
    def ordered_dates(self) -> Self:
        if date.fromisoformat(self.end) <= date.fromisoformat(self.start):
            raise ValueError("end must follow start")
        return self


TypedValue = Annotated[Policy | BooleanValue | Quantity | Money | Category | Geography | DateRange,
                       Field(discriminator="kind")]


class Qualifiers(Contract):
    species: Literal["dog", "cat", "other"] | None = None
    size: Literal["small", "medium", "large", "unspecified"] | None = None
    max_count: Annotated[int, Field(ge=1, le=10)] | None = None
    approval_required: bool | None = None
    smoking_scope: Literal["indoors", "outdoors", "balcony", "terrace"] | None = None
    inventory_scope: Literal["rented_unit"] | None = None
    amenity_code: Code | None = None
    tenant_group: Code | None = None


class FactValue(Contract):
    key: FactKey
    status: FactStatus
    typed_value: TypedValue | None
    qualifiers: Qualifiers

    @property
    def scope_hash(self) -> str:
        return digest(self.qualifiers.model_dump(mode="json", exclude_none=True))

    @model_validator(mode="after")
    def value_and_scope(self) -> Self:
        value = self.typed_value
        unresolved = self.status in {"unknown", "conflict", "legacy_unverified"}
        if unresolved != (value is None) and self.status != "conditional":
            raise ValueError("unresolved facts have no value; explicit facts require a value")
        scopes = set(self.qualifiers.model_dump(exclude_none=True))
        allowed_scopes: set[str] = set()
        if self.key == "pets":
            allowed_scopes = {"species", "size", "max_count", "approval_required"}
        elif self.key == "smoking":
            allowed_scopes = {"smoking_scope", "approval_required"}
        elif self.key in {"couples", "children"}:
            allowed_scopes = {"approval_required"}
        elif self.key == "tenant_groups":
            allowed_scopes = {"tenant_group", "approval_required"}
        elif self.key in {"capacity_total", "current_room_residents", "available_spots", "availability"}:
            allowed_scopes = {"inventory_scope"}
        elif self.key == "amenity":
            allowed_scopes = {"amenity_code"}
        if scopes - allowed_scopes:
            raise ValueError("qualifier does not belong to fact key")
        required = ({"inventory_scope"} if "inventory_scope" in allowed_scopes else
                    {"smoking_scope"} if self.key == "smoking" else
                    {"amenity_code"} if self.key == "amenity" else
                    {"tenant_group"} if self.key == "tenant_groups" else set())
        if not required <= scopes:
            raise ValueError("scoped key requires explicit scope even when unresolved")
        if self.qualifiers.approval_required is True and self.status in {"explicit_allow", "explicit_deny"}:
            raise ValueError("approval condition cannot become unconditional")
        if value is None:
            return self
        if self.key in {"pets", "smoking", "couples", "children", "tenant_groups"}:
            if not isinstance(value, Policy):
                raise ValueError("policy key requires policy value")
            if self.status in {"explicit_allow", "explicit_deny"} and (
                value.allowed != (self.status == "explicit_allow")
            ):
                raise ValueError("permission status contradicts value")
        else:
            if self.status == "explicit_deny":
                raise ValueError("value facts use explicit_allow for confirmed values")
            if self.key in {"capacity_total", "current_room_residents", "available_spots"}:
                if not isinstance(value, Quantity) or value.unit != "persons":
                    raise ValueError("capacity requires persons")
                if self.key != "current_room_residents" and value.value == 0:
                    raise ValueError("total/available capacity must be positive")
            elif self.key in {"minimum_stay", "maximum_stay"}:
                if not isinstance(value, Quantity) or value.unit not in {"months", "nights"} or value.value == 0:
                    raise ValueError("stay requires positive months/nights")
            elif self.key == "deposit":
                if not ((isinstance(value, Quantity) and value.unit == "months") or
                        (isinstance(value, Money) and value.period == "one_off")):
                    raise ValueError("deposit requires months or one-off EUR")
            elif self.key == "price":
                if not isinstance(value, Money) or value.period == "one_off":
                    raise ValueError("rent requires explicit rental period")
            elif self.key in {"furnished", "bills_included", "balcony", "terrace", "amenity"}:
                if not isinstance(value, BooleanValue):
                    raise ValueError("boolean key requires boolean value")
            elif self.key in {"rental_mode", "accommodation"}:
                modes = {"long", "holiday"}
                if not isinstance(value, Category) or ((value.value in modes) != (self.key == "rental_mode")):
                    raise ValueError("category does not belong to key")
            elif self.key == "geography" and not isinstance(value, Geography):
                raise ValueError("geography requires geography value")
            elif self.key == "availability" and not isinstance(value, DateRange):
                raise ValueError("availability requires date range")
        return self


class EvidenceSpan(Contract):
    field: Literal["title", "description", "structured", "owner_form"]
    provider_field: Annotated[str, Field(min_length=1, max_length=120,
                                        pattern=r"^[a-zA-Z][a-zA-Z0-9_.\[\]-]*$")] | None = None
    quote: Annotated[str, Field(min_length=1, max_length=512)]
    start: Annotated[int, Field(ge=0, le=65_536)]
    end: Annotated[int, Field(ge=1, le=65_536)]

    @model_validator(mode="after")
    def span_length(self) -> Self:
        if self.end - self.start != len(self.quote):
            raise ValueError("span offsets must delimit exact quote")
        if (self.field == "structured") != (self.provider_field is not None):
            raise ValueError("structured evidence requires a named provider field only")
        return self


class FactObservation(FactValue):
    fact_id: UUID
    origin: Origin
    evidence: Annotated[list[EvidenceSpan], Field(max_length=16)]

    @model_validator(mode="after")
    def evidence_semantics(self) -> Self:
        if self.status in {"unknown", "legacy_unverified"}:
            if self.evidence:
                raise ValueError("unknown/legacy cannot fabricate evidence")
        elif not self.evidence:
            raise ValueError("known/conditional/conflict observations require evidence")
        if (self.origin == "legacy_default") != (self.status == "legacy_unverified"):
            raise ValueError("legacy defaults are unverified only")
        fields = {span.field for span in self.evidence}
        permitted = ({"owner_form"} if self.origin == "owner_explicit" else
                     {"structured"} if self.origin == "source_structured" else
                     {"title", "description"} if self.origin == "source_text" else
                     {"title", "description", "structured"})
        if fields - permitted:
            raise ValueError("evidence field does not belong to origin")
        return self


class FactVocabulary(Contract):
    """Required server-owned allowlists at the future writer boundary; no production defaults."""

    amenity_codes: frozenset[Code]
    catalog_other_codes: frozenset[Code]
    tenant_group_codes: frozenset[Code]
    municipality_zones: frozenset[tuple[str, Code]]

    def validate_fact(self, fact: FactValue) -> None:
        if fact.qualifiers.amenity_code is not None and fact.qualifiers.amenity_code not in self.amenity_codes:
            raise ValueError("unsupported amenity")
        if fact.qualifiers.tenant_group is not None and fact.qualifiers.tenant_group not in self.tenant_group_codes:
            raise ValueError("unsupported tenant group")
        value = fact.typed_value
        if isinstance(value, Category) and value.value == "catalog_other" and value.catalog_code not in self.catalog_other_codes:
            raise ValueError("unsupported catalog type")
        if isinstance(value, Geography) and value.zone_id is not None and (
            value.municipality_code, value.zone_id
        ) not in self.municipality_zones:
            raise ValueError("unsupported municipality zone")


class FactBatch(Contract):
    schema_version: Literal["ai-facts.v1"]
    taxonomy_version: Literal["ai-search.v1"]
    batch_id: UUID
    canonical_listing_id: UUID
    source_record_id: UUID | None
    source_generation: Annotated[int, Field(ge=1, le=2_147_483_647)]
    content_hash: Digest
    extractor_version: Version
    observed_at: datetime
    source_status: Literal["active", "unknown", "unavailable", "retired"]
    last_successful_check_at: datetime | None
    last_content_change_at: datetime | None
    last_check_error_at: datetime | None
    facts: Annotated[list[FactObservation], Field(min_length=1, max_length=128)]

    @model_validator(mode="after")
    def provenance(self) -> Self:
        instants = [self.observed_at, self.last_successful_check_at,
                    self.last_content_change_at, self.last_check_error_at]
        if any(v is not None and (v.tzinfo is None or v.utcoffset() is None) for v in instants):
            raise ValueError("timestamps must be timezone aware")
        if any(v is not None and v > self.observed_at for v in instants[1:]):
            raise ValueError("source timestamps cannot follow observation")
        ids = [f.fact_id for f in self.facts]
        identities = [(f.key, f.scope_hash, f.origin) for f in self.facts]
        if len(ids) != len(set(ids)) or len(identities) != len(set(identities)):
            raise ValueError("duplicate observation identity")
        if self.source_record_id is None and any(f.origin != "owner_explicit" for f in self.facts):
            raise ValueError("only explicit owner observations may omit source record")
        if self.source_record_id is not None and any(f.origin == "owner_explicit" for f in self.facts):
            raise ValueError("source observations cannot impersonate owner")
        return self

    def validate_evidence_against(self, sanitized_fields: dict[str, str]) -> None:
        """Check offsets in already-sanitized input. This function is not a sanitizer."""
        if digest(sanitized_fields) != self.content_hash:
            raise ValueError("sanitized input hash mismatch")
        for fact in self.facts:
            for span in fact.evidence:
                field = f"structured.{span.provider_field}" if span.field == "structured" else span.field
                text = sanitized_fields.get(field)
                if text is None or text[span.start:span.end] != span.quote:
                    raise ValueError("evidence does not match sanitized input")


class SearchFeature(FactValue):
    supporting_fact_ids: Annotated[list[UUID], Field(max_length=128)]

    @model_validator(mode="after")
    def support(self) -> Self:
        if len(set(self.supporting_fact_ids)) != len(self.supporting_fact_ids):
            raise ValueError("duplicate supporting facts")
        if self.status != "unknown" and not self.supporting_fact_ids:
            raise ValueError("resolved/uncertain features need provenance")
        return self


class SearchProjection(Contract):
    schema_version: Literal["ai-facts.v1"]
    taxonomy_version: Literal["ai-search.v1"]
    canonical_listing_id: UUID
    feature_revision: Annotated[int, Field(ge=1, le=2_147_483_647)]
    resolver_version: Version
    input_hash: Digest
    computed_at: datetime
    features: Annotated[list[SearchFeature], Field(max_length=128)]

    @model_validator(mode="after")
    def unique_features(self) -> Self:
        if self.computed_at.tzinfo is None or self.computed_at.utcoffset() is None:
            raise ValueError("computed_at must be timezone aware")
        identities = [(f.key, f.scope_hash) for f in self.features]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate feature key/scope")
        if len(json.dumps(self.model_dump(mode="json")["features"], ensure_ascii=False).encode()) > 524_288:
            raise ValueError("projection exceeds storage byte budget")
        return self

    def validate_support(self, batches: list[FactBatch]) -> None:
        """Check provenance, never choose authority or assert that generations are current."""
        facts = {}
        states = {}
        for batch in batches:
            if batch.canonical_listing_id != self.canonical_listing_id:
                raise ValueError("cross-listing supporting batch")
            for fact in batch.facts:
                if fact.fact_id in facts:
                    raise ValueError("ambiguous supporting fact ID")
                facts[fact.fact_id] = fact
                states[fact.fact_id] = batch.source_status
        for feature in self.features:
            for fact_id in feature.supporting_fact_ids:
                supporting = facts.get(fact_id)
                if supporting is None or (supporting.key, supporting.scope_hash) != (feature.key, feature.scope_hash):
                    raise ValueError("missing or differently scoped supporting observation")
                if feature.status in {"explicit_allow", "explicit_deny"} and (
                    supporting.status != feature.status or supporting.typed_value != feature.typed_value
                    or states[fact_id] != "active"
                ):
                    raise ValueError("explicit feature cannot upgrade uncertain, contradictory or inactive evidence")
