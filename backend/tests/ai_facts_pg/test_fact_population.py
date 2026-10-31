"""Bounded real PostgreSQL correctness and plan checks, never capacity acceptance."""
import asyncio
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, insert, select, text, update

from app.models.ai_fact_pipeline import AiFactCatalog
from app.repositories.ai_fact_population import fact_population_signature

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def population(pipeline):
    _, sessions = pipeline
    async with sessions() as session, session.begin():
        # Migration must also work over an existing, nonempty catalog.
        await session.execute(insert(AiFactCatalog).values(canonical_listing_id=uuid4(), revision=7))

        def migrate(connection):
            path = Path(__file__).parents[2] / "alembic/versions/0076_ai_fact_population.py"
            spec = importlib.util.spec_from_file_location("fact_population_migration", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                module.downgrade()  # expand-only binary rollback preserves state
        await (await session.connection()).run_sync(migrate)
        assert await session.scalar(select(func.sum(AiFactCatalog.revision))) == 7
        assert await session.scalar(identity()) is not None
        await session.execute(text("DELETE FROM ai_fact_catalogs"))
    return sessions


def identity():
    return select(fact_population_signature())


def member(revision=1):
    return {"canonical_listing_id": uuid4(), "revision": revision}


def generation(value):
    return int(value.rsplit(":", 1)[1])


async def test_bulk_copy_upserts_noops_remap_delete_and_truncate(population):
    sessions = population
    async with sessions() as s, s.begin():
        initial = await s.scalar(identity())
        rows = [member() for _ in range(8)]
        await s.execute(insert(AiFactCatalog).values(rows))
        inserted = await s.scalar(identity())
        assert generation(inserted) == generation(initial) + 1
        await s.execute(text("UPDATE ai_fact_catalogs SET revision=revision"))
        await s.execute(text("UPDATE ai_fact_catalogs SET revision=99 WHERE false"))
        await s.execute(text("DELETE FROM ai_fact_catalogs WHERE false"))
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(AiFactCatalog).values(rows[0])
        await s.execute(stmt.on_conflict_do_nothing())
        await s.execute(stmt.on_conflict_do_update(index_elements=[AiFactCatalog.canonical_listing_id],
                                                  set_={"revision": stmt.excluded.revision}))
        assert await s.scalar(identity()) == inserted
        await s.execute(stmt.on_conflict_do_update(index_elements=[AiFactCatalog.canonical_listing_id],
                                                  set_={"revision": 2}))
        assert generation(await s.scalar(identity())) == generation(inserted) + 1
        before = await s.scalar(identity())
        await s.execute(update(AiFactCatalog).where(AiFactCatalog.canonical_listing_id == rows[0]["canonical_listing_id"])
                        .values(canonical_listing_id=uuid4()))
        assert generation(await s.scalar(identity())) == generation(before) + 1
        before = await s.scalar(identity())
        await s.execute(text("DELETE FROM ai_fact_catalogs"))
        assert generation(await s.scalar(identity())) == generation(before) + 1
        before = await s.scalar(identity())
        raw = await (await s.connection()).get_raw_connection()
        copied = [member() for _ in range(8)]
        await raw.driver_connection.copy_records_to_table("ai_fact_catalogs",
            columns=["canonical_listing_id", "revision"],
            records=[(row["canonical_listing_id"], row["revision"]) for row in copied])
        assert generation(await s.scalar(identity())) == generation(before) + 1
        before = await s.scalar(identity())
        await s.execute(text("TRUNCATE ai_fact_catalogs CASCADE"))
        assert generation(await s.scalar(identity())) == generation(before) + 1


async def test_same_count_sum_swaps_and_restored_values_cannot_revive_cursor(population):
    async with population() as s, s.begin():
        rows = [member(1), member(2)]
        await s.execute(insert(AiFactCatalog).values(rows))
        before = await s.scalar(identity())
        legacy = select(func.count(), func.sum(AiFactCatalog.revision))
        original = (await s.execute(legacy)).one()
        await s.execute(text("UPDATE ai_fact_catalogs SET revision=3-revision"))
        assert (await s.execute(legacy)).one() == original
        changed = await s.scalar(identity())
        assert changed != before
        await s.execute(text("UPDATE ai_fact_catalogs SET revision=3-revision"))
        assert (await s.execute(legacy)).one() == original
        assert await s.scalar(identity()) not in {before, changed}


async def test_snapshot_rollback_savepoint_cas_and_concurrent_writers(population):
    sessions = population
    row = member()
    async with sessions() as writer, writer.begin():
        await writer.execute(insert(AiFactCatalog).values(row))
    async with sessions() as snapshot, snapshot.begin():
        await snapshot.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        before = await snapshot.scalar(identity())
        async with sessions() as writer, writer.begin():
            await writer.execute(update(AiFactCatalog).values(revision=2))
            assert await writer.scalar(identity()) != before
            assert await snapshot.scalar(identity()) == before
        assert await snapshot.scalar(identity()) == before
        assert await snapshot.scalar(select(AiFactCatalog.revision)) == 1
    async with sessions() as s:
        committed = await s.scalar(identity())
        await s.execute(update(AiFactCatalog).values(revision=3))
        await s.rollback()
        assert await s.scalar(identity()) == committed
        async with s.begin_nested() as savepoint:
            await s.execute(update(AiFactCatalog).values(revision=4))
            assert await s.scalar(identity()) != committed
            await savepoint.rollback()
        assert await s.scalar(identity()) == committed
        # Failed CAS must not change cursor context.
        await s.execute(update(AiFactCatalog).where(AiFactCatalog.revision == 99).values(revision=5))
        await s.commit()
        assert await s.scalar(identity()) == committed
    async def write():
        async with sessions() as s, s.begin():
            await s.execute(update(AiFactCatalog).where(AiFactCatalog.canonical_listing_id == row["canonical_listing_id"])
                            .values(revision=AiFactCatalog.revision + 1))
    await asyncio.gather(*(write() for _ in range(8)))
    async with sessions() as s:
        assert generation(await s.scalar(identity())) == generation(committed) + 8
        assert await s.scalar(select(AiFactCatalog.revision)) == 10


async def test_missing_state_and_recreation_use_fresh_epoch(population):
    async with population() as s, s.begin():
        original = await s.scalar(identity())
        await s.execute(text("DELETE FROM ai_fact_population"))
        assert await s.scalar(identity()) is None  # repository refuses this state
        await s.execute(insert(AiFactCatalog).values(member()))
        recreated = await s.scalar(identity())
        assert recreated is not None and recreated.split(":")[1] != original.split(":")[1]
        await s.execute(text("TRUNCATE ai_fact_population"))
        assert await s.scalar(identity()) is None
        await s.execute(text("TRUNCATE ai_fact_catalogs CASCADE"))
        assert await s.scalar(identity()) not in {None, original, recreated}


async def test_identity_reads_one_state_row_without_catalog_aggregate(population):
    async with population() as s, s.begin():
        await s.execute(text("INSERT INTO ai_fact_catalogs SELECT gen_random_uuid(), g FROM generate_series(1,4096) g"))
        await s.execute(text("ANALYZE ai_fact_catalogs"))
        await s.execute(text("ANALYZE ai_fact_population"))
        legacy = select(func.count(), func.coalesce(func.sum(AiFactCatalog.revision), 0))
        plans = {}
        for name, statement in (("legacy_count_sum", legacy), ("population_identity", identity())):
            sql = str(statement.compile(dialect=s.bind.dialect, compile_kwargs={"literal_binds": True}))
            plans[name] = await s.scalar(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql))
        def nodes(plan):
            yield plan
            for child in plan.get("Plans", []):
                yield from nodes(child)
        old_nodes = list(nodes(plans["legacy_count_sum"][0]["Plan"]))
        new_nodes = list(nodes(plans["population_identity"][0]["Plan"]))
        assert sum(n["Actual Rows"] * n["Actual Loops"] for n in old_nodes
                   if n.get("Relation Name") == "ai_fact_catalogs") == 4096
        assert not any(n.get("Relation Name") == "ai_fact_catalogs" or n["Node Type"] == "Aggregate" for n in new_nodes)
        assert sum(n["Actual Rows"] * n["Actual Loops"] for n in new_nodes
                   if n.get("Relation Name") == "ai_fact_population") == 1
        print("FACT_POPULATION_BOUNDED_PLAN=" + json.dumps({"rows": 4096, "capacity_acceptance": False, "plans": plans}))
