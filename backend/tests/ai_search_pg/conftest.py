"""Isolated schemas for real AI quota/session migrations, never an application DSN."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.repositories.ai_search_quota import QuotaLedger
from app.repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
from app.schemas.ai_search_quota import LeasePolicy


@pytest_asyncio.fixture
async def pg():
    value = os.getenv("AI_QUOTA_TEST_DATABASE_URL") or os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.fail("set AI_QUOTA_TEST_DATABASE_URL to a disposable loopback ai_quota_test_* database")
    url = make_url(value)
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not (
        (url.database or "").startswith("ai_quota_test_") or url.database == "ttest_test"
    ):
        pytest.fail("AI tests require a disposable loopback test database")
    schema = "ai_quota_" + uuid4().hex
    admin = create_async_engine(url.set(drivername="postgresql+asyncpg"))
    async with admin.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        url.set(drivername="postgresql+asyncpg"),
        pool_size=16,
        max_overflow=0,
        connect_args={
            "server_settings": {
                "search_path": schema,
                "lock_timeout": "5000",
                "statement_timeout": "10000",
            }
        },
    )
    try:
        async with engine.begin() as conn:

            def migrate(sync):
                for filename in ("0067_ai_search_quota.py", "0068_ai_search_sessions.py", "0072_ai_session_commands.py"):
                    path = Path(__file__).parents[2] / "alembic/versions" / filename
                    spec = importlib.util.spec_from_file_location("ai_migration", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    with Operations.context(MigrationContext.configure(sync)):
                        module.upgrade()

            await conn.run_sync(migrate)
            # Existing AI-07 seam tests keep their clearly synthetic stand-ins.
            await conn.execute(
                text(
                    "CREATE TABLE session_fixture (id uuid PRIMARY KEY, owner uuid NOT NULL, version integer NOT NULL)"
                )
            )
            await conn.execute(text("CREATE TABLE result_fixture (id uuid PRIMARY KEY, count integer NOT NULL)"))
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        policy = LeasePolicy(reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30)
        yield QuotaLedger(sessions, policy), sessions
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


@pytest.fixture
def store(pg):
    return SearchSessions(
        pg[0],
        SessionPolicy(inactivity_seconds=3600),
        IntentVocabulary(
            frozenset({"wifi", "elevator"}),
            frozenset({"synthetic_unit"}),
            frozenset(),
        ),
    )
