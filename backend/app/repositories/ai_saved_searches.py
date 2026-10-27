"""Offline registered snapshots and current-proof dry runs. Delivery stays off."""
import json
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models import Listing, SavedSearch, User
from ..models.ai_fact_pipeline import AiFactRematchEvent
from ..models.ai_saved_search import AiSavedSearch
from ..models.moderation import UserRestriction
from ..schemas.ai_listing_facts import digest
from ..schemas.ai_search_intent import Criteria, SearchIntent
from ..schemas.ai_search_quota import QuotaSubject, StrictContract
from ..services.moderation import active_window
from ..services.search_state import lock_saved_searches, saved_search_count
from .ai_fact_pipeline import FactPipeline
from .ai_search_sessions import SearchSessions
from .ai_verified_cards import verified_intent_predicate
from .listings import visible_query


class SavedAIError(ValueError):
    pass


class SavedIntent(StrictContract):
    # No session, result reference or expiry dependency is stored here.
    schema_version: Literal["ai-search.v1"]
    taxonomy_version: Literal["rental.v1"]
    criteria: Criteria = Field(repr=False)


class SavedAISnapshot(StrictContract):
    id: UUID
    revision: int = Field(ge=1)
    enabled: bool
    intent: SavedIntent = Field(repr=False)
    intent_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class SavedAIDryRun(StrictContract):
    saved_search_id: UUID
    saved_revision: int
    intent_hash: str
    listing_id: UUID
    status: Literal["matched", "not_verified_or_ineligible", "disabled"]
    delivery_enabled: Literal[False] = False


class RegisteredAISearches:
    def __init__(self, sessions: SearchSessions, pipeline: FactPipeline):
        if sessions.ledger.sessions is not pipeline.sessions:
            raise ValueError("saved search and verified matcher must share one database authority")
        self.sessions, self.pipeline = sessions, pipeline
        self.connections = sessions.ledger.sessions

    @staticmethod
    def _subject(subject: QuotaSubject) -> QuotaSubject:
        subject = QuotaSubject.model_validate(subject.model_dump())
        if subject.kind != "auth":
            raise SavedAIError("REGISTERED_USER_REQUIRED")
        return subject

    @staticmethod
    async def _active(conn: AsyncSession, subject: QuotaSubject) -> None:
        restriction = select(1).where(UserRestriction.user_id == User.id,
            UserRestriction.restriction_type.in_(("full", "view_listings")),
            *active_window(UserRestriction)).correlate(User).exists()
        owner = await conn.scalar(select(User.id).where(User.id == subject.id, User.deleted_at.is_(None),
                                                       User.blocked.is_(False), ~restriction))
        if owner is None:
            raise SavedAIError("REGISTERED_USER_UNAVAILABLE")

    def _decode(self, parent: SavedSearch, child: AiSavedSearch) -> SavedAISnapshot:
        try:
            if (parent.matcher != "ai.v1" or child.matcher != "ai.v1" or parent.rental_mode is not None
                    or parent.query != "" or parent.filters != {} or parent.polygon != [] or parent.alerts_enabled):
                raise ValueError("hybrid matcher")
            intent = SavedIntent.model_validate_json(json.dumps({"schema_version": child.schema_version,
                "taxonomy_version": child.taxonomy_version, "criteria": child.criteria}))
            self.sessions.vocabulary.validate(intent.criteria)
            if digest(intent.model_dump(mode="json", exclude_none=True)) != child.intent_hash:
                raise ValueError("snapshot mismatch")
            return SavedAISnapshot(id=parent.id, revision=child.revision, enabled=child.enabled,
                                   intent=intent, intent_hash=child.intent_hash)
        except (ValueError, TypeError):
            raise SavedAIError("SAVED_AI_STATE_INVALID") from None

    async def _read(self, conn: AsyncSession, subject: QuotaSubject, saved_id: UUID, *, lock=False):
        await self._active(conn, subject)
        query = select(SavedSearch, AiSavedSearch).join(AiSavedSearch,
            AiSavedSearch.saved_search_id == SavedSearch.id).where(SavedSearch.id == saved_id,
            SavedSearch.user_id == subject.id, SavedSearch.matcher == "ai.v1")
        result = (await conn.execute(query.with_for_update() if lock else query)).one_or_none()
        if result is None:
            raise SavedAIError("SAVED_AI_NOT_FOUND")
        parent, child = result
        return parent, child, self._decode(parent, child)

    async def save(self, subject: QuotaSubject, result_ref: UUID, *, name: str = "") -> SavedAISnapshot:
        """Explicit save of an owned committed result; no caller criteria/hash accepted."""
        subject = self._subject(subject)
        if type(name) is not str or len(name) > 120:
            raise SavedAIError("SAVED_AI_NAME_INVALID")
        async with self.connections.begin() as conn:
            # Same collection lock and existing total limit as manual saves/import.
            await lock_saved_searches(subject.id, conn)
            await self._active(conn, subject)
            if await saved_search_count(subject.id, conn) >= get_settings().max_saved_searches_per_user:
                raise SavedAIError("SAVED_SEARCH_LIMIT")
            committed = await self.sessions.result(subject, result_ref)
            copied = SavedIntent(schema_version=committed.intent.schema_version,
                taxonomy_version=committed.intent.taxonomy_version, criteria=committed.intent.criteria)
            self.sessions.vocabulary.validate(copied.criteria)
            saved_id = uuid4()
            parent = SavedSearch(id=saved_id, user_id=subject.id, name=name.strip(), matcher="ai.v1",
                query="", rental_mode=None, filters={}, polygon=[], alerts_enabled=False)
            conn.add(parent)
            await conn.flush()
            child = AiSavedSearch(saved_search_id=saved_id, matcher="ai.v1", revision=1, enabled=True,
                schema_version=copied.schema_version, taxonomy_version=copied.taxonomy_version,
                criteria=copied.criteria.model_dump(mode="json", exclude_none=True),
                intent_hash=digest(copied.model_dump(mode="json", exclude_none=True)))
            conn.add(child)
            await conn.flush()
            return self._decode(parent, child)

    async def get(self, subject: QuotaSubject, saved_id: UUID) -> SavedAISnapshot:
        subject = self._subject(subject)
        async with self.connections() as conn:
            return (await self._read(conn, subject, saved_id))[2]

    async def set_enabled(self, subject: QuotaSubject, saved_id: UUID, revision: int, enabled: bool) -> SavedAISnapshot:
        subject = self._subject(subject)
        if type(revision) is not int or revision < 1 or type(enabled) is not bool:
            raise SavedAIError("SAVED_AI_COMMAND_INVALID")
        async with self.connections.begin() as conn:
            parent, child, current = await self._read(conn, subject, saved_id, lock=True)
            if current.revision != revision:
                raise SavedAIError("SAVED_AI_VERSION_CONFLICT")
            child.enabled = enabled
            child.revision += 1
            await conn.flush()
            return self._decode(parent, child)

    async def _decision(self, conn: AsyncSession, subject: QuotaSubject, saved_id: UUID, listing_id: UUID) -> SavedAIDryRun:
        snapshot = (await self._read(conn, subject, saved_id))[2]
        status: Literal["matched", "not_verified_or_ineligible", "disabled"] = "disabled"
        if snapshot.enabled:
            # Synthetic matching identity only; immutable saved criteria/hash are
            # independent of the original conversation and its mutable version.
            intent = SearchIntent(schema_version=snapshot.intent.schema_version,
                taxonomy_version=snapshot.intent.taxonomy_version, session_id=snapshot.id,
                version=0, criteria=snapshot.intent.criteria)
            found = await conn.scalar(visible_query().where(Listing.id == listing_id,
                verified_intent_predicate(self.pipeline, intent)).with_only_columns(Listing.id).limit(1))
            status = "matched" if found else "not_verified_or_ineligible"
        return SavedAIDryRun(saved_search_id=saved_id, saved_revision=snapshot.revision,
            intent_hash=snapshot.intent_hash, listing_id=listing_id, status=status)

    async def dry_run(self, subject: QuotaSubject, saved_id: UUID, listing_id: UUID) -> SavedAIDryRun:
        subject = self._subject(subject)
        async with self.connections() as conn, conn.begin():
            await conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            return await self._decision(conn, subject, saved_id, listing_id)

    async def dry_run_event(self, subject: QuotaSubject, saved_id: UUID, event_id: UUID) -> SavedAIDryRun:
        """Inspect current state, never trust an event's old revision/hash or ack it."""
        subject = self._subject(subject)
        async with self.connections() as conn, conn.begin():
            await conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            listing_id = await conn.scalar(select(AiFactRematchEvent.canonical_listing_id).where(AiFactRematchEvent.id == event_id))
            if listing_id is None:
                raise SavedAIError("REMATCH_EVENT_NOT_FOUND")
            return await self._decision(conn, subject, saved_id, listing_id)
