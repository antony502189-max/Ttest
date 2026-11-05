"""Explicit owned-session query using existing public eligibility/cards/TOP.

No public endpoint/activation/provider and no debit: new-message orchestration
must use quota finalize; page reads reuse an already-owned normalized session.

Pagination is live keyset, not a frozen result set. Each page rechecks current
source/public eligibility and TOP ordering in its own repeatable-read snapshot.
Signed context detects intent/filter/config/catalog/fact/prepared-proof changes,
with conservative invalidation when another resolver's proofs change or a
previous proof set is restored. Identical preparation preserves the cursor.
Direct source, user/moderation changes and clock-driven TOP changes can
alter totals/order without rejecting a cursor. Restart without a cursor to
discover rows newly eligible or moved before the seek point. No stale card is
kept merely to preserve an earlier page's total or order.
"""
from dataclasses import dataclass
from math import isfinite
from uuid import UUID

from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import and_, cast, select, text

from ..models import CatalogState, Listing
from ..models.ai_query_proof import AiQueryProof
from ..schemas.ai_listing_facts import digest
from ..schemas.ai_search_intent import SearchIntent
from ..schemas.ai_search_quota import QuotaSubject
from ..schemas.listings import (
    ListingCardSearchRequest,
    ListingCardSearchResponse,
    ListingMapRequest,
    ListingMapResponse,
)
from ..services.ai_card_cursors import AICardCursors
from ..services.ai_hard_matching import HardMatchPlan, compile_hard_match
from .ai_card_values import current_card_values_predicate
from .ai_fact_pipeline import FactPipeline
from .ai_fact_population import fact_population_signature
from .ai_fact_quality import source_freshness_predicate
from .ai_query_proofs import (
    PROOF_CONTRACT_VERSION,
    current_projection_predicate,
    proof_age_predicate,
    proof_population_signature,
)
from .ai_query_settings import configure_ai_query
from .ai_search_sessions import SearchSessions, SessionError, intent_hash
from .listings import (
    _cursor_fingerprint,
    _search_filtered_cards,
    _search_filtered_map,
    apply_search_filters,
    visible_query,
)


@dataclass(frozen=True)
class VerifiedBudgetPrice:
    listing_id: str
    matched_amount: int
    matched_period: str
    display_amount: int | None
    display_period: str
    currency: str = "EUR"
    confirmation: str = "current_source_proof"


@dataclass(frozen=True)
class VerifiedMapCenter:
    listing_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class VerifiedCardResult:
    cards: ListingCardSearchResponse
    intent_hash: str
    reason_codes: tuple[str, ...]
    budget_prices: tuple[VerifiedBudgetPrice, ...] = ()
    map_center: VerifiedMapCenter | None = None


class SourceCoverageUnavailable(ValueError):
    pass


class VerifiedCardSearch:
    def __init__(self, pipeline: FactPipeline, sessions: SearchSessions, *, signing_key: bytes):
        if sessions.ledger.sessions is not pipeline.sessions:
            raise ValueError("query and owned sessions must share the same database session factory")
        self.pipeline, self.sessions = pipeline, sessions
        self.cursors = AICardCursors(signing_key)

    async def search_owned(self, subject: QuotaSubject, session_id: UUID, expected_version: int,
                           payload: ListingCardSearchRequest) -> VerifiedCardResult:
        if type(expected_version) is not int or not 0 <= expected_version <= 2_147_483_647:
            raise ValueError("bounded expected session version required")
        # Snapshot caller containers before await, including favorite IDs.
        payload = ListingCardSearchRequest.model_validate(payload.model_dump())
        async with self.pipeline.sessions() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            _, intent = await self.sessions._read(session, subject, session_id)
            if intent.version != expected_version:
                raise SessionError("SESSION_VERSION_CONFLICT")
            return await self._query_intent(session, subject, intent, payload)

    async def query_candidate(self, subject: QuotaSubject, current: SearchIntent, candidate: SearchIntent,
                              payload: ListingCardSearchRequest) -> VerifiedCardResult:
        if candidate.session_id != current.session_id or candidate.version != current.version + 1:
            raise SessionError("SESSION_STATE_INVALID")
        async with self.pipeline.sessions() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            _, owned = await self.sessions._read(session, subject, current.session_id)
            if intent_hash(owned) != intent_hash(current):
                raise SessionError("SESSION_VERSION_CONFLICT")
            self.sessions.vocabulary.validate(candidate.criteria)
            if self.pipeline.operating_policy is not None:
                # Check coverage independently of the requested constraints:
                # zero matches is meaningful only with usable source evidence.
                baseline = candidate.model_copy(update={"criteria": type(candidate.criteria)()})
                base = apply_search_filters(visible_query(), payload)
                covered = base.where(verified_intent_predicate(self.pipeline, baseline,
                    cohort_scope=_candidate_cohorts(base, self.pipeline)))
                if not await session.scalar(select(covered.exists())):
                    raise SourceCoverageUnavailable("SOURCE_COVERAGE_UNAVAILABLE")
            return await self._query_intent(session, subject, candidate, payload)

    async def query_result(self, subject: QuotaSubject, result_ref: UUID,
                           payload: ListingCardSearchRequest) -> VerifiedCardResult:
        # Durable original intent is reloaded on replay; never apply its patch
        # again or use a later conversational intent to recreate old semantics.
        committed = await self.sessions.result(subject, result_ref)
        async with self.pipeline.sessions() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            await self.sessions._read(session, subject, committed.intent.session_id)
            return await self._query_intent(session, subject, committed.intent, payload)

    async def _query_intent(self, session, subject: QuotaSubject, intent: SearchIntent,
                            payload: ListingCardSearchRequest) -> VerifiedCardResult:
        await configure_ai_query(session)
        payload = ListingCardSearchRequest.model_validate(payload.model_dump())
        compiled = compile_hard_match(intent, self.pipeline.vocabulary)
        normalized_hash = intent_hash(intent)
        catalog = await session.scalar(select(CatalogState.version).where(CatalogState.id == 1))
        facts = await session.scalar(select(fact_population_signature()))
        if facts is None:
            raise RuntimeError("fact-catalog population state is missing")
        proofs = await session.scalar(select(proof_population_signature(
            resolver_version=self.pipeline.resolver_version, vocabulary_hash=self.pipeline.vocabulary_hash)))
        if proofs is None:
            raise RuntimeError("prepared-proof population state is missing")
        context = digest({"subject": [subject.kind, str(subject.id)], "intent": normalized_hash,
            "filters": _cursor_fingerprint(payload), "catalog": catalog,
            "facts": facts, "proofs": proofs, "resolver": self.pipeline.resolver_version,
            "vocabulary": self.pipeline.vocabulary_hash, "proof_contract": PROOF_CONTRACT_VERSION})
        raw_cursor = self.cursors.decode(payload.cursor, context)
        payload = payload.model_copy(update={"cursor": raw_cursor})
        # EXISTS preserves one catalog row per listing and the existing
        # commercial ordering/gallery/redirect pipeline. No post-page filter.
        base = apply_search_filters(visible_query(), payload)
        filtered = base.where(_verified_intent_predicate(self.pipeline, intent, compiled,
            cohort_scope=_candidate_cohorts(base, self.pipeline)))
        cards = await _search_filtered_cards(session, payload, filtered, _cursor_fingerprint(payload))
        cards = cards.model_copy(update={"nextCursor": self.cursors.encode(cards.nextCursor, context),
                                         "previousCursor": self.cursors.encode(cards.previousCursor, context)})
        budget_prices: tuple[VerifiedBudgetPrice, ...] = ()
        budget = intent.criteria.budget
        if budget and budget.strength == "hard" and cards.items:
            # Same repeatable-read snapshot and already verified card IDs.
            # Preserve native card/TOP prices while exposing the actual amount
            # confirmed in the requested period, without unit conversion.
            amount = {"monthly": Listing.monthly_price, "nightly": Listing.nightly_price,
                      "weekly": Listing.weekly_price}[budget.value.period]
            values = dict((await session.execute(select(Listing.id, amount).where(
                Listing.id.in_([UUID(card.id) for card in cards.items])))).all())
            budget_prices = tuple(VerifiedBudgetPrice(card.id, values[UUID(card.id)], budget.value.period,
                card.price, "nightly" if card.rentalMode == "holiday" else "monthly") for card in cards.items)
        # Camera metadata uses only public approximate geometry from an already
        # verified page, inside this same read-only repeatable-read snapshot.
        # Never call the side-effecting public detail/view-accounting endpoint.
        map_center = None
        if cards.items:
            location = cast(Listing.location, Geometry("POINT", srid=4326))
            positions = {str(row[0]): (row[1], row[2]) for row in (await session.execute(
                select(Listing.id, ST_Y(location), ST_X(location)).where(
                    Listing.id.in_([UUID(card.id) for card in cards.items])))).all()}
            for card in cards.items:
                latitude, longitude = positions[card.id]
                if latitude is not None and longitude is not None and isfinite(latitude) and isfinite(longitude) and abs(latitude) <= 85 and abs(longitude) <= 180:
                    map_center = VerifiedMapCenter(card.id, latitude, longitude)
                    break
        return VerifiedCardResult(cards, normalized_hash, tuple(group.name for group in compiled.criteria), budget_prices, map_center)


    async def map_owned(self, subject: QuotaSubject, session_id: UUID, expected_version: int,
                        payload: ListingMapRequest) -> "VerifiedMapResult":
        if type(expected_version) is not int or not 0 <= expected_version <= 2_147_483_647:
            raise ValueError("bounded expected session version required")
        payload = ListingMapRequest.model_validate(payload.model_dump())
        async with self.pipeline.sessions() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            _, intent = await self.sessions._read(session, subject, session_id)
            if intent.version != expected_version:
                raise SessionError("SESSION_VERSION_CONFLICT")
            return await self._map_intent(session, intent, payload)

    async def map_result(self, subject: QuotaSubject, result_ref: UUID,
                         payload: ListingMapRequest) -> "VerifiedMapResult":
        payload = ListingMapRequest.model_validate(payload.model_dump())
        committed = await self.sessions.result(subject, result_ref)
        async with self.pipeline.sessions() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            await self.sessions._read(session, subject, committed.intent.session_id)
            return await self._map_intent(session, committed.intent, payload)

    async def _map_intent(self, session, intent: SearchIntent, payload: ListingMapRequest) -> "VerifiedMapResult":
        await configure_ai_query(session)
        bounded = payload.model_copy(update={"minLatitude": payload.south, "maxLatitude": payload.north,
                                             "minLongitude": payload.west, "maxLongitude": payload.east})
        base = apply_search_filters(visible_query(), bounded)
        filtered = base.where(verified_intent_predicate(self.pipeline, intent, cohort_scope=_candidate_cohorts(base, self.pipeline)))
        return VerifiedMapResult(await _search_filtered_map(session, payload, filtered), intent_hash(intent))


@dataclass(frozen=True)
class VerifiedMapResult:
    map: ListingMapResponse
    intent_hash: str


def verified_intent_predicate(pipeline: FactPipeline, intent: SearchIntent, *, cohort_scope=None):
    """Identical evidence/current card-value contract for cards, map and later saved matching."""
    return _verified_intent_predicate(pipeline, intent, compile_hard_match(intent, pipeline.vocabulary), cohort_scope=cohort_scope)


def _candidate_cohorts(base, pipeline):
    candidates = base.with_only_columns(Listing.id, maintain_column_froms=True).order_by(None).correlate(None)
    return select(AiQueryProof.match_cohort_id).where(AiQueryProof.canonical_listing_id.in_(candidates),
        AiQueryProof.input_status == "current", AiQueryProof.resolver_version == pipeline.resolver_version,
        AiQueryProof.vocabulary_hash == pipeline.vocabulary_hash, AiQueryProof.match_cohort_id.is_not(None)).distinct().correlate(None)


def _verified_intent_predicate(pipeline: FactPipeline, intent: SearchIntent, compiled: HardMatchPlan, *, cohort_scope=None):
    # Cards reuse this exact plan for reason codes; map compiles once above.
    facts = current_projection_predicate(Listing.id, resolver_version=pipeline.resolver_version,
        vocabulary_hash=pipeline.vocabulary_hash, match_plan=compiled, cohort_scope=cohort_scope)
    conditions = [facts, current_card_values_predicate(intent)]
    if pipeline.operating_policy is not None:
        conditions.append(source_freshness_predicate(Listing.__table__.c.id, compiled, pipeline.operating_policy))
        conditions.append(proof_age_predicate(Listing.id))
    return and_(*conditions)
