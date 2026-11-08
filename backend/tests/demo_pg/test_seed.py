"""Hard kill/resume on full migrated disposable PostGIS; no provider/key access."""
import asyncio
import hashlib
import json
import multiprocessing
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.ai_erasure_journal import ErasureJournal
from demo.budget import DemoBudget
from demo.entry import BINDING
from demo.seed_state import seed_catalog, validated_snapshot

pytestmark = pytest.mark.integration
BACKEND = Path(__file__).parents[2]


def snapshot():
    now = datetime.now(UTC).isoformat()
    records = []
    for i in range(12):
        price, lid, sid = 350 + i * 20, str(UUID(int=i + 1)), str(UUID(int=i + 101))
        normalized = {"source_name":"PisoCompartido", "source_price_text":f"{price} €/mes", "rental_mode":"long",
            "price_currency":"EUR", "price_period":"month", "price_is_from":False, "price_amount":price}
        records.append({"listing":{"id":lid,"title":f"Synthetic seed regression {i}","city":"Adeje","area":"Test",
            "rental_mode":"long","monthly_price":price,"primary_source":"PisoCompartido","is_external":True,
            "latitude":28.1+i*.001,"longitude":-16.7,"published_at":now},
            "source":{"id":sid,"source_name":"PisoCompartido","external_id":str(i),
                "source_url":f"https://www.pisocompartido.com/habitacion/{i}/","source_price_text":f"{price} €/mes",
                "current_status":"active","last_success_at":now,"last_checked_at":now,
                "content_updated_at":now,"last_state_check_at":now,"last_state_check_result":"active",
                "normalized_payload":normalized}})
    return {"snapshot_at":now,"records":records}


@pytest.fixture
def seed_database(tmp_path):
    raw = os.environ.get("AI_FACTS_TEST_DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.fail("explicit disposable loopback test database required")
    url = make_url(raw)
    if url.host not in {"127.0.0.1","localhost","::1"} or not (url.database == "ttest_test" or (url.database or "").startswith("ai_facts_test_")):
        pytest.fail("explicit disposable loopback facts database required")
    name = "ai_demo_seed_test_" + uuid4().hex
    admin = create_engine(url.set(drivername="postgresql+psycopg"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    dsn = url.set(drivername="postgresql+asyncpg", database=name).render_as_string(hide_password=False)
    try:
        env = dict(os.environ, DATABASE_URL=dsn, APP_ENV="test", REDIS_URL="", EXTERNAL_IMPORT_ENABLED="false",
                   EXTERNAL_REMOVAL_CHECK_ENABLED="false", JWT_SECRET="isolated-seed-regression-only-32-characters")
        migration = subprocess.run([sys.executable,"-m","alembic","upgrade","head"], cwd=BACKEND,
                                  env=env, capture_output=True, text=True, check=False)
        assert migration.returncode == 0, migration.stderr
        file = tmp_path / "snapshot.json"
        file.write_text(json.dumps(snapshot()))
        yield dsn, name, file, tmp_path / "state"
    finally:
        assert name.startswith("ai_demo_seed_test_") and len(name) == 50
        with admin.connect() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid<>pg_backend_pid()"), {"name":name})
            c.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


def worker(dsn, name, file, state, point, marker):
    async def execute():
        engine = create_async_engine(dsn, pool_size=2, max_overflow=0)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async def checkpoint(current):
            if current == point:
                Path(marker).write_text(current)
                while True:
                    await asyncio.sleep(10)
        try:
            result = await seed_catalog(engine, factory, json.loads(Path(file).read_text()), Path(state),
                lambda *, initialize: ErasureJournal(Path(state)/"erasure.sqlite3", b"s"*32, initialize=initialize),
                database_name=name, checkpoint=checkpoint)
            Path(marker).with_suffix(".done").write_text(json.dumps(result))
        finally:
            await engine.dispose()
    asyncio.run(execute())


def finish_process(process, timeout=40):
    process.join(timeout)
    if process.is_alive():
        process.kill()
        process.join(5)
        pytest.fail("bounded seed process did not finish")
    assert process.exitcode == 0


@pytest.mark.parametrize("point", ["starting","keys_ready","budget_ready","journal_bound","importing","imported","observed", "claimed",
                                   "facts_ready","proof_ready","proofs_ready","completed"])
def test_hard_kill_resumes_same_snapshot_keys_journals_and_twelve_proofs(seed_database, tmp_path, point):
    dsn, name, file, state = seed_database
    context = multiprocessing.get_context("spawn")
    marker = tmp_path / "checkpoint"
    process = context.Process(target=worker, args=(dsn,name,str(file),str(state),point,str(marker)))
    process.start()
    try:
        deadline = time.monotonic()+25
        while not marker.exists() and process.is_alive() and time.monotonic()<deadline:
            time.sleep(.02)
        assert marker.exists(), f"checkpoint {point} not reached; exit={process.exitcode}"
    finally:
        if process.is_alive():process.kill()
        process.join(5)
    before = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in state.iterdir()
              if p.name in {"signing.json","provider.sqlite3","erasure.sqlite3"}}
    resumed = context.Process(target=worker, args=(dsn,name,str(file),str(state),None,str(marker)))
    resumed.start()
    finish_process(resumed)
    assert json.loads(marker.with_suffix(".done").read_text())["prepared"] == 12
    for key, value in before.items():assert hashlib.sha256((state/key).read_bytes()).hexdigest() == value
    budget = DemoBudget(state/"provider.sqlite3", corpus_sha256=BINDING)
    assert budget.summary()["attempts"] == 0
    sync = create_engine(make_url(dsn).set(drivername="postgresql+psycopg"))
    try:
        with sync.connect() as c:
            for table, count in (("listings",12),("external_listing_sources",12),("ai_query_proofs",12),
                                 ("ai_listing_fact_batches",12),("ai_listing_facts",24)):
                assert c.scalar(text(f"SELECT count(*) FROM {table}")) == count
            assert c.scalar(text("SELECT phase FROM private_ai_demo_seed_state WHERE id=1")) == "completed"
        again = context.Process(target=worker, args=(dsn,name,str(file),str(state),None,str(marker)))
        again.start()
        finish_process(again)
        for key,value in before.items():assert hashlib.sha256((state/key).read_bytes()).hexdigest() == value
        assert budget.summary()["attempts"] == 0
    finally:
        sync.dispose()


async def test_resume_refuses_changed_snapshot_catalog_or_missing_bound_files(seed_database, tmp_path):
    dsn, name, file, state = seed_database
    engine = create_async_engine(dsn, pool_size=2, max_overflow=0)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    value = json.loads(file.read_text())
    async def seed(value):
        return await seed_catalog(engine, factory, value, state,
            lambda *, initialize: ErasureJournal(state/"erasure.sqlite3", b"s"*32, initialize=initialize),
            database_name=name)
    try:
        await seed(value)
        before = {p.name:p.read_bytes() for p in state.iterdir() if p.suffix in {".json", ".sqlite3"}}
        changed = json.loads(file.read_text())
        changed["records"][0]["listing"]["title"] = "Changed snapshot"
        with pytest.raises(ValueError, match="SNAPSHOT_BINDING_MISMATCH"):
            await seed(changed)
        async with factory.begin() as session:
            await session.execute(text("UPDATE listings SET title='Tampered' WHERE id=:id"),
                                  {"id":UUID(value["records"][0]["listing"]["id"])})
        with pytest.raises(ValueError, match="CATALOG_MISMATCH"):
            await seed(value)
        async with factory.begin() as session:
            await session.execute(text("UPDATE listings SET title=:title WHERE id=:id"),
                {"id":UUID(value["records"][0]["listing"]["id"]), "title":value["records"][0]["listing"]["title"]})
        for filename in ("signing.json", "provider.sqlite3", "erasure.sqlite3"):
            path = state/filename
            path.unlink()
            with pytest.raises((ValueError, OSError)):
                await seed(value)
            assert not path.exists(), "lost bound files must never be regenerated"
            path.write_bytes(before[filename])
        await seed(value)
        assert {p.name:p.read_bytes() for p in state.iterdir() if p.name in before} == before
    finally:
        await engine.dispose()


@pytest.mark.parametrize("fault", ["duplicate_listing", "duplicate_source", "bad_price", "private_field", "bad_position", "naive_time"])
def test_malformed_snapshot_rejected_before_state_creation(fault):
    value = snapshot()
    first, second = value["records"][:2]
    if fault == "duplicate_listing":second["listing"]["id"] = first["listing"]["id"]
    if fault == "duplicate_source":second["source"]["id"] = first["source"]["id"]
    if fault == "bad_price":first["listing"]["monthly_price"] += 1
    if fault == "private_field":first["listing"]["contact_email"] = "private@example.invalid"
    if fault == "bad_position":first["listing"]["latitude"] = 999
    if fault == "naive_time":value["snapshot_at"] = "2026-11-08T01:00:00"
    with pytest.raises(ValueError):validated_snapshot(value)
