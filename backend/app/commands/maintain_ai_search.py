"""Explicit AI recovery/GC runner; no application DSN, provider or auto-start.

AI_MAINTENANCE_DATABASE_URL must identify the intended database. --loop runs
recovery every five seconds and retention hourly; default is one bounded pass.
Only aggregate counters and fixed errors leave this process.
"""
import argparse
import asyncio
import json
import os
from dataclasses import asdict

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ..repositories.ai_fact_pipeline import FactPipeline
from ..repositories.ai_search_quota import QuotaLedger
from ..repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
from ..schemas.ai_fact_pipeline import FactQueuePolicy
from ..schemas.ai_listing_facts import FactVocabulary
from ..schemas.ai_search_quota import LeasePolicy
from ..services.ai_erasure_journal import configured_journal, replay_erasure
from ..services.ai_fact_retention import AIFactRetention
from ..services.ai_retention import AIRetention


async def run(*, loop: bool) -> None:
    dsn = os.environ.get("AI_MAINTENANCE_DATABASE_URL")
    if not dsn:
        raise ValueError("AI_MAINTENANCE_DATABASE_REQUIRED")
    engine = create_async_engine(dsn, pool_size=1, max_overflow=0, pool_timeout=3,
        connect_args={"server_settings": {"statement_timeout": "3000", "lock_timeout": "1000"}})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ledger = QuotaLedger(factory, LeasePolicy(reservation_seconds=10, running_seconds=30, recovery_grace_seconds=10))
    sessions = SearchSessions(ledger, SessionPolicy(inactivity_seconds=86400),
        IntentVocabulary(frozenset(), frozenset(), frozenset()))
    collector = AIRetention(sessions)
    facts = AIFactRetention(FactPipeline(factory, FactQueuePolicy(lease_seconds=30, max_attempts=1, retry_delay_seconds=1),
        FactVocabulary(amenity_codes=frozenset(), catalog_other_codes=frozenset(), tenant_group_codes=frozenset(),
            municipality_zones=frozenset()), resolver_version="retention.v1"))
    next_gc = 0.0
    try:
        while True:
            async with asyncio.timeout(15):
                journal = configured_journal()
                if journal is None:
                    raise ValueError("AI_ERASURE_JOURNAL_REQUIRED")
                # Process pending accepted deletions before dropping old
                # intents; retention must never forget an incomplete erasure.
                replayed = await replay_erasure(factory, journal)
                recovered = await ledger.recover_expired(batch_size=100)
                counters = {"recovered": len(recovered), "erasure_intents": replayed}
                now = asyncio.get_running_loop().time()
                if recovered:
                    next_gc = min(next_gc, now)
                if now >= next_gc:
                    await asyncio.to_thread(journal.compact)
                    state_counts = asdict(await collector.prune())
                    fact_counts = await facts.prune()
                    counters.update(state_counts)
                    counters.update({"fact_" + key: value for key, value in fact_counts.items()})
                    # A batch is not a completed deletion. Drain backlog on the
                    # next bounded tick instead of postponing each parent by an
                    # hour; return to hourly idle checks once nothing changes.
                    next_gc = now + (5 if any((*state_counts.values(), *fact_counts.values())) else 3600)
                print(json.dumps(counters), flush=True)
            if not loop:
                break
            await asyncio.sleep(5)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(loop=args.loop))
    except KeyboardInterrupt:
        pass
    except Exception:  # noqa: BLE001 - fixed private error, no DSN/SQL export
        # Never echo a DSN, SQL, connection error or private row.
        raise SystemExit("AI_MAINTENANCE_FAILED") from None


if __name__ == "__main__":
    main()
