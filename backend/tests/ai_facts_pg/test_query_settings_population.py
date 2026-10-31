"""Real transaction/pool and database-writer population invariants."""
import asyncio
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.ai_query_proof import AiQueryProof
from app.repositories.ai_query_proofs import proof_population_signature
from app.repositories.ai_query_settings import configure_ai_query

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def population(pipeline):
    _, sessions = pipeline
    async with sessions() as session, session.begin():
        def migrate(connection):
            with Operations.context(MigrationContext.configure(connection)):
                connection.execute(text("CREATE TABLE listing_room_details (listing_id uuid PRIMARY KEY)"))
                for name in ("0071_ai_query_proofs", "0075_ai_proof_population", "0077_ai_live_inputs"):
                    path = Path(__file__).parents[2] / "alembic/versions" / (name + ".py")
                    spec = importlib.util.spec_from_file_location(name, path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.upgrade()
        await (await session.connection()).run_sync(migrate)
    return sessions


def identity():
    return select(proof_population_signature(resolver_version="test.v1", vocabulary_hash="a" * 64))


def member():
    return {"canonical_listing_id": uuid4(), "signature": "b" * 64, "vocabulary_hash": "a" * 64,
            "resolver_version": "test.v1", "feature_revision": 1}


async def test_population_direct_bulk_upsert_noops_delete_truncate_and_recreation(population):
    sessions = population
    async with sessions() as s, s.begin():
        initial = await s.scalar(identity())
        rows = [member() for _ in range(8)]
        await s.execute(insert(AiQueryProof).values(rows))
        inserted = await s.scalar(identity())
        assert int(inserted.rsplit(":", 1)[1]) == int(initial.rsplit(":", 1)[1]) + 1
        plan = await s.scalar(text("EXPLAIN (FORMAT JSON) " + str(identity().compile(
            dialect=s.bind.dialect, compile_kwargs={"literal_binds": True}))))
        assert "ai_query_proofs" not in str(plan)
        await s.execute(text("UPDATE ai_query_proofs SET signature = signature"))
        assert await s.scalar(identity()) == inserted
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(AiQueryProof).values(rows[0])
        await s.execute(stmt.on_conflict_do_update(index_elements=[AiQueryProof.canonical_listing_id],
                                                  set_={"signature": stmt.excluded.signature}))
        assert await s.scalar(identity()) == inserted
        # Every persisted proof field participates, including scope/remap.
        for field, value in (("signature", "c" * 64), ("feature_revision", 2),
                             ("resolver_version", "other.v1"), ("vocabulary_hash", "d" * 64),
                             ("canonical_listing_id", uuid4())):
            before = await s.scalar(identity())
            await s.execute(update(AiQueryProof).where(AiQueryProof.canonical_listing_id == rows[0]["canonical_listing_id"])
                            .values(**{field: value}))
            assert await s.scalar(identity()) != before
        before = await s.scalar(identity())
        await s.execute(text("DELETE FROM ai_query_proofs"))
        assert await s.scalar(identity()) != before
        before = await s.scalar(identity())
        await s.execute(text("TRUNCATE ai_query_proofs"))
        assert await s.scalar(identity()) != before
        before = await s.scalar(identity())
        raw = await (await s.connection()).get_raw_connection()
        copied = [member() for _ in range(8)]
        columns = list(copied[0])
        await raw.driver_connection.copy_records_to_table("ai_query_proofs", columns=columns,
            records=[tuple(row[key] for key in columns) for row in copied])
        assert int((await s.scalar(identity())).rsplit(":", 1)[1]) == int(before.rsplit(":", 1)[1]) + 1
        await s.execute(text("DELETE FROM ai_proof_population"))
        assert await s.scalar(identity()) is None  # caller must fail closed
        await s.execute(insert(AiQueryProof).values(member()))
        assert await s.scalar(identity()) not in {None, before, initial, inserted}


async def test_population_atomic_snapshot_rollback_and_concurrent_writers(population):
    sessions = population
    async with sessions() as snapshot, snapshot.begin():
        await snapshot.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        before = await snapshot.scalar(identity())
        async with sessions() as writer, writer.begin():
            await writer.execute(insert(AiQueryProof).values(member()))
            assert await writer.scalar(identity()) != before
            assert await snapshot.scalar(identity()) == before
        assert await snapshot.scalar(identity()) == before
        assert not (await snapshot.execute(select(AiQueryProof))).all()
    async with sessions() as s:
        committed = await s.scalar(identity())
        await s.execute(insert(AiQueryProof).values(member()))
        await s.rollback()
        assert await s.scalar(identity()) == committed
    async def write():
        async with sessions() as s, s.begin():
            await s.execute(insert(AiQueryProof).values(member()))
    await asyncio.gather(*(write() for _ in range(8)))
    async with sessions() as s:
        assert int((await s.scalar(identity())).rsplit(":", 1)[1]) == int(committed.rsplit(":", 1)[1]) + 8
        assert len((await s.execute(select(AiQueryProof))).all()) == 9


@pytest.mark.parametrize("finish", ["commit", "rollback", "cancel", "sql_error", "timeout"])
async def test_jit_restored_on_same_pool_connection(pg, finish):
    sync, _ = pg
    engine = create_async_engine(sync.url.set(drivername="postgresql+asyncpg"), pool_size=1, max_overflow=0,
                                 connect_args={"server_settings": {"jit": "on"}})
    try:
        async with engine.connect() as c:
            pid = await c.scalar(text("SELECT pg_backend_pid()"))
            await c.rollback()
        async def query():
            async with engine.begin() as c:
                assert await c.scalar(text("SHOW jit")) == "on"
                await configure_ai_query(c)
                assert await c.scalar(text("SHOW jit")) == "off"
                assert await c.scalar(text("SELECT pg_backend_pid()")) == pid
                if finish == "cancel":
                    ready.set()
                    await asyncio.Event().wait()
                if finish == "rollback":
                    raise ValueError("rollback")
                if finish == "sql_error":
                    await c.execute(text("SELECT 1 / 0"))
                if finish == "timeout":
                    await c.execute(text("SET LOCAL statement_timeout = '20ms'"))
                    await c.execute(text("SELECT pg_sleep(1)"))
        ready = asyncio.Event()
        if finish == "cancel":
            task = asyncio.create_task(query())
            await asyncio.wait_for(ready.wait(), 5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        elif finish == "commit":
            await query()
        else:
            with pytest.raises(Exception, match="rollback|division by zero|statement timeout"):
                await query()
        async with engine.connect() as c:
            assert await c.scalar(text("SELECT pg_backend_pid()")) == pid
            assert await c.scalar(text("SHOW jit")) == "on"
    finally:
        await engine.dispose()
