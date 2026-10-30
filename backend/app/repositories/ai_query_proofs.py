"""Snapshot verification and set-based fail-closed SQL currentness guard.

No public activation, default freshness TTL, provider, crawl or backfill. This
proof establishes equality with explicitly verified stored source state, not
source-health freshness by elapsed time or complete listing eligibility.
"""
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Text, func, literal, select, text
from sqlalchemy.dialects.postgresql import JSONB, aggregate_order_by, insert
from sqlalchemy.sql.elements import ColumnElement

from ..models import ExternalListingSource, Listing
from ..models.ai_fact_pipeline import AiFactCatalog, AiFactSource
from ..models.ai_listing_facts import AiListingFact, AiListingFactBatch, AiListingSearchFeatures
from ..models.ai_query_proof import AiProofPopulation, AiQueryProof
from ..models.room_details import ListingRoomDetails
from ..schemas.ai_listing_facts import Category, DateRange, Money, Quantity, SearchProjection
from .ai_fact_pipeline import FactPipeline

PROOF_CONTRACT_VERSION = "query-proof.v2"


def _hash(value):
    return func.encode(func.sha256(func.convert_to(value.cast(Text), "UTF8")), "hex")


def _object(columns):
    pairs = []
    for column in columns:
        # Epoch preserves timestamptz equality across connection time zones.
        value = func.extract("epoch", column) if isinstance(column.type, DateTime) else column
        pairs.extend((literal(str(column.name), type_=Text), value))
    return func.jsonb_build_object(*pairs)


def _canonical_listing_rows(listing, listing_id):
    # Keep the whole-row conversion below a query boundary: otherwise every
    # timestamp lookup expands to another to_jsonb(whole_listing) call. LIMIT
    # and OFFSET prevent flattening while preserving the exact v2 JSON value,
    # including support for deliberately minimal legacy fixture schemas.
    snapshot = select(func.to_jsonb(listing.table_valued()).label("value"), listing.c.id.label("ordering")).where(
        listing.c.id == listing_id).order_by(listing.c.id).limit(1).offset(0).correlate_except(listing).subquery()
    canonical = snapshot.c.value.op("-")(literal("views")).op("-")(literal("updated_at"))
    timestamps: list[ColumnElement] = []
    for column in listing.c:
        if isinstance(column.type, DateTime) and column.name != "updated_at":
            timestamps.extend((literal(column.name, type_=Text), func.extract(
                "epoch", snapshot.c.value.op("->>")(literal(column.name, type_=Text)).cast(DateTime(timezone=True)))))
    canonical = canonical.op("||")(func.jsonb_build_object(*timestamps))
    return select(func.coalesce(func.jsonb_agg(aggregate_order_by(canonical, snapshot.c.ordering)),
                                literal([], type_=JSONB))).select_from(snapshot).scalar_subquery()


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
    room = ListingRoomDetails.__table__.alias()
    projection = AiListingSearchFeatures.__table__.alias()
    anchor = AiFactCatalog.__table__.alias()
    known_ids = select(source.c.source_record_id).where(source.c.canonical_listing_id == listing_id).correlate_except(source)
    batch_ids = select(source.c.batch_id).where(source.c.canonical_listing_id == listing_id).correlate_except(source)
    current = ExternalListingSource.__table__.alias()
    current_ids = select(current.c.id).where(current.c.canonical_listing_id == listing_id).correlate_except(current)
    # Select the identical current-or-former identity set through indexed
    # lookups first. An OR against a correlated IN subquery made PostgreSQL
    # scan the entire external-source PK for each sparse listing, even with
    # the 129-row result bound below. UNION deduplicates identities without
    # dropping newly linked or formerly known/remapped sources.
    authority_ids = current_ids.union(known_ids)

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
        # Bump whenever preparation's semantic checks change. Old cache rows
        # must not bypass a new verifier merely because their inputs are equal.
        "proof_contract", PROOF_CONTRACT_VERSION,
        # Hash the canonical row too: public cards can change independently of
        # the provider snapshot. Views/updated_at are bookkeeping, not evidence.
        # to_jsonb(row) also supports deliberately minimal legacy test schemas.
        "listing", _canonical_listing_rows(listing, listing_id),
        "room", rows(room, room.c.listing_id == listing_id, room.c.listing_id, 1),
        "anchor", rows(anchor, anchor.c.canonical_listing_id == listing_id, anchor.c.canonical_listing_id, 1),
        "projection", rows(projection, projection.c.canonical_listing_id == listing_id, projection.c.canonical_listing_id, 1),
        "sources", rows(source, source.c.canonical_listing_id == listing_id, source.c.source_record_id, 129),
        "authority", rows(external, external.c.id.in_(authority_ids),
                          external.c.id, 129, authority),
        "batches", rows(batch, batch.c.id.in_(batch_ids), batch.c.id, 129),
        "facts", rows(fact, fact.c.batch_id.in_(batch_ids), fact.c.id, 1025)))


def proof_population_signature(*, resolver_version: str, vocabulary_hash: str):
    """O(1) transactional prepared-set generation, never live eligibility.

    Database statement triggers cover every ordinary proof writer, including
    direct SQL and TRUNCATE. Identical preparation leaves the version unchanged.
    Restoring a former set or changing another resolver conservatively expires
    cursors. Source/canonical/room/fact changes still fail the full live digest
    before count/order/LIMIT, without requiring a version bump or reconciler.
    Missing state returns NULL and the caller fails closed. A recreated counter
    gets a fresh random epoch so it cannot revive an earlier cursor.
    """
    state = AiProofPopulation
    return select(func.concat("proof-population.v1:", resolver_version, ":", vocabulary_hash, ":",
                              state.epoch, ":", state.revision)).where(state.id == 1).scalar_subquery()


def current_projection_predicate(listing_id, *, resolver_version: str, vocabulary_hash: str) -> ColumnElement[bool]:
    """Use with existing eligibility and hard matching BEFORE count/order/seek/limit."""
    # Preserve the correlated PK lookup. Flattening this EXISTS into a hash
    # semi-join scans the complete proof catalog for a small viewport and can
    # evaluate the expensive signature again when rechecking the hash match.
    # OFFSET 0 changes neither membership nor the before-LIMIT guard contract.
    return select(1).select_from(AiQueryProof).where(
        AiQueryProof.canonical_listing_id == listing_id,
        AiQueryProof.resolver_version == resolver_version,
        AiQueryProof.vocabulary_hash == vocabulary_hash,
        AiQueryProof.signature == projection_signature(listing_id),
    ).offset(0).correlate_except(AiQueryProof).exists()


async def _canonical_values_agree(session, listing_id: UUID, projection: SearchProjection) -> bool:
    """Preparation cannot recertify stale prices/dates against a changed card.

    The provider remains evidence authority. The public canonical price and
    inventory must agree before certifying it; defaults never create AI facts.
    The SQL signature subsequently guards both rows at each query snapshot.
    """
    listing = Listing.__table__.alias()
    room = ListingRoomDetails.__table__.alias()
    card = await session.scalar(select(func.to_jsonb(listing.table_valued())).where(listing.c.id == listing_id))
    details = await session.scalar(select(func.to_jsonb(room.table_valued())).where(room.c.listing_id == listing_id)) or {}
    if card is None:
        return False
    for feature in projection.features:
        if feature.status != "explicit_allow":
            continue
        value = feature.typed_value
        if feature.key == "price" and isinstance(value, Money):
            field = {"monthly": "monthly_price", "nightly": "nightly_price", "weekly": "weekly_price"}.get(value.period)
            if field is None or card.get(field) is None or Decimal(str(card[field])) != Decimal(value.amount):
                return False
            if card.get("source_price_is_from") is True:
                return False
        elif feature.key == "rental_mode" and isinstance(value, Category):
            if card.get("rental_mode") != value.value:
                return False
        elif feature.key == "availability" and isinstance(value, DateRange):
            if (card.get("available_from"), card.get("available_until")) != (value.start, value.end):
                return False
        elif feature.key == "available_spots" and isinstance(value, Quantity):
            # Use exactly the public rented-unit inventory contract. A missing
            # occupancy is unknown, never zero; household current_residents
            # cannot substitute for current_room_residents.
            capacity = details.get("room_capacity_v2")
            if capacity is None:
                capacity = card.get("room_capacity")
            residents = details.get("current_room_residents")
            if (type(capacity) is not int or capacity <= 0 or type(residents) is not int or residents < 0
                    or value.value != max(0, capacity - residents)):
                return False
        elif feature.key in {"capacity_total", "current_room_residents"} and isinstance(value, Quantity):
            field = "room_capacity_v2" if feature.key == "capacity_total" else "current_room_residents"
            current = details.get(field)
            if current is None and feature.key == "capacity_total":
                current = card.get("room_capacity")
            if current != value.value:
                return False
    return True


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
            if projection is None or not await _canonical_values_agree(session, listing_id, projection):
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
