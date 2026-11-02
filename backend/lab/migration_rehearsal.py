"""Bounded synthetic DDL rehearsal; new loopback DB only, retained as evidence.

250 listings + four genuine fact/proof fixtures, not production capacity evidence.
No production snapshot, providers, application DSN fallback or schema downgrade.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError


def run(args, *, env=None, cwd=None, success=True):
    result = subprocess.run(args, env=env, cwd=cwd, capture_output=True, text=True, timeout=90, check=False)
    if (result.returncode == 0) != success:
        raise RuntimeError("MIGRATION_REHEARSAL_COMMAND_FAILED")
    return result


def main():
    url = make_url(os.environ.get("AI_MIGRATION_REHEARSAL_DATABASE_URL", ""))
    if url.host not in {"localhost", "127.0.0.1"} or url.port != 55479 or url.database != "ttest_test":
        raise ValueError("EXPLICIT_DISPOSABLE_AUDIT_DATABASE_REQUIRED")
    root = Path(__file__).resolve().parents[2]
    name = "ai_quota_test_migration_" + uuid4().hex[:12]
    directory = root / "output" / name
    directory.mkdir()
    admin = create_engine(url.set(drivername="postgresql+psycopg"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    dsn = url.set(database=name)
    # Explicit process environment; no provider keys or evaluation journal.
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP") if key in os.environ}
    env.update(APP_ENV="test", DATABASE_URL=dsn.render_as_string(hide_password=False),
               JWT_SECRET="synthetic-migration-rehearsal-key-only", PYTHONUTF8="1", REDIS_URL="")
    backend = root / "backend"
    engine = create_engine(dsn.set(drivername="postgresql+psycopg"), pool_size=3, max_overflow=0)
    report = {"source": run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip(),
              "database": name, "synthetic_listings": 250, "cases": [], "production_sized": False}

    def passed(label, **fields):
        report["cases"].append({"name": label, "passed": True, **fields})
        print("PASS " + label, flush=True)

    def migrate(revision, *, success=True):
        return run([sys.executable, "-m", "alembic", "-x", "lock_timeout_ms=300", "-x",
                    "statement_timeout_ms=10000", "upgrade", revision], env=env, cwd=backend, success=success)

    try:
        migrate("0076_ai_fact_population")
        # Real legacy schema and constraints; clearly synthetic empty-data listings.
        seed = """import asyncio
from app.db.session import SessionLocal,engine
from app.models import User,Listing
from app.repositories.listings import point
async def seed():
 async with SessionLocal.begin() as s:
  u=User(email='migration@synthetic.example',password_hash='unused',name='Synthetic Host',role='host',initials='SH',email_verified=True)
  s.add(u);await s.flush()
  s.add_all([Listing(owner_user_id=u.id,title=f'Synthetic migration {i}',description='Synthetic only',city='Adeje',area='Synthetic',approximate_address='Synthetic',rental_mode='long',monthly_price=500,location=point(-16.7,28.1),status='published') for i in range(250)])
 await engine.dispose()
asyncio.run(seed())
"""
        run([sys.executable, "-c", seed], env=env, cwd=backend)
        with engine.begin() as writer:
            writer.execute(text("UPDATE listings SET title=title"))
            started = time.monotonic()
            failure = migrate("0077_ai_live_inputs", success=False)
            assert "lock timeout" in failure.stderr.lower()
            elapsed = time.monotonic() - started
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0076_ai_fact_population"
            assert conn.scalar(text("SELECT to_regclass('ai_live_input_versions')")) is None
        passed("0077 contended writer causes bounded abort and complete DDL rollback", wall_seconds=round(elapsed, 3))
        started = time.monotonic()
        migrate("0077_ai_live_inputs")
        passed("0077 succeeds on populated real schema after writer release", wall_seconds=round(time.monotonic()-started, 3))

        # Seed actual pre-0078 proofs with the exact historical binary, not fake signatures.
        old_sha = run(["git", "rev-parse", "a38a4f3d^"], cwd=root).stdout.strip()
        archive = directory / "old-runtime.tar"
        with archive.open("wb") as output:
            subprocess.run(["git", "archive", old_sha, "backend"], cwd=root, stdout=output, check=True, timeout=30)
        old = directory / "old-runtime"
        old.mkdir()
        with tarfile.open(archive) as source:
            source.extractall(old, filter="data")
        helper = """import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path('tests/integration').resolve()))
from test_ai_verified_cards import setup
from app.db.session import engine
async def seed():
 q,subject,sid,ids,_=await setup('long')
 print(json.dumps({'subject':subject.model_dump(mode='json'),'session':str(sid),'ids':[str(i) for i in ids]}))
 await engine.dispose()
asyncio.run(seed())
"""
        fixture = json.loads(run([sys.executable, "-c", helper], env=env, cwd=old / "backend").stdout.strip().splitlines()[-1])
        report["old_binary_source"] = old_sha
        with engine.connect() as conn:
            before = conn.scalar(text("SELECT count(*) FROM ai_query_proofs WHERE input_signature IS NOT NULL"))
            assert before == 4
        passed("historical 0077 binary prepares four genuine fact/proof fixtures")

        spec = importlib.util.spec_from_file_location("rehearsal_0078", backend / "alembic/versions/0078_ai_live_validity.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as migration:
            migration.execute(text("SET LOCAL lock_timeout='300ms'"))
            migration.execute(text("SET LOCAL statement_timeout='10s'"))
            started = time.monotonic()
            with Operations.context(MigrationContext.configure(migration)):
                module.upgrade()
            migration.execute(text("UPDATE alembic_version SET version_num='0078_ai_live_validity'"))
            with engine.connect() as writer:
                writer.execute(text("SET lock_timeout='300ms'"))
                try:
                    writer.execute(text("UPDATE ai_query_proofs SET signature=signature"))
                except DBAPIError as error:
                    assert getattr(error.orig, "sqlstate", None) == "55P03"
                    writer.rollback()
                else:
                    raise AssertionError("writer was not fenced by migration DDL")
        with engine.begin() as conn:
            conn.execute(text("UPDATE listings SET title=title"))
            assert conn.scalar(text("SELECT count(*) FROM ai_query_proofs WHERE input_status='legacy' AND input_signature IS NULL")) == 4
        passed("0078 locks cache writer, invalidates four old fast-path bindings, then releases writes",
               wall_seconds=round(time.monotonic()-started, 3))
        migrate("head")
        recovery = """import asyncio,json
from uuid import UUID
from sqlalchemy import select,text
from app.db.session import SessionLocal,engine
from app.repositories.ai_fact_pipeline import FactPipeline
from app.repositories.ai_query_proofs import QueryProofs
from app.repositories.ai_search_quota import QuotaLedger
from app.repositories.ai_search_sessions import SearchSessions,SessionPolicy,IntentVocabulary
from app.repositories.ai_verified_cards import VerifiedCardSearch
from app.schemas.ai_fact_pipeline import FactQueuePolicy
from app.schemas.ai_listing_facts import FactVocabulary
from app.schemas.ai_search_quota import LeasePolicy,QuotaSubject
from app.schemas.listings import ListingCardSearchRequest
data=json.loads(DATA)
async def check():
 v=FactVocabulary(amenity_codes=frozenset(),catalog_other_codes=frozenset(),tenant_group_codes=frozenset(),municipality_zones=frozenset())
 p=FactPipeline(SessionLocal,FactQueuePolicy(lease_seconds=60,max_attempts=2,retry_delay_seconds=1),v,resolver_version='test-cards.v1')
 if PREPARE:
  for lid in data['ids']: assert await QueryProofs(p).prepare(UUID(lid))
 sessions=SearchSessions(QuotaLedger(SessionLocal,LeasePolicy(reservation_seconds=60,running_seconds=60,recovery_grace_seconds=30)),SessionPolicy(inactivity_seconds=600),IntentVocabulary(frozenset(),frozenset(),frozenset()))
 q=VerifiedCardSearch(p,sessions,signing_key=b'synthetic-cards-key-not-a-secret32')
 result=await q.search_owned(QuotaSubject.model_validate_json(json.dumps(data['subject'])),UUID(data['session']),1,ListingCardSearchRequest(limit=6))
 assert result.cards.total==3
 await engine.dispose()
asyncio.run(check())
"""
        run([sys.executable, "-c", "DATA=" + repr(json.dumps(fixture)) + "\nPREPARE=True\n" + recovery], env=env, cwd=backend)
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM ai_query_proofs WHERE input_status='current'")) == 4
        passed("current binary reprepare restores four current proofs and three real SQL cards on 0079")
        run([sys.executable, "-c", "DATA=" + repr(json.dumps(fixture)) + "\nPREPARE=False\n" + recovery], env=env, cwd=old / "backend")
        passed("historical binary reads the same three cards on expand-only 0079, no downgrade")
        report["status"] = "PASS"
    finally:
        engine.dispose()
        (directory / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("Evidence: " + str(directory), flush=True)


if __name__ == "__main__":
    main()
