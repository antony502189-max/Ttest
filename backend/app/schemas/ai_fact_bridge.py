"""Bounded compatibility subset of #373's sanitized listing-evidence-v1 JSON.

No parser/cleaner is imported or copied. These types do not attest privacy or
authorize outbound data. A reviewed server builder must supply the packet.
"""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from .ai_listing_facts import Code, Contract, Digest

PolicyField = Literal["pets_allowed", "children_allowed", "smoking_allowed", "room_capacity", "couples_allowed",
                      "students_only", "smoking_indoors_allowed", "smoking_outdoors_allowed"]
ProviderField = Literal["pets_allowed", "children_allowed", "smoking_allowed", "room_capacity", "couples_allowed",
                        "furnished", "bills_included", "empadronamiento_allowed", "amenities"]
POLICY_FIELDS = frozenset({"pets_allowed", "children_allowed", "smoking_allowed", "room_capacity", "couples_allowed",
                           "students_only", "smoking_indoors_allowed", "smoking_outdoors_allowed"})
ProviderPath = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z][A-Za-z0-9_.\[\]-]*$")]
OpaqueSource = Annotated[str, Field(max_length=120,
    pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}(?::[A-Za-z0-9_-]{1,55})?$")]


class BridgeRejected(ValueError):
    """Stable redacted reason, never a payload/quote or provider error message."""


class ParserSpan(Contract):
    source: Literal["title", "description", "structured"]
    quote: Annotated[str, Field(min_length=1, max_length=512)] = Field(repr=False)
    provider_field: ProviderPath | None = None

    @model_validator(mode="after")
    def source_path(self) -> Self:
        if (self.source == "structured") != (self.provider_field is not None):
            raise ValueError("structured evidence requires a named provider field only")
        return self


class ParserPolicy(Contract):
    status: Literal["unknown", "explicit", "conditional", "conflict"]
    value: bool | Annotated[int, Field(ge=1, le=99)] | None
    evidence: Annotated[list[ParserSpan], Field(max_length=16)] = Field(repr=False)

    @model_validator(mode="after")
    def uncertainty(self) -> Self:
        if self.status == "unknown" and (self.value is not None or self.evidence):
            raise ValueError("unknown carries neither value nor evidence")
        if self.status != "unknown" and not self.evidence:
            raise ValueError("known policy requires evidence")
        if (self.status == "explicit") != (self.value is not None):
            raise ValueError("only explicit has a value")
        if any(s.source == "structured" for s in self.evidence):
            raise ValueError("parser policy requires textual evidence; structured facts are separate")
        return self


class ParserProviderFact(Contract):
    field: ProviderField
    value: bool | Annotated[int, Field(ge=1, le=99)] | Annotated[list[str], Field(min_length=1, max_length=7)]
    evidence: ParserSpan = Field(repr=False)

    @model_validator(mode="after")
    def typed_field(self) -> Self:
        if self.evidence.source != "structured":
            raise ValueError("provider fact requires structured evidence")
        if self.field == "room_capacity":
            if type(self.value) is not int:
                raise ValueError("capacity requires integer")
        elif self.field == "amenities":
            allowed = {"wifi", "internet", "balcony", "terrace", "parking", "lift", "air_conditioning"}
            if not isinstance(self.value, list) or len(set(self.value)) != len(self.value) or not set(self.value) <= allowed:
                raise ValueError("unsupported/duplicate structured amenity")
        elif type(self.value) is not bool:
            raise ValueError("policy/boolean field requires boolean")
        return self


class ParserEvidencePacket(Contract):
    schema_version: Literal["listing-evidence-v1"]
    source_identifier: OpaqueSource
    canonical_listing_identifier: UUID
    title: Annotated[str, Field(max_length=500)] = Field(repr=False)
    description: Annotated[str, Field(max_length=30_000)] = Field(repr=False)
    property_category: Literal["room", "studio", "one_bedroom", "unknown"]
    rental_category: Literal["long", "holiday"]
    source_language: Literal["es", "en", "ru", "mixed"] | None
    provider_facts: Annotated[list[ParserProviderFact], Field(max_length=128)] = Field(repr=False)
    policy_evidence: dict[PolicyField, ParserPolicy] = Field(repr=False)
    data_status: Literal["ready", "insufficient_source_data"]
    content_hash: Digest

    @model_validator(mode="after")
    def policy_types(self) -> Self:
        if set(self.policy_evidence) != POLICY_FIELDS:
            raise ValueError("exact parser policy vocabulary required")
        for key, fact in self.policy_evidence.items():
            if fact.value is not None and (
                (type(fact.value) is int) != (key == "room_capacity")
            ):
                raise ValueError("policy field/value type mismatch")
        return self


class BridgeReference(Contract):
    source_record_id: UUID
    canonical_listing_id: UUID
    source_identifier: OpaqueSource
    snapshot_hash: Digest


class BridgeMapping(Contract):
    # All choices are required, with no production mapping/default authority.
    structured_fields: Annotated[dict[ProviderPath, ProviderField], Field(max_length=128)]
    rented_unit_capacity_fields: Annotated[frozenset[ProviderPath], Field(max_length=128)]
    text_capacity_scope: Literal["rented_unit"] | None
    structured_smoking_scopes: Annotated[dict[ProviderPath, Literal["indoors", "outdoors", "balcony", "terrace"]],
                                        Field(max_length=128)]
    text_smoking_scopes: dict[Literal["smoking_allowed", "smoking_outdoors_allowed"],
                             Literal["indoors", "outdoors", "balcony", "terrace"]]
    amenity_codes: dict[Literal["wifi", "internet", "balcony", "terrace", "parking", "lift", "air_conditioning"], Code]

    @model_validator(mode="after")
    def capacity_paths(self) -> Self:
        if any(self.structured_fields.get(path) != "room_capacity" for path in self.rented_unit_capacity_fields):
            raise ValueError("capacity scope may only attest a mapped capacity field")
        if any(self.structured_fields.get(path) != "smoking_allowed" for path in self.structured_smoking_scopes):
            raise ValueError("smoking scope may only attest a mapped smoking field")
        return self
