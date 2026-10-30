"""Tiny PostgreSQL evidence/cancellation regressions, never a capacity run."""
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.integration


def benchmark():
    path = Path(__file__).parents[3] / "scripts/benchmark-ai-map.py"
    spec = importlib.util.spec_from_file_location("map_lab_pg", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.mark.parametrize("damage", [None, "entities", "listings", "listing_room_details",
    "external_listing_sources", "ai_fact_catalogs", "ai_listing_fact_batches", "ai_fact_sources",
    "ai_listing_facts", "ai_listing_search_features", "ai_query_proofs", "profile", "trigger", "generation"])
async def test_exact_dataset_validation_on_postgres(pg, tmp_path, monkeypatch, damage):
    bench = benchmark()
    db = pg[1].kw["bind"]
    provenance = {"sources":2, "experiment_id":"a"*32}
    monkeypatch.setattr(bench, "PROVENANCE", provenance)
    monkeypatch.setattr(bench, "OUT", tmp_path)
    counts = {model.__tablename__:4*(20 if model is bench.AiListingFact else 2 if model in (
        bench.ExternalListingSource,bench.AiFactSource,bench.AiListingFactBatch) else 1) for model in (
            bench.Listing,bench.ListingRoomDetails,bench.ExternalListingSource,bench.AiFactCatalog,
            bench.AiListingFactBatch,bench.AiFactSource,bench.AiListingFact,bench.AiListingSearchFeatures,bench.AiQueryProof)}
    async with db.begin() as c:
        for table, count in counts.items():
            # Identifiers come only from the fixed model list above.
            await c.execute(text(f"CREATE TABLE {table} (id int, source_name text)"))
            await c.execute(text(f"INSERT INTO {table} SELECT g, 'synth-' || (g%5)::text FROM generate_series(1,:n) g"), {"n":count})
        await c.execute(text("CREATE TABLE r01_entities AS SELECT generate_series(1,3) AS n"))
        await c.execute(text("CREATE TABLE r01_meta (data jsonb)"))
        await c.execute(text("INSERT INTO r01_meta VALUES (CAST(:v AS jsonb))"), {"v":json.dumps({
            "synthetic_only":True,"sources":10 if damage == "profile" else 2,"provenance":provenance,"generation":2 if damage == "generation" else 1})})
        await c.execute(text("CREATE FUNCTION lab_noop() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$"))
        await c.execute(text("CREATE TRIGGER listings_catalog_version BEFORE INSERT ON listings FOR EACH ROW EXECUTE FUNCTION lab_noop()"))
        if damage == "trigger":
            await c.execute(text("ALTER TABLE listings DISABLE TRIGGER listings_catalog_version"))
        elif damage == "entities":
            await c.execute(text("DELETE FROM r01_entities WHERE n=3"))
        elif damage in counts:
            await c.execute(text(f"DELETE FROM {damage} WHERE id=1"))
    (tmp_path / "template.json").write_text(json.dumps({"sources":2,"observations":20,"provenance":provenance}))
    (tmp_path / "dataset-3.json").write_text(json.dumps({"listings":3,"source_records_per_listing":2,
        "observations_per_listing":20,"counts_including_template":counts,"distinct_providers":5,"provenance":provenance,"seed_generation":1}))
    async with db.connect() as c:
        await c.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        if damage is None:
            await bench.validate_dataset(c,3)
        else:
            with pytest.raises(RuntimeError,match="dataset|trigger"):
                await bench.validate_dataset(c,3)


async def test_twenty_server_active_queries_are_actually_cancelled_and_pool_reused(pg):
    bench = benchmark()
    db = create_async_engine(pg[1].kw["bind"].url, pool_size=30, max_overflow=0)
    factory = async_sessionmaker(db)
    async def request(_):
        async with factory() as session:
            return {"ok":await session.scalar(text("SELECT 42")) == 42}
    try:
        result = await bench.cancellation_check(db,factory,request,3)
        assert all(result[key] == 20 for key in ("tasks","active_before_cancel","cancel_requested","cancel_accepted","cancelled"))
        assert result["failed"] == result["remaining_active"] == result["completed_before_cancel"] == 0
        assert result["pool_reusable"] is True
    finally:
        await db.dispose()


@pytest.mark.parametrize("other_phase", ["seed","measure"])
async def test_database_excludes_simultaneous_phases_even_with_different_outputs(pg, other_phase):
    bench = benchmark()
    db = pg[1].kw["bind"]
    async with bench.phase_database_guard(db,"seed",3):
        with pytest.raises(RuntimeError,match="another synthetic"):
            async with bench.phase_database_guard(db,other_phase,3):
                pytest.fail("concurrent phase entered")
    async with bench.phase_database_guard(db,"seed",3):
        pass


@pytest.mark.parametrize("failure", [False,True])
async def test_measurement_freeze_blocks_writes_and_ddl_and_releases_on_exit(pg,tmp_path,monkeypatch,failure):
    bench = benchmark()
    db = pg[1].kw["bind"]
    provenance = {"experiment_id":"a"*32}
    monkeypatch.setattr(bench,"PROVENANCE",provenance)
    monkeypatch.setattr(bench,"RUN_ID","b"*32)
    monkeypatch.setattr(bench,"OUT",tmp_path)
    async with db.begin() as c:
        await c.execute(text("CREATE TABLE freeze_fixture (id int)"))
        await c.execute(text("INSERT INTO freeze_fixture VALUES (1)"))
        await c.execute(text("CREATE TABLE r01_meta (data jsonb)"))
        await c.execute(text("INSERT INTO r01_meta VALUES (CAST(:v AS jsonb))"),{"v":json.dumps({"provenance":provenance,"generation":1})})
    async def guarded():
        async with bench.phase_database_guard(db,"measure",3):
            for sql in ("INSERT INTO freeze_fixture VALUES (2)","UPDATE r01_meta SET data=data",
                        "TRUNCATE freeze_fixture","ALTER TABLE freeze_fixture ADD COLUMN n int"):
                async with db.connect() as c:
                    await c.execute(text("SET lock_timeout='100ms'"))
                    with pytest.raises(DBAPIError) as error:
                        await c.execute(text(sql))
                    assert error.value.orig.sqlstate == "55P03"
            async with db.connect() as c:
                assert await c.scalar(text("SELECT count(*) FROM freeze_fixture")) == 1
            if failure:
                raise RuntimeError("synthetic interrupted measurement")
    if failure:
        with pytest.raises(RuntimeError,match="interrupted"):
            await guarded()
    else:
        await guarded()
    value = json.loads(next(tmp_path.glob("dataset-stability-*.json")).read_text())
    assert value["stable"] is (not failure) and value["write_frozen"]
    async with db.begin() as c:
        await c.execute(text("INSERT INTO freeze_fixture VALUES (2)"))


async def test_seed_vacuum_waits_for_maintenance_lock_and_restores_query_timeout(pg):
    bench = benchmark()
    db = pg[1].kw["bind"]
    async with db.begin() as connection:
        await connection.execute(text("CREATE TABLE seed_vacuum_fixture (id int)"))
    async with db.connect() as blocker, db.connect() as maintenance:
        await blocker.execute(text("LOCK TABLE seed_vacuum_fixture IN SHARE UPDATE EXCLUSIVE MODE"))
        await maintenance.execution_options(isolation_level="AUTOCOMMIT")
        await maintenance.execute(text("SET lock_timeout='1000ms'"))
        pid = await maintenance.scalar(text("SELECT pg_backend_pid()"))
        task = asyncio.create_task(bench.vacuum_seed_database(maintenance))
        try:
            for _ in range(200):
                async with db.connect() as observer:
                    blocked = await observer.scalar(text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid})
                if blocked:
                    break
                await asyncio.sleep(0.01)
            assert blocked, "VACUUM never reached the held maintenance lock"
            await asyncio.sleep(1.2)
            assert not task.done(), "setup inherited the measured-query lock timeout"
        finally:
            await blocker.rollback()
            await task
        assert await maintenance.scalar(text("SHOW lock_timeout")) == "1s"


async def test_seed_vacuum_restores_timeout_after_statement_failure(pg):
    bench = benchmark()
    db = pg[1].kw["bind"]
    async with db.begin() as connection:
        await connection.execute(text("CREATE TABLE seed_vacuum_failure_fixture (id int)"))
    async with db.begin() as blocker, db.connect() as maintenance:
        await blocker.execute(text("LOCK TABLE seed_vacuum_failure_fixture IN SHARE UPDATE EXCLUSIVE MODE"))
        await maintenance.execution_options(isolation_level="AUTOCOMMIT")
        await maintenance.execute(text("SET lock_timeout='1000ms'"))
        await maintenance.execute(text("SET statement_timeout='100ms'"))
        with pytest.raises(DBAPIError) as error:
            await bench.vacuum_seed_database(maintenance)
        assert error.value.orig.sqlstate == "57014"
        assert await maintenance.scalar(text("SHOW lock_timeout")) == "1s"


@pytest.mark.parametrize("failure", [False, True])
async def test_initialize_guard_allows_concurrent_index_and_releases_session_lock(pg, failure):
    bench = benchmark()
    db = pg[1].kw["bind"]
    async with db.begin() as connection:
        await connection.execute(text("CREATE TABLE initialize_index_fixture (id int)"))
    async def initialize():
        async with bench.phase_database_guard(db, "initialize", 3):
            async with db.connect() as connection:
                await connection.execution_options(isolation_level="AUTOCOMMIT")
                await connection.execute(text("SET statement_timeout='2000ms'"))
                await connection.execute(text("CREATE INDEX CONCURRENTLY initialize_fixture_index ON initialize_index_fixture(id)"))
            with pytest.raises(RuntimeError, match="another synthetic"):
                async with bench.phase_database_guard(db, "seed", 3):
                    pytest.fail("initializer did not exclude concurrent phases")
            if failure:
                raise RuntimeError("synthetic initialization failure")
    if failure:
        with pytest.raises(RuntimeError, match="synthetic initialization failure"):
            await initialize()
    else:
        await initialize()
    async with bench.phase_database_guard(db, "seed", 3):
        pass


async def test_capture_keeps_ctes_comments_and_explicit_control_and_explains_every_query(pg):
    bench = benchmark()
    db = pg[1].kw["bind"]
    captured = []
    def capture(conn,cursor,statement,parameters,context,executemany):
        captured.append(bench.capture_statement(context,statement,parameters))
    event.listen(db.sync_engine,"before_cursor_execute",capture)
    try:
        async with db.connect() as c:
            await c.execute(text("SET TRANSACTION READ ONLY").execution_options(r01_control=True))
            await c.execute(text("WITH fixture AS (SELECT 1 AS n) SELECT n FROM fixture"))
            await c.execute(text("/* synthetic query comment */ SELECT 2"))
    finally:
        event.remove(db.sync_engine,"before_cursor_execute",capture)
    assert [row["category"] for row in captured] == ["transaction-control","map-query","map-query"]
    for row in captured[1:]:
        plan = await bench.explain_statement(db,row["sql"],row["parameters"])
        assert plan["status"] == "actual" and plan["plan"][0]["Plan"]
