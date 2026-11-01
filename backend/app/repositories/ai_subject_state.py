"""Shared identity mutation order and physical account erasure, local SQL only."""
import asyncio
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SavedSearch
from ..models.ai_saved_search import AiSavedSearch, AiSavedSearchCommand
from ..models.ai_search_quota import AISearchRequest, AIUsageDay
from ..models.ai_search_session import AISearchResult, AISearchSession, AISessionCommand
from ..schemas.ai_search_quota import QuotaSubject


async def lock_subject(conn: AsyncSession, subject: QuotaSubject) -> None:
    await conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"ai-session-create:{subject.kind}:{subject.id}"})


async def erase_account(conn: AsyncSession, user_id: UUID) -> None:
    """Caller holds auth subject advisory BEFORE User, then marks User deleted.

    Admission uses advisory -> day -> session. Finalize/recovery use day ->
    request -> session and never acquire advisory/User. Preserve this order.
    A deleted auth identity cannot create a fresh session; no quota marker is
    needed after erasure. Ordinary history/reset never calls this function.
    """
    from ..services.ai_erasure_journal import REPLAYING, configured_journal
    journal = configured_journal()
    if journal is not None and not REPLAYING.get():
        await asyncio.to_thread(journal.append, user_id)
    owned = lambda model: (model.subject_kind == "auth", model.subject_id == user_id)
    await conn.scalars(select(AIUsageDay).where(*owned(AIUsageDay)).order_by(
        AIUsageDay.madrid_date).with_for_update())
    await conn.scalars(select(AISearchRequest).where(*owned(AISearchRequest)).order_by(
        AISearchRequest.madrid_date, AISearchRequest.idempotency_key).with_for_update())
    await conn.scalars(select(AISearchSession).where(*owned(AISearchSession)).order_by(
        AISearchSession.id).with_for_update())
    await conn.execute(delete(AISearchResult).where(*owned(AISearchResult)))
    await conn.execute(delete(AISessionCommand).where(*owned(AISessionCommand)))
    await conn.execute(delete(AISearchSession).where(*owned(AISearchSession)))
    await conn.execute(delete(AISearchRequest).where(*owned(AISearchRequest)))
    await conn.execute(delete(AIUsageDay).where(*owned(AIUsageDay)))
    # Independent AI snapshots are owned directly by User in the current
    # schema, so deleting a legacy parent cannot remove them by cascade.
    # Account-delete callers also hold the saved-search collection lock.
    await conn.execute(delete(SavedSearch).where(SavedSearch.user_id == user_id, SavedSearch.matcher == "ai.v1"))
    await conn.execute(delete(AiSavedSearchCommand).where(AiSavedSearchCommand.user_id == user_id))
    await conn.execute(delete(AiSavedSearch).where(AiSavedSearch.user_id == user_id))
