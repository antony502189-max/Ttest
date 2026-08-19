from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class ListingRoomDetails(Base):
    """Room-specific structured facts that are optional for legacy/imported listings.

    The core ``listings`` table keeps compatibility with existing imports. Direct
    room listings can opt into this one-to-one record so room-only search does
    not have to overload apartment-oriented fields or free-text amenities.
    """

    __tablename__ = "listing_room_details"

    listing_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    home_size_m2: Mapped[int | None] = mapped_column(Integer)
    bathroom_count: Mapped[int | None] = mapped_column(Integer)
    rental_unit: Mapped[str | None] = mapped_column(String(16))
    bed_type: Mapped[str | None] = mapped_column(String(16))
    bed_count: Mapped[int | None] = mapped_column(Integer)
    current_room_residents: Mapped[int | None] = mapped_column(Integer)
    toilet: Mapped[str | None] = mapped_column(String(64))
    household_gender: Mapped[str | None] = mapped_column(String(16))
    household_has_children: Mapped[bool | None] = mapped_column(Boolean)
    heating_type: Mapped[str | None] = mapped_column(String(16))
    accessible: Mapped[bool | None] = mapped_column(Boolean)
    floor: Mapped[str | None] = mapped_column(String(16))
    couples_allowed: Mapped[bool | None] = mapped_column(Boolean)
    accepted_tenant_types: Mapped[list[str]] = mapped_column(JSONB, default=list)
