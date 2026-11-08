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


async def test_explicit_unknown_fields_remain_null_and_resume_with_pilot_budget(seed_database):
    from pilot.budget import PilotBudget
    dsn, name, file, state = seed_database
    engine = create_async_engine(dsn, pool_size=2, max_overflow=0)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    value = json.loads(file.read_text())
    fields = ("furnished", "room_capacity", "room_size_m2", "bills_included", "bathroom", "kitchen", "pets_allowed", "smoking_allowed", "children_allowed")
    for record in value["records"]:
        record["listing"].update({key: None for key in fields})
    try:
        async def seed():
            return await seed_catalog(engine, factory, value, state,
                lambda *, initialize: ErasureJournal(state/"erasure.sqlite3", b"s"*32, initialize=initialize),
                database_name=name, budget_factory=PilotBudget)
        assert (await seed())["prepared"] == 12
        async with factory() as session:
            rows = (await session.execute(text("SELECT " + ",".join(fields) + " FROM listings"))).all()
            assert len(rows) == 12 and all(all(v is None for v in row) for row in rows)
        before = {p.name:p.read_bytes() for p in state.iterdir()}
        assert (await seed())["prepared"] == 12
        assert before == {p.name:p.read_bytes() for p in state.iterdir()}
        assert PilotBudget(state/"provider.sqlite3").summary()["attempts"] == 0
    finally:
        await engine.dispose()


async def test_pilot_readiness_expires_without_provider_reserve_or_quota(seed_database, monkeypatch):
    from app.repositories.ai_verified_cards import SourceCoverageUnavailable
    from app.schemas.ai_search_intent import Criteria, SearchIntent
    from demo.entry import pipeline
    from pilot.budget import PilotBudget
    from pilot.entry import PilotParser
    from pilot.readiness import CatalogReadiness
    dsn, name, file, state = seed_database
    engine = create_async_engine(dsn, pool_size=2, max_overflow=0)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await seed_catalog(engine, factory, json.loads(file.read_text()), state,
            lambda *, initialize: ErasureJournal(state/"erasure.sqlite3", b"s"*32, initialize=initialize),
            database_name=name, budget_factory=PilotBudget)
        ready = CatalogReadiness(pipeline(factory))
        assert (await ready())["catalog_ready"]
        async with factory.begin() as session:
            await session.execute(text("UPDATE external_listing_sources SET last_success_at=statement_timestamp()-interval '86401 seconds'"))
        assert not (await ready())["catalog_ready"]
        budget = PilotBudget(state/"provider.sqlite3")
        current = SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1", session_id=uuid4(), version=0,
            criteria=Criteria.model_validate({"rental_mode":{"strength":"hard","value":"long"}}))
        with pytest.raises(SourceCoverageUnavailable):
            await PilotParser(budget, ready).parse("до 600 евро в месяц", current)
        assert budget.summary()["attempts"] == 0
        from app.repositories.ai_search_quota import QuotaLedger
        from app.repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
        from app.repositories.ai_verified_cards import VerifiedCardSearch
        from app.schemas.ai_search_intent import SessionCreate
        from app.schemas.ai_search_quota import LeasePolicy, QuotaOperation, QuotaSubject
        from app.schemas.listings import ListingCardSearchRequest
        from app.services.ai_search_execution import TextSearchExecution
        class Gate:
            async def check(self, subject): pass
        sessions = SearchSessions(QuotaLedger(factory, LeasePolicy(reservation_seconds=60,running_seconds=60,recovery_grace_seconds=30)),
            SessionPolicy(inactivity_seconds=86400), IntentVocabulary(frozenset(),frozenset(),frozenset()))
        owner = QuotaSubject(kind="guest",id=uuid4())
        owned = await sessions.create(owner, SessionCreate(rental_mode="long"))
        utterance = "до 600 евро в месяц"
        op = QuotaOperation(idempotency_key=uuid4(),channel="text",payload_sha256=hashlib.sha256(utterance.encode()).hexdigest(),
            session_id=owned.intent.session_id,expected_session_version=0)
        execution = TextSearchExecution(sessions,PilotParser(budget,ready),Gate(),VerifiedCardSearch(pipeline(factory),sessions,signing_key=b"q"*32))
        result = await execution.execute(owner,op,utterance,ListingCardSearchRequest())
        assert result.operation.status == "failed" and result.operation.failure_code == "SOURCE_COVERAGE_UNAVAILABLE"
        assert budget.summary()["attempts"] == 0
        async with factory() as session:
            assert await session.scalar(text("SELECT coalesce(sum(used+reserved),0) FROM ai_usage_days")) == 0
    finally:
        await engine.dispose()


async def test_export_selects_consistent_source_even_when_newer_price_differs(seed_database):
    import importlib.util

    from app.models import ExternalListingSource
    dsn, name, file, state = seed_database
    engine = create_async_engine(dsn, pool_size=2, max_overflow=0)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    value = json.loads(file.read_text())
    for record in value["records"]:
        record["listing"].update(primary_source_url=record["source"]["source_url"], source_price_text=record["source"]["source_price_text"])
    spec = importlib.util.spec_from_file_location("export_public", BACKEND.parent/"deploy/ai-text-demo/export_public.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        await seed_catalog(engine, factory, value, state,
            lambda *, initialize: ErasureJournal(state/"erasure.sqlite3", b"s"*32, initialize=initialize), database_name=name)
        original = UUID(value["records"][0]["source"]["id"])
        lid = UUID(value["records"][0]["listing"]["id"])
        async with factory.begin() as session:
            source = await session.get(ExternalListingSource, original)
            fields = {c.name:getattr(source, c.name) for c in ExternalListingSource.__table__.columns if c.name not in {"id", "external_id", "last_success_at", "normalized_payload"}}
            fields.update(source_url=source.source_url+"new/",source_price_text="999 €/mes")
            changed = dict(source.normalized_payload, price_amount=999,source_price_text="999 €/mes")
            session.add(ExternalListingSource(id=uuid4(), external_id="different-newer-price", last_success_at=datetime.now(UTC), normalized_payload=changed, **fields))
        async with factory() as session:
            query = "SELECT s.id FROM listings l " + module.consistent_source_join() + " WHERE l.id=:lid"
            assert await session.scalar(text(query), {"lid":lid}) == original
        async with factory.begin() as session:
            await session.execute(text("UPDATE listings SET primary_source_url=primary_source_url || 'new/' WHERE id=:lid"),{"lid":lid})
        async with factory() as session:
            assert await session.scalar(text(query), {"lid":lid}) is None  # Explicit null -> exporter refuses, never overwrites price.
    finally:
        await engine.dispose()


async def test_minimal_pilot_asgi_real_pg_mock_provider_replay_refine_and_expiry(seed_database, monkeypatch):
    import httpx

    from app.api.v1.ai_search import AISearchRuntime
    from app.repositories.ai_search_quota import QuotaLedger
    from app.repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
    from app.repositories.ai_verified_cards import VerifiedCardSearch
    from app.schemas.ai_search_quota import LeasePolicy
    from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
    from app.services.ai_http_policy import AIHTTPPolicy
    from app.services.ai_search_execution import TextSearchExecution
    from demo.entry import pipeline
    from pilot import entry
    from pilot.budget import BINDING as PILOT_BINDING
    from pilot.budget import PilotBudget
    from pilot.readiness import CatalogReadiness
    from pilot.surface import minimal_app
    dsn, name, file, state = seed_database
    engine = create_async_engine(dsn,pool_size=2,max_overflow=0)
    factory = async_sessionmaker(engine,expire_on_commit=False)
    try:
        await seed_catalog(engine,factory,json.loads(file.read_text()),state,
            lambda *,initialize:ErasureJournal(state/"erasure.sqlite3",b"s"*32,initialize=initialize),database_name=name,budget_factory=PilotBudget)
        control=state/"control"
        control.mkdir()
        (control/"approval.json").write_text(json.dumps({"binding":PILOT_BINDING,"owner_approved":True,"max_calls":50,"max_micro_usd":1000000,"scope":"owner-team-nonpersonal-positive-rent-grammar.v1"}))
        (control/"deepseek.env").write_text("AI_INTENT_EVAL_DEEPSEEK_KEY=fixture-not-a-real-key\n")
        monkeypatch.setattr(entry,"CONTROL",control)
        requests=[]
        def completion(request):
            requests.append(request)
            message=json.loads(json.loads(request.content)["messages"][1]["content"])
            amount=message["text"].split()[5]
            decision={"status":"patch","patch":{"set":{"budget":{"strength":"hard","value":{"amount":amount,"currency":"EUR","period":"monthly"}}},"remove":[]}}
            return httpx.Response(200,json={"usage":{"prompt_tokens":10,"completion_tokens":1,"total_tokens":11},"choices":[{"finish_reason":"stop","message":{"role":"assistant","content":json.dumps(decision)}}]})
        monkeypatch.setattr(httpx,"AsyncHTTPTransport",lambda **_kwargs:httpx.MockTransport(completion))
        budget=PilotBudget(state/"provider.sqlite3")
        budget.dispatch_guard=entry.require_approval
        facts=pipeline(factory)
        sessions=SearchSessions(QuotaLedger(factory,LeasePolicy(reservation_seconds=60,running_seconds=60,recovery_grace_seconds=30)),SessionPolicy(inactivity_seconds=86400),IntentVocabulary(frozenset(),frozenset(),frozenset()))
        cards=VerifiedCardSearch(facts,sessions,signing_key=b"q"*32)
        class Gate:
            async def check(self, _value): pass
        execution=TextSearchExecution(sessions,entry.PilotParser(budget,CatalogReadiness(facts)),Gate(),cards)
        app=minimal_app()
        app.state.ai_search_runtime=AISearchRuntime(sessions,cards,execution,GuestTokens(key=b"g"*32,policy=GuestPolicy(ttl_seconds=3600)),Gate(),frozenset({entry.ORIGIN}),32768,AIHTTPPolicy(20,3,(),entry.ORIGIN))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url=entry.ORIGIN,headers={"Origin":entry.ORIGIN,"X-AI-Request":"1"}) as client:
            base="/api/v1/ai-search"
            assert (await client.post("/api/v1/auth/register",json={})).status_code==404
            cookie=await client.post(base+"/identity")
            assert cookie.status_code==200 and "Secure" in cookie.headers["set-cookie"]
            created=await client.post(base+"/sessions",json={"idempotency_key":str(uuid4()),"rental_mode":"long"})
            assert created.status_code==200,created.text
            sid=created.json()["intent"]["session_id"]
            def message(version,amount):return {"idempotency_key":str(uuid4()),"session_id":sid,"expected_version":version,"text":f"до {amount} евро в месяц","search":{"limit":6}}
            first=message(0,600)
            response=await client.post(base+"/query",json=first)
            assert response.status_code==200,response.text
            answer=response.json()
            assert answer["operation"]["status"]=="succeeded" and answer["operation"]["receipt"]["count"]==12,answer
            replay=(await client.post(base+"/query",json=first)).json()
            assert replay["operation"]["receipt"]==answer["operation"]["receipt"] and len(requests)==1
            refined=(await client.post(base+"/query",json=message(1,400))).json()
            assert refined["operation"]["receipt"]["count"]==3 and len(requests)==2
            ref=refined["operation"]["receipt"]["result_ref"]
            metadata=(await client.get(base+"/results/"+ref)).json()
            assert metadata["intent"]["version"]==2 and metadata["count"]==3
            mapped=await client.post(base+"/results/"+ref+"/map",json={"search":{"north":29,"south":27,"east":-16,"west":-18,"zoom":14}})
            assert mapped.status_code==200 and mapped.json()["map"]["items"]
            async with factory.begin() as connection:
                await connection.execute(text("UPDATE external_listing_sources SET last_success_at=statement_timestamp()-interval '86401 seconds'"))
            stale=(await client.post(base+"/query",json=message(2,500))).json()
            assert stale["operation"]["failure_code"]=="SOURCE_COVERAGE_UNAVAILABLE",stale
            assert len(requests)==2 and budget.summary()["attempts"]==2
            assert (await client.get(base+"/quota")).json()["remaining"]==1
            assert (await client.get(base+"/results/"+ref)).json()["count"]==3
    finally:
        await engine.dispose()
