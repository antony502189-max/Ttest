"""Explicit owned-session query using existing public eligibility/cards/TOP.

No public endpoint/activation/provider and no debit: new-message orchestration
must use quota finalize; page reads reuse an already-owned normalized session.

Pagination is live keyset, not a frozen result set. Each page rechecks current
source/public eligibility and TOP ordering in its own repeatable-read snapshot.
Signed context detects intent/filter/config/catalog/fact/prepared-proof changes,
but direct source, user/moderation changes and clock-driven TOP changes can
alter totals/order without rejecting a cursor. Restart without a cursor to
discover rows newly eligible or moved before the seek point. No stale card is
kept merely to preserve an earlier page's total or order.
"""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, func, select, text

from ..models import CatalogState, Listing
from ..models.ai_fact_pipeline import AiFactCatalog
from ..models.ai_listing_facts import AiListingSearchFeatures
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
from ..services.ai_hard_matching import compile_hard_match
from .ai_card_values import current_card_values_predicate
from .ai_fact_pipeline import FactPipeline
from .ai_hard_matching import hard_match_predicate
from .ai_query_proofs import PROOF_CONTRACT_VERSION, current_projection_predicate, proof_population_signature
from .ai_search_sessions import SearchSessions, SessionError, intent_hash
from .listings import (
    _cursor_fingerprint,
    _search_filtered_cards,
    _search_filtered_map,
    apply_search_filters,
    visible_query,
)


@dataclass(frozen=True)
class VerifiedCardResult:
    cards: ListingCardSearchResponse
    intent_hash: str
    reason_codes: tuple[str, ...]


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
        payload = ListingCardSearchRequest.model_validate(payload.model_dump())
        compiled = compile_hard_match(intent, self.pipeline.vocabulary)
        normalized_hash = intent_hash(intent)
        catalog = await session.scalar(select(CatalogState.version).where(CatalogState.id == 1))
        facts = (await session.execute(select(func.count(), func.coalesce(func.sum(AiFactCatalog.revision), 0)))).one()
        proofs = await session.scalar(select(proof_population_signature(
            resolver_version=self.pipeline.resolver_version, vocabulary_hash=self.pipeline.vocabulary_hash)))
        context = digest({"subject": [subject.kind, str(subject.id)], "intent": normalized_hash,
            "filters": _cursor_fingerprint(payload), "catalog": catalog,
            "facts": [facts[0], str(facts[1])], "proofs": proofs, "resolver": self.pipeline.resolver_version,
            "vocabulary": self.pipeline.vocabulary_hash, "proof_contract": PROOF_CONTRACT_VERSION})
        raw_cursor = self.cursors.decode(payload.cursor, context)
        payload = payload.model_copy(update={"cursor": raw_cursor})
        # EXISTS preserves one catalog row per listing and the existing
        # commercial ordering/gallery/redirect pipeline. No post-page filter.
        filtered = apply_search_filters(visible_query(), payload).where(verified_intent_predicate(self.pipeline, intent))
        cards = await _search_filtered_cards(session, payload, filtered, _cursor_fingerprint(payload))
        cards = cards.model_copy(update={"nextCursor": self.cursors.encode(cards.nextCursor, context),
                                         "previousCursor": self.cursors.encode(cards.previousCursor, context)})
        return VerifiedCardResult(cards, normalized_hash, tuple(group.name for group in compiled.criteria))


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
        bounded = payload.model_copy(update={"minLatitude": payload.south, "maxLatitude": payload.north,
                                             "minLongitude": payload.west, "maxLongitude": payload.east})
        filtered = apply_search_filters(visible_query(), bounded).where(verified_intent_predicate(self.pipeline, intent))
        return VerifiedMapResult(await _search_filtered_map(session, payload, filtered), intent_hash(intent))


@dataclass(frozen=True)
class VerifiedMapResult:
    map: ListingMapResponse
    intent_hash: str


def verified_intent_predicate(pipeline: FactPipeline, intent: SearchIntent):
    """Identical evidence/current card-value contract for cards, map and later saved matching."""
    compiled = compile_hard_match(intent, pipeline.vocabulary)
    facts = select(1).select_from(AiListingSearchFeatures).where(
        AiListingSearchFeatures.canonical_listing_id == Listing.id,
        current_projection_predicate(Listing.id, resolver_version=pipeline.resolver_version,
                                     vocabulary_hash=pipeline.vocabulary_hash),
        hard_match_predicate(AiListingSearchFeatures.__table__.c.features, compiled),
    ).correlate(Listing).exists()
    return and_(facts, current_card_values_predicate(intent))
