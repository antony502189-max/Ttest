"""Snapshot verification and set-based fail-closed SQL currentness guard.

No public activation, default freshness TTL, provider, crawl or backfill. This
proof establishes equality with explicitly verified stored source state, not
source-health freshness by elapsed time or complete listing eligibility.
"""
from uuid import UUID

from sqlalchemy import DateTime, Text, func, literal, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB, aggregate_order_by, insert
from sqlalchemy.sql.elements import ColumnElement

from ..models import ExternalListingSource, Listing
from ..models.ai_fact_pipeline import AiFactCatalog, AiFactSource
from ..models.ai_listing_facts import AiListingFact, AiListingFactBatch, AiListingSearchFeatures
from ..models.ai_query_proof import AiQueryProof
from .ai_fact_pipeline import FactPipeline


def _hash(value):
    return func.encode(func.sha256(func.convert_to(value.cast(Text), "UTF8")), "hex")


def _object(columns):
    pairs = []
    for column in columns:
        # Epoch preserves timestamptz equality across connection time zones.
        value = func.extract("epoch", column) if isinstance(column.type, DateTime) else column
        pairs.extend((literal(str(column.name), type_=Text), value))
    return func.jsonb_build_object(*pairs)


def projection_signature(listing_id) -> ColumnElement[str]:
    """Bounded correlated SQL digest of everything the verifier relies on.

    Includes complete current AI batches/facts/projection and all current or
    formerly known external identities/payload digests. New sources, remaps,
    deletions, corruption and generation changes invalidate equality. No raw
    payload/evidence is returned to application or persisted in this cache.
    """
    source = AiFactSource.__table__.alias()
    batch = AiListingFactBatch.__table__.alias()
    fact = AiListingFact.__table__.alias()
    external = ExternalListingSource.__table__.alias()
    listing = Listing.__table__.alias()
    projection = AiListingSearchFeatures.__table__.alias()
    anchor = AiFactCatalog.__table__.alias()
    known_ids = select(source.c.source_record_id).where(source.c.canonical_listing_id == listing_id).correlate_except(source)
    batch_ids = select(source.c.batch_id).where(source.c.canonical_listing_id == listing_id).correlate_except(source)

    def rows(table, condition, key, limit, value=None):
        bounded = select((value if value is not None else _object(table.c)).label("row"), key.label("ordering")).where(
            condition).order_by(key).limit(limit).correlate_except(table).subquery()
        return select(func.coalesce(func.jsonb_agg(aggregate_order_by(bounded.c.row, bounded.c.ordering)),
                                    literal([], type_=JSONB))).select_from(bounded).scalar_subquery()

    snapshot = _hash(func.jsonb_build_object("raw", external.c.raw_payload, "normalized", external.c.normalized_payload,
        "price", external.c.source_price_text, "source_name", external.c.source_name, "external_id", external.c.external_id,
        "source_url", external.c.source_url))
    authority = func.jsonb_build_object("id", external.c.id, "canonical", external.c.canonical_listing_id,
        "fingerprint", external.c.fingerprint, "status", external.c.current_status, "snapshot", snapshot,
        "last_success", func.extract("epoch", external.c.last_success_at),
        "content_updated", func.extract("epoch", external.c.content_updated_at))
    return _hash(func.jsonb_build_object(
        "listing", rows(listing, listing.c.id == listing_id, listing.c.id, 1,
                        _object([listing.c.id, listing.c.status, listing.c.deleted_at])),
        "anchor", rows(anchor, anchor.c.canonical_listing_id == listing_id, anchor.c.canonical_listing_id, 1),
        "projection", rows(projection, projection.c.canonical_listing_id == listing_id, projection.c.canonical_listing_id, 1),
        "sources", rows(source, source.c.canonical_listing_id == listing_id, source.c.source_record_id, 129),
        "authority", rows(external, or_(external.c.canonical_listing_id == listing_id, external.c.id.in_(known_ids)),
                          external.c.id, 129, authority),
        "batches", rows(batch, batch.c.id.in_(batch_ids), batch.c.id, 129),
        "facts", rows(fact, fact.c.batch_id.in_(batch_ids), fact.c.id, 1025)))


def current_projection_predicate(listing_id, *, resolver_version: str, vocabulary_hash: str) -> ColumnElement[bool]:
    """Use with existing eligibility and hard matching BEFORE count/order/seek/limit."""
    return select(1).select_from(AiQueryProof).where(
        AiQueryProof.canonical_listing_id == listing_id,
        AiQueryProof.resolver_version == resolver_version,
        AiQueryProof.vocabulary_hash == vocabulary_hash,
        AiQueryProof.signature == projection_signature(listing_id),
    ).correlate_except(AiQueryProof).exists()


class QueryProofs:
    def __init__(self, pipeline: FactPipeline):
        self.pipeline = pipeline

    async def prepare(self, listing_id: UUID) -> bool:
        """Explicit one-listing preparation; never invoked on a per-card query.

        Verify in one read-only RR snapshot, then CAS the digest in a separate
        short write. Any subsequent mutation invalidates the SQL guard without
        waiting for a repair/reconciler. Concurrent change before CAS returns
        False; errors propagate and never broaden a query.
        """
        async with self.pipeline.sessions() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            projection = await self.pipeline._read_current_projection(session, listing_id)
            if projection is None:
                return False
            signature = await session.scalar(select(projection_signature(literal(listing_id))))
        async with self.pipeline.sessions() as session, session.begin():
            values = select(literal(listing_id), literal(signature), literal(self.pipeline.vocabulary_hash),
                            literal(self.pipeline.resolver_version), literal(projection.feature_revision)).where(
                projection_signature(literal(listing_id)) == signature)
            statement = insert(AiQueryProof).from_select(
                ["canonical_listing_id", "signature", "vocabulary_hash", "resolver_version", "feature_revision"], values)
            returning = statement.on_conflict_do_update(index_elements=[AiQueryProof.canonical_listing_id], set_={
                "signature": statement.excluded.signature, "vocabulary_hash": statement.excluded.vocabulary_hash,
                "resolver_version": statement.excluded.resolver_version, "feature_revision": statement.excluded.feature_revision,
            }).returning(AiQueryProof.canonical_listing_id)
            return await session.scalar(returning) is not None
