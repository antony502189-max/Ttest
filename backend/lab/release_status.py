"""Read-only synthetic release snapshot. Fixed aggregate fields; no private rows.

Explicit CLI only, no HTTP endpoint. Cost zero describes this finite local
parser, never a real provider account. Not a catalog capacity benchmark.
"""
import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select, text

from lab.ai_text import pipeline, require_lab, verify_database


async def snapshot():
    require_lab()
    from app.db.session import SessionLocal, engine
    from app.models import ExternalListingSource
    from app.models.ai_fact_pipeline import AiFactJob
    from app.models.ai_operating_policy import AiProofAge
    from app.models.ai_search_quota import AISearchRequest
    from app.repositories.ai_verified_cards import verified_intent_predicate
    from app.repositories.listings import visible_query
    from app.schemas.ai_search_intent import SearchIntent
    try:
        await verify_database(SessionLocal)
        async with SessionLocal() as conn, conn.begin():
            await conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            await conn.execute(text("SET LOCAL statement_timeout='3000'"))
            now = await conn.scalar(select(func.clock_timestamp()))
            source = ExternalListingSource
            total = await conn.scalar(select(func.count()).select_from(source))
            fresh = await conn.scalar(select(func.count()).select_from(source).where(
                source.current_status == "active", source.last_success_at <= now,
                source.last_success_at >= now - text("interval '24 hours'")))
            proofs = await conn.scalar(select(func.count()).select_from(AiProofAge).where(
                AiProofAge.prepared_at <= now, AiProofAge.prepared_at >= now - text("interval '24 hours'")))
            base = visible_query()
            intent = SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1",
                                  session_id=uuid4(), version=0, criteria={})
            covered = base.where(verified_intent_predicate(pipeline(SessionLocal), intent))
            coverage = await conn.scalar(select(func.count()).select_from(covered.subquery()))
            public = await conn.scalar(select(func.count()).select_from(base.subquery()))
            jobs = dict((await conn.execute(select(AiFactJob.status, func.count()).group_by(AiFactJob.status))).all())
            operations = dict((await conn.execute(select(AISearchRequest.status, func.count()).group_by(AISearchRequest.status))).all())
            overdue = await conn.scalar(select(func.count()).select_from(AISearchRequest).where(
                AISearchRequest.status.in_(["reserved", "running"]), AISearchRequest.recover_after <= now))
            oldest = await conn.scalar(select(func.min(AiFactJob.available_at)).where(AiFactJob.status == "pending"))
            return {"at": datetime.now(UTC).isoformat(), "profile": "synthetic-only",
                "sources_total": total, "sources_fresh_24h": fresh, "proofs_prepared_24h": proofs,
                "public_listings": public, "verified_listings": coverage,
                "fact_jobs": jobs, "pending_oldest_seconds": max(0, (now - oldest).total_seconds()) if oldest else 0,
                "operations": operations, "recovery_overdue": overdue,
                "provider_calls": 0, "provider_cost_usd": 0, "real_provider_cost": "unverified"}
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(snapshot())))
    except Exception:  # noqa: BLE001 - no SQL, DSN or private exception output
        raise SystemExit("AI_RELEASE_STATUS_UNAVAILABLE") from None
