"""Bounded current-proof rematching. SQL only; no model, email or manual filters."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert

from ..models import Listing, Notification
from ..models.ai_saved_rematch import AiSavedRematch, AiSavedSeen
from ..models.ai_saved_search import AiSavedSearch
from ..repositories.ai_saved_searches import RegisteredAISearches, SavedAIError, SavedAISnapshot
from ..repositories.ai_verified_cards import verified_intent_predicate
from ..repositories.listings import visible_query
from ..schemas.ai_search_intent import SearchIntent
from ..schemas.ai_search_quota import QuotaSubject
from .search_state import lock_saved_searches


def matching_ids(repo: RegisteredAISearches, saved: SavedAISnapshot):
    intent = SearchIntent(schema_version=saved.intent.schema_version,
        taxonomy_version=saved.intent.taxonomy_version, session_id=saved.id,
        version=0, criteria=saved.intent.criteria)
    return visible_query().where(verified_intent_predicate(repo.pipeline, intent)).with_only_columns(Listing.id).order_by(None)


async def initialize_rematch(conn, repo: RegisteredAISearches, saved: SavedAISnapshot) -> None:
    """Same transaction as save: current matches form the baseline, not alerts."""
    current = matching_ids(repo, saved).subquery()
    await conn.execute(insert(AiSavedSeen).from_select(["saved_search_id", "listing_id"],
        select(literal(saved.id), current.c.id)).on_conflict_do_nothing())
    conn.add(AiSavedRematch(saved_search_id=saved.id, fence=0))


@dataclass(frozen=True)
class RematchClaim:
    saved_id: UUID
    owner_id: UUID
    revision: int
    fence: int
    token: UUID


class SavedNotificationWorker:
    def __init__(self, repo: RegisteredAISearches, *, daily_limit: int, batch_size: int, cadence_seconds: int):
        if not (type(daily_limit) is int and 1 <= daily_limit <= 100 and
                type(batch_size) is int and 1 <= batch_size <= 100 and
                type(cadence_seconds) is int and 60 <= cadence_seconds <= 86400):
            raise ValueError("explicit bounded saved notification policy required")
        self.repo, self.daily_limit, self.batch_size, self.cadence_seconds = repo, daily_limit, batch_size, cadence_seconds

    async def claim(self) -> RematchClaim | None:
        async with self.repo.connections.begin() as conn:
            now = await conn.scalar(select(func.clock_timestamp()))
            if not isinstance(now, datetime):
                raise TypeError("AI_SAVED_CLOCK_UNAVAILABLE")
            row = (await conn.execute(select(AiSavedRematch, AiSavedSearch.user_id, AiSavedSearch.revision)
                .join(AiSavedSearch, AiSavedSearch.saved_search_id == AiSavedRematch.saved_search_id)
                .where(AiSavedSearch.enabled.is_(True), AiSavedRematch.next_at <= now,
                    or_(AiSavedRematch.lease_until.is_(None), AiSavedRematch.lease_until <= now))
                .order_by(AiSavedRematch.next_at, AiSavedRematch.saved_search_id)
                .with_for_update(of=AiSavedRematch, skip_locked=True).limit(1))).first()
            if row is None:
                return None
            cursor, owner, revision = row
            cursor.fence += 1
            cursor.lease_token, cursor.lease_until = uuid4(), now + timedelta(seconds=30)
            return RematchClaim(cursor.saved_search_id, owner, revision, cursor.fence, cursor.lease_token)

    async def run(self, claim: RematchClaim) -> int:
        subject = QuotaSubject(kind="auth", id=claim.owner_id)
        async with self.repo.connections.begin() as conn:
            # Same locks as explicit save/disable/delete/account erasure.
            await lock_saved_searches(subject.id, conn)
            await self.repo.sessions.lock_subject(conn, subject)
            try:
                child, saved = await self.repo._read(conn, subject, claim.saved_id, lock=True)
            except SavedAIError as error:
                if str(error) in {"SAVED_AI_NOT_FOUND", "REGISTERED_USER_UNAVAILABLE"}:
                    return 0
                raise
            cursor = await conn.scalar(select(AiSavedRematch).where(
                AiSavedRematch.saved_search_id == saved.id).with_for_update())
            now = await conn.scalar(select(func.clock_timestamp()))
            if not isinstance(now, datetime):
                raise TypeError("AI_SAVED_CLOCK_UNAVAILABLE")
            if (cursor is None or cursor.fence != claim.fence or cursor.lease_token != claim.token
                    or cursor.lease_until is None or cursor.lease_until <= now):
                return 0
            if not child.enabled or child.revision != claim.revision:
                cursor.lease_token = cursor.lease_until = None
                cursor.next_at = now + timedelta(seconds=self.cadence_seconds)
                return 0
            # Distinct background allowance, shared across all searches of this
            # user under the collection lock. Never reserve foreground quota.
            madrid_date = func.date(func.timezone("Europe/Madrid", now))
            used = await conn.scalar(select(func.count()).select_from(Notification).where(
                Notification.recipient_user_id == subject.id, Notification.type == "ai_saved_match",
                func.date(func.timezone("Europe/Madrid", Notification.created_at)) == madrid_date))
            allowance = max(0, self.daily_limit - (used or 0))
            query = matching_ids(self.repo, saved)
            if cursor.cursor_listing_id is not None:
                query = query.where(Listing.id > cursor.cursor_listing_id)
            ids = list(await conn.scalars(query.order_by(Listing.id).limit(self.batch_size)))
            delivered = 0
            for listing_id in ids:
                if allowance <= delivered:
                    # Do not checkpoint past unsent rows; resume after quota
                    # refresh rather than permanently forgetting a new match.
                    break
                seen = await conn.get(AiSavedSeen, (saved.id, listing_id))
                if seen is None:
                    # Re-evaluate live proof/visibility immediately before the
                    # atomic in-app delivery. Old events/claims grant no rights.
                    eligible = matching_ids(self.repo, saved).where(Listing.id == listing_id).subquery()
                    created = await conn.scalar(insert(Notification).from_select(
                        ["id", "recipient_user_id", "type", "title", "body", "entity_listing_id", "idempotency_key"],
                        select(literal(uuid4()), literal(subject.id), literal("ai_saved_match"),
                            literal("Nueva coincidencia para tu búsqueda IA"),
                            literal("Hay un anuncio que cumple las condiciones de tu búsqueda guardada."),
                            eligible.c.id, literal(f"ai-saved:{saved.id}:{listing_id}")).where(
                                self.repo.active_owner_query(subject.id).exists()))
                        .on_conflict_do_nothing(index_elements=["recipient_user_id", "idempotency_key"])
                        .returning(Notification.id))
                    if created is not None:
                        conn.add(AiSavedSeen(saved_search_id=saved.id, listing_id=listing_id))
                        delivered += 1
                cursor.cursor_listing_id = listing_id
            if len(ids) < self.batch_size and (not ids or cursor.cursor_listing_id == ids[-1]):
                cursor.cursor_listing_id = None
            cursor.lease_token = cursor.lease_until = None
            cursor.next_at = now + timedelta(seconds=self.cadence_seconds)
            return delivered
