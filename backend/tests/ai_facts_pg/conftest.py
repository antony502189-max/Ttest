"""Actual migration in a fresh schema of an explicitly selected disposable DB."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


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
    path = Path(__file__).parents[2] / "alembic/versions/0069_ai_listing_facts.py"
    spec = importlib.util.spec_from_file_location("facts_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        yield engine, migration
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
