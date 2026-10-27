"""Actual migration in a fresh schema of an explicitly selected disposable DB."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.repositories.ai_fact_pipeline import FactPipeline
from app.schemas.ai_fact_pipeline import FactQueuePolicy
from app.schemas.ai_listing_facts import FactVocabulary


@pytest.fixture
def pg():
    value = os.getenv("AI_FACTS_TEST_DATABASE_URL") or os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.fail("set AI_FACTS_TEST_DATABASE_URL to disposable loopback ai_facts_test_* DB")
    url = make_url(value)
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not (
        (url.database or "").startswith("ai_facts_test_") or url.database == "ttest_test"
    ):
        pytest.fail("facts tests require a disposable loopback ai_facts_test_* database")
    schema = "ai_facts_" + uuid4().hex
    admin = create_engine(url.set(drivername="postgresql+psycopg"))
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url.set(drivername="postgresql+psycopg"), connect_args={
        "options": f"-csearch_path={schema} -clock_timeout=5000 -cstatement_timeout=10000",
    })
    migrations = []
    for name in ("0069_ai_listing_facts.py", "0070_ai_fact_pipeline.py"):
        path = Path(__file__).parents[2] / "alembic/versions" / name
        spec = importlib.util.spec_from_file_location("facts_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migrations.append(migration)
    try:
        with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            for migration in migrations:
                migration.upgrade()
        yield engine, migrations[0]
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest_asyncio.fixture
async def pipeline(pg):
    sync_engine, _ = pg
    with sync_engine.begin() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
        # Minimal clearly synthetic stand-ins for the selected legacy columns.
        # Full real legacy migrations run independently in CI before these tests.
        connection.execute(text("CREATE TYPE listing_status AS ENUM ('draft','pending','published','hidden','closed','rejected')"))
        connection.execute(text("CREATE TABLE listings (id uuid PRIMARY KEY, status listing_status NOT NULL, deleted_at timestamptz)"))
        connection.execute(text("CREATE TABLE external_listing_sources (id uuid PRIMARY KEY, canonical_listing_id uuid NOT NULL, "
                                "fingerprint text NOT NULL, current_status text NOT NULL, last_success_at timestamptz, "
                                "content_updated_at timestamptz, raw_payload jsonb NOT NULL DEFAULT '{}', "
                                "normalized_payload jsonb NOT NULL DEFAULT '{}', source_price_text text, "
                                "source_name text NOT NULL DEFAULT 'synthetic', external_id text NOT NULL DEFAULT 'fixture', "
                                "source_url text NOT NULL DEFAULT 'https://example.invalid/fixture')"))
    engine = create_async_engine(sync_engine.url.set(drivername="postgresql+asyncpg"),
                                pool_size=16, max_overflow=0, connect_args={"server_settings": {
                                    "search_path": schema, "lock_timeout": "5000", "statement_timeout": "10000",
                                }})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    policy = FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1)
    vocabulary = FactVocabulary(amenity_codes=frozenset({"test_wifi"}), catalog_other_codes=frozenset(),
                                tenant_group_codes=frozenset(), municipality_zones=frozenset())
    try:
        yield FactPipeline(sessions, policy, vocabulary, resolver_version="source-resolver.test.v1"), sessions
    finally:
        await engine.dispose()
