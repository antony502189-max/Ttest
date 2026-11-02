"""Bounded AI session/result GC. Receipts outlive private conversational state.

No daemon is started by importing this module. This service uses only the
explicitly supplied database, never application settings or provider clients.
"""
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, func, or_, select, update

from ..models.ai_search_quota import AISearchRequest, AIUsageDay
from ..models.ai_search_session import AISearchResult, AISearchSession, AISessionCommand
from ..repositories.ai_search_quota import _now
from ..repositories.ai_search_sessions import SearchSessions


@dataclass(frozen=True)
class RetentionResult:
    sessions: int
    results: int
    requests: int
    usage_days: int


class AIRetention:
    def __init__(self, sessions: SearchSessions):
        self.sessions = sessions
        self.factory = sessions.ledger.sessions

    async def prune(self, *, batch_size: int = 1000) -> RetentionResult:
        if type(batch_size) is not int or not 1 <= batch_size <= 1000:
            raise ValueError("retention batch must be between 1 and 1000")
        # Lock session, but never request/day after it. Finalize locks day then
        # request then session; this collector must not invert that lock order.
        async with self.factory.begin() as conn:
            now = await _now(conn)
            terminal_only = ~select(1).where(
                AISearchRequest.session_id == AISearchSession.id,
                AISearchRequest.status.in_(("reserved", "running")),
            ).exists()
            expiry = func.least(AISearchSession.expires_at,
                AISearchSession.created_at + timedelta(seconds=self.sessions.policy.absolute_seconds),
                func.coalesce(AISearchSession.closed_at, AISearchSession.expires_at))
            unreferenced = ~select(1).where(AISearchRequest.session_id == AISearchSession.id).exists()
            no_results = ~select(1).where(AISearchResult.session_id == AISearchSession.id).exists()
            commands = select(1).where(or_(AISessionCommand.result_id == AISearchSession.id,
                AISessionCommand.source_id == AISearchSession.id)).exists()
            initial = or_(AISearchSession.criteria == {}, *(
                AISearchSession.criteria == {"rental_mode": {"strength": "hard", "value": mode}}
                for mode in ("long", "holiday")))
            seed = (AISearchSession.version == 0) & initial & unreferenced & no_results & ~commands & (
                AISearchSession.schema_version == "ai-search.v1") & (
                AISearchSession.taxonomy_version == "rental.v1") & (
                AISearchSession.created_at <= now - timedelta(hours=1))
            ids = list(await conn.scalars(select(AISearchSession.id).where(
                terminal_only, or_((expiry <= now - timedelta(hours=24)) & or_(
                    ~commands, AISearchSession.criteria != {}, ~no_results, AISearchSession.closed_at.is_(None)), seed),
            ).order_by(AISearchSession.created_at, AISearchSession.id).limit(batch_size).with_for_update(skip_locked=True)))
            result_ids = []
            if ids:
                # A long conversation can have more rows than the batch. It is
                # already inaccessible; remove at most one bounded result batch
                # and leave the expired parent until all dependents are gone.
                old_results = select(AISearchResult.id).where(AISearchResult.session_id.in_(ids)).order_by(
                    AISearchResult.created_at, AISearchResult.id).limit(batch_size)
                result_ids = list(await conn.scalars(delete(AISearchResult).where(
                    AISearchResult.id.in_(old_results)).returning(AISearchResult.id)))
                # Keyed create/reset receipts keep their FKs. Erase private
                # criteria but retain a closed minimal shell until receipt GC.
                await conn.execute(update(AISearchSession).where(AISearchSession.id.in_(ids), commands).values(
                    criteria={}, closed_at=func.coalesce(AISearchSession.closed_at, now)))
                ids = list(await conn.scalars(delete(AISearchSession).where(
                    AISearchSession.id.in_(ids), no_results, ~commands).returning(AISearchSession.id)))
        # Separate short transactions: requests have no FK to private result.
        # Keep original result_ref/count so a lost acknowledgement remains
        # authoritative even when its criteria have been physically deleted.
        async with self.factory.begin() as conn:
            now = await _now(conn)
            live = AISearchSession.__table__.alias()
            live_command = select(1).select_from(live).where(or_(live.c.id == AISessionCommand.result_id,
                live.c.id == AISessionCommand.source_id), live.c.closed_at.is_(None), live.c.expires_at > now,
                live.c.created_at > now - timedelta(seconds=self.sessions.policy.absolute_seconds)).exists()
            command_rows = list(await conn.scalars(select(AISessionCommand).where(
                AISessionCommand.created_at <= now - timedelta(days=30), ~live_command).order_by(
                AISessionCommand.created_at).limit(batch_size).with_for_update(skip_locked=True)))
            for command in command_rows:
                await conn.delete(command)
            old = select(AISearchRequest).where(
                AISearchRequest.status.in_(("succeeded", "failed")),
                AISearchRequest.completed_at <= now - timedelta(days=30),
                ~select(1).where(AISearchResult.subject_kind == AISearchRequest.subject_kind,
                    AISearchResult.subject_id == AISearchRequest.subject_id,
                    AISearchResult.idempotency_key == AISearchRequest.idempotency_key).exists(),
                # Never drop the last anti-replay protection for a live dialog,
                # including legacy rows made with a more permissive policy.
                ~select(1).where(AISearchSession.id == AISearchRequest.session_id).exists(),
            ).order_by(AISearchRequest.completed_at, AISearchRequest.idempotency_key).limit(batch_size).with_for_update(skip_locked=True)
            rows = list(await conn.scalars(old))
            for row in rows:
                await conn.delete(row)
        async with self.factory.begin() as conn:
            # Madrid date, not UTC date, defines quota-day retention.
            cutoff = func.cast(func.timezone("Europe/Madrid", func.clock_timestamp()), AIUsageDay.madrid_date.type) - 30
            old_days = list(await conn.scalars(select(AIUsageDay).where(
                AIUsageDay.madrid_date < cutoff, AIUsageDay.reserved == 0,
                ~select(1).where(AISearchRequest.subject_kind == AIUsageDay.subject_kind,
                    AISearchRequest.subject_id == AIUsageDay.subject_id,
                    AISearchRequest.madrid_date == AIUsageDay.madrid_date).exists(),
            ).order_by(AIUsageDay.madrid_date, AIUsageDay.subject_id).limit(batch_size).with_for_update(skip_locked=True)))
            for old_day in old_days:
                await conn.delete(old_day)
        return RetentionResult(len(ids), len(result_ids), len(rows), len(old_days))
