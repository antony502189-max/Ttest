"""Explicit owned-session query using existing public eligibility/cards/TOP.

No public endpoint/activation/provider and no debit: new-message orchestration
must use quota finalize; page reads reuse an already-owned normalized session.
"""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, text

from ..models import CatalogState, Listing
from ..models.ai_fact_pipeline import AiFactCatalog
from ..models.ai_listing_facts import AiListingSearchFeatures
from ..schemas.ai_listing_facts import digest
from ..schemas.ai_search_quota import QuotaSubject
from ..schemas.listings import ListingCardSearchRequest, ListingCardSearchResponse
from ..services.ai_card_cursors import AICardCursors
from ..services.ai_hard_matching import compile_hard_match
from .ai_fact_pipeline import FactPipeline
from .ai_hard_matching import hard_match_predicate
from .ai_query_proofs import current_projection_predicate
from .ai_search_sessions import SearchSessions, SessionError, intent_hash
from .listings import _cursor_fingerprint, _search_filtered_cards, apply_search_filters, visible_query


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
            compiled = compile_hard_match(intent, self.pipeline.vocabulary)
            normalized_hash = intent_hash(intent)
            catalog = await session.scalar(select(CatalogState.version).where(CatalogState.id == 1))
            facts = (await session.execute(select(func.count(), func.coalesce(func.sum(AiFactCatalog.revision), 0)))).one()
            context = digest({"subject": [subject.kind, str(subject.id)], "intent": normalized_hash,
                "filters": _cursor_fingerprint(payload), "catalog": catalog,
                "facts": [facts[0], str(facts[1])], "resolver": self.pipeline.resolver_version,
                "vocabulary": self.pipeline.vocabulary_hash})
            raw_cursor = self.cursors.decode(payload.cursor, context)
            payload = payload.model_copy(update={"cursor": raw_cursor})
            # EXISTS preserves one catalog row per listing and the existing
            # commercial ordering/gallery/redirect pipeline. No post-page filter.
            verified = select(1).select_from(AiListingSearchFeatures).where(
                AiListingSearchFeatures.canonical_listing_id == Listing.id,
                current_projection_predicate(Listing.id, resolver_version=self.pipeline.resolver_version,
                                             vocabulary_hash=self.pipeline.vocabulary_hash),
                hard_match_predicate(AiListingSearchFeatures.__table__.c.features, compiled),
            ).correlate(Listing).exists()
            filtered = apply_search_filters(visible_query(), payload).where(verified)
            cards = await _search_filtered_cards(session, payload, filtered, _cursor_fingerprint(payload))
            cards = cards.model_copy(update={"nextCursor": self.cursors.encode(cards.nextCursor, context),
                                             "previousCursor": self.cursors.encode(cards.previousCursor, context)})
            return VerifiedCardResult(cards, normalized_hash, tuple(group.name for group in compiled.criteria))
