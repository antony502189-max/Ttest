"""Partial internal hard-value requirements, not a public intent contract."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .ai_listing_facts import Contract


class BooleanRequirement(Contract):
    key: Literal["furnished", "bills_included", "balcony", "terrace"]
    value: bool


class HardValueRequirements(Contract):
    capacity_at_least: Annotated[int, Field(ge=1, le=2_147_483_647)] | None = None
    booleans: Annotated[tuple[BooleanRequirement, ...], Field(max_length=4)] = ()

    @model_validator(mode="after")
    def nonempty_unique(self) -> Self:
        if self.capacity_at_least is None and not self.booleans:
            raise ValueError("at least one supported hard value is required")
        if len({item.key for item in self.booleans}) != len(self.booleans):
            raise ValueError("duplicate boolean requirement")
        return self
