"""Explicit bounded source capture. No minimizer, parser, provider or live hook."""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from ..models import ExternalListingSource, Listing
from ..schemas.ai_fact_bridge import BridgeReference, BridgeRejected


def source_snapshot_hash() -> ColumnElement[str]:
    """Same coarse CAS token as AI-04, computed from one stored PG row version."""
    return func.encode(func.sha256(func.convert_to(func.jsonb_build_object(
        "raw", ExternalListingSource.raw_payload, "normalized", ExternalListingSource.normalized_payload,
        "price", ExternalListingSource.source_price_text, "source_name", ExternalListingSource.source_name,
        "external_id", ExternalListingSource.external_id, "source_url", ExternalListingSource.source_url,
    ).cast(Text), "UTF8")), "hex")


@dataclass(frozen=True)
class CapturedParserSnapshot:
    reference: BridgeReference
    raw_json: str = field(repr=False)
    normalized_json: str = field(repr=False)
    source_price_text: str | None = field(repr=False)


class FactSnapshotReader:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], *, max_payload_bytes: int):
        if type(max_payload_bytes) is not int or not 1 <= max_payload_bytes <= 2_097_152:
            raise ValueError("explicit bounded snapshot byte policy required")
        self.sessions, self.max_payload_bytes = sessions, max_payload_bytes

    async def capture(self, source_record_id: UUID) -> CapturedParserSnapshot:
        raw = ExternalListingSource.raw_payload.cast(Text)
        normalized = ExternalListingSource.normalized_payload.cast(Text)
        size = func.octet_length(raw) + func.octet_length(normalized) + func.coalesce(
            func.octet_length(ExternalListingSource.source_price_text), 0)
        # The source row is locked only during capture. No builder/provider
        # runs here; the caller receives immutable JSON strings after commit.
        async with self.sessions() as session, session.begin():
            row = (await session.execute(select(
                ExternalListingSource.id, ExternalListingSource.canonical_listing_id, ExternalListingSource.source_name,
                raw.label("raw_json"), normalized.label("normalized_json"), ExternalListingSource.source_price_text,
                source_snapshot_hash().label("snapshot_hash"),
            ).join(Listing, Listing.id == ExternalListingSource.canonical_listing_id).where(
                ExternalListingSource.id == source_record_id, ExternalListingSource.current_status == "active",
                Listing.status == "published", Listing.deleted_at.is_(None), size <= self.max_payload_bytes,
            ).with_for_update(of=ExternalListingSource))).first()
            if row is None:
                raise BridgeRejected("SOURCE_SNAPSHOT_UNAVAILABLE")
            try:
                reference = BridgeReference(source_record_id=row.id, canonical_listing_id=row.canonical_listing_id,
                    source_identifier=f"{row.source_name}:{row.id.hex}", snapshot_hash=row.snapshot_hash)
            except ValueError:
                raise BridgeRejected("SOURCE_IDENTITY_UNSUPPORTED") from None
            return CapturedParserSnapshot(reference, row.raw_json, row.normalized_json, row.source_price_text)
