"""Snapshot verification and set-based fail-closed SQL currentness guard.

No public activation, default freshness TTL, provider, crawl or backfill. This
proof establishes equality with explicitly verified stored source state, not
source-health freshness by elapsed time or complete listing eligibility.
"""
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Text, and_, case, delete, func, literal, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import JSONB, aggregate_order_by, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import ColumnElement

from ..models import ExternalListingSource, Listing
from ..models.ai_fact_pipeline import AiFactCatalog, AiFactSource
from ..models.ai_listing_facts import AiListingFact, AiListingFactBatch, AiListingSearchFeatures
from ..models.ai_query_proof import (
    AiLiveInputEpoch,
    AiLiveInputVersion,
    AiLiveMatchCohort,
    AiLiveProofDependency,
    AiProofPopulation,
    AiQueryProof,
)
from ..models.room_details import ListingRoomDetails
from ..schemas.ai_listing_facts import Category, DateRange, Money, Quantity, SearchProjection
from .ai_fact_pipeline import FactPipeline
from .ai_hard_matching import hard_match_predicate

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


def input_binding(signature, inputs, resolver, vocabulary, revision):
    # Bind the new shortcut to every original persisted proof field. Changing
    # a stored signature/scope cannot silently reuse an earlier input token.
    return _hash(func.jsonb_build_object("contract", "live-proof-binding.v1", "proof_contract", PROOF_CONTRACT_VERSION,
        "signature", signature, "inputs", inputs, "resolver", resolver, "vocabulary", vocabulary, "revision", revision))


def live_vector_signature(vector):
    return _hash(vector)


def _input_context():
    epoch = select(AiLiveInputEpoch.epoch).where(AiLiveInputEpoch.id == 1).scalar_subquery()
    # Uncorrelated scalar subquery is a statement-wide InitPlan: schema/trigger
    # readiness is not recomputed for every candidate.
    schema = select(func.ai_live_input_schema_signature()).scalar_subquery()
    return and_(AiQueryProof.input_schema == schema, AiQueryProof.input_epoch == epoch)


def current_projection_predicate(listing_id, *, resolver_version: str, vocabulary_hash: str,
                                 match_plan=None, cohort_scope=None) -> ColumnElement[bool]:
    """Use with existing eligibility and hard matching BEFORE count/order/seek/limit."""
    # The legacy digest stays inside COALESCE/CASE, not an equality hash key.
    # PostgreSQL may choose a set join for broad views and indexed probes for
    # narrow candidates, without hashing every listing's raw v2 inputs.
    # The ALWAYS proof-write guard verifies vector/binding integrity once per
    # write. Query readiness includes that guard's definition and enabled state.
    binding_valid = and_(_input_context(), AiQueryProof.input_contract == PROOF_CONTRACT_VERSION)
    # TRUE is the unchanged-input shortcut. FALSE is fail-closed missing or
    # corrupted state. NULL requests the exact original v2 check: legacy proofs
    # or changed tokens with all dependencies present. This preserves live
    # keyset restoration semantics without treating a stale token as permission.
    fast_match: ColumnElement[bool] = literal(True)
    legacy_match: ColumnElement[bool] = literal(True)
    if match_plan is not None:
        matching = select(AiLiveMatchCohort.id).where(hard_match_predicate(AiLiveMatchCohort.__table__.c.features, match_plan))
        if cohort_scope is not None:
            cohorts = matching.where(AiLiveMatchCohort.id.in_(cohort_scope)).cte().prefix_with("MATERIALIZED")
            fast_match = AiQueryProof.match_cohort_id.in_(select(cohorts.c.id))
        else:
            # One-listing/saved matching must not scan every catalog cohort.
            fast_match = matching.where(AiLiveMatchCohort.id == AiQueryProof.match_cohort_id
                ).offset(0).correlate(AiQueryProof).exists()
        features = AiListingSearchFeatures.__table__.alias()
        legacy_match = select(1).select_from(features).where(features.c.canonical_listing_id == AiQueryProof.canonical_listing_id,
            hard_match_predicate(features.c.features, match_plan)).correlate_except(features).exists()
    decision = case((AiQueryProof.input_status != "legacy",
        case((binding_valid, case((AiQueryProof.input_status == "current", fast_match),
                                 (AiQueryProof.input_status == "changed", None), else_=False)),
             else_=False)), else_=None)
    return select(1).select_from(AiQueryProof).where(
        AiQueryProof.canonical_listing_id == listing_id,
        AiQueryProof.resolver_version == resolver_version,
        AiQueryProof.vocabulary_hash == vocabulary_hash,
        func.coalesce(decision, and_(AiQueryProof.signature == projection_signature(AiQueryProof.canonical_listing_id), legacy_match)),
    ).correlate_except(AiQueryProof).exists()


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
            snapshot = select(func.ai_live_input_vector(literal(listing_id)).cast(JSONB).label("vector")).offset(0).subquery()
            vector, inputs = (await session.execute(select(snapshot.c.vector, live_vector_signature(snapshot.c.vector)))).one()
            if inputs is None:
                return False
            matching = select(func.ai_live_match_features(literal(listing_id)).cast(JSONB).label("features")).offset(0).subquery()
            match_features, cohort = (await session.execute(select(matching.c.features, _hash(matching.c.features)))).one()
        try:
            return await self._write_prepared(listing_id, signature, inputs, vector, projection.feature_revision, match_features, cohort)
        except IntegrityError as error:
            cause = getattr(error.orig, "__cause__", None)
            constraint = getattr(error.orig, "constraint_name", None) or getattr(cause, "constraint_name", None)
            if constraint in {"fk_ai_live_dep_version", "ck_ai_live_current_proof"}:
                return False  # context changed; the whole write has rolled back
            raise

    async def _write_prepared(self, listing_id, signature, inputs, vector, revision, match_features, cohort):
        deps = [("listing", listing_id, UUID(vector["listing"]))]
        deps += [(kind, UUID(record), UUID(token)) for field, kind in (("authority", "external"), ("batches", "batch"))
                 for record, token in vector[field]]
        async with self.pipeline.sessions() as session, session.begin():
            # Match PostgreSQL's FK lock ordering before locking the proof row.
            # Key-share locks serialize token-key updates with preparation even
            # when a source writer has an older repeatable-read snapshot.
            version = AiLiveInputVersion
            locked = (await session.execute(select(version.kind, version.record_id, version.token).where(
                tuple_(version.kind, version.record_id).in_([(kind, record) for kind, record, _ in deps])
                ).order_by(version.kind, version.record_id).with_for_update(read=True, key_share=True))).all()
            if {(kind, record): token for kind, record, token in locked} != {(kind, record): token for kind, record, token in deps}:
                return False
            await session.execute(insert(AiLiveMatchCohort).values(id=cohort, features=match_features).on_conflict_do_nothing())
            values = select(literal(listing_id), literal(signature), literal(self.pipeline.vocabulary_hash),
                            literal(self.pipeline.resolver_version), literal(revision), literal(inputs),
                            input_binding(literal(signature), literal(inputs), literal(self.pipeline.resolver_version),
                                literal(self.pipeline.vocabulary_hash), literal(revision)),
                            literal(vector, type_=JSONB), literal("missing"), literal(PROOF_CONTRACT_VERSION),
                            literal(UUID(vector["epoch"])), literal(vector["schema"]), literal(cohort)).where(
                projection_signature(literal(listing_id)) == signature,
                func.ai_live_input_signature(literal(listing_id)) == inputs)
            statement = insert(AiQueryProof).from_select(
                ["canonical_listing_id", "signature", "vocabulary_hash", "resolver_version", "feature_revision",
                 "input_signature", "input_binding", "input_vector", "input_status", "input_contract", "input_epoch", "input_schema", "match_cohort_id"], values)
            returning = statement.on_conflict_do_update(index_elements=[AiQueryProof.canonical_listing_id], set_={
                "signature": statement.excluded.signature, "vocabulary_hash": statement.excluded.vocabulary_hash,
                "resolver_version": statement.excluded.resolver_version, "feature_revision": statement.excluded.feature_revision,
                "input_signature": statement.excluded.input_signature, "input_binding": statement.excluded.input_binding,
                "input_vector": statement.excluded.input_vector,
                "input_status": statement.excluded.input_status,
                "input_contract": statement.excluded.input_contract,
                "input_epoch": statement.excluded.input_epoch, "input_schema": statement.excluded.input_schema,
                "match_cohort_id": statement.excluded.match_cohort_id,
            }).returning(AiQueryProof.canonical_listing_id)
            if await session.scalar(returning) is None:
                return False
            await session.execute(delete(AiLiveProofDependency).where(AiLiveProofDependency.proof_listing_id == listing_id))
            await session.execute(insert(AiLiveProofDependency).values([
                {"proof_listing_id": listing_id, "kind": kind, "record_id": record, "token": token}
                for kind, record, token in deps]))
            status = await session.scalar(update(AiQueryProof).where(AiQueryProof.canonical_listing_id == listing_id)
                .values(input_status="current").returning(AiQueryProof.input_status))
            if status != "current":
                raise RuntimeError("prepared proof binding rejected")
            return True
