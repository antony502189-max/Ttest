"""Exercise all new AI migrations together, separate from historical CI upgrade."""
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, inspect, text

from app.db.base import Base

pytestmark = pytest.mark.integration


def test_linear_combined_schema_matches_all_ai_models(pg):
    engine, _ = pg
    names = ("0067_ai_search_quota", "0068_ai_search_sessions", "0069_ai_listing_facts", "0070_ai_fact_pipeline")
    previous = "0066_complimentary_ads"
    modules = []
    for name in names:
        path = Path(__file__).parents[2] / "alembic/versions" / (name + ".py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.down_revision == previous
        previous = module.revision
        modules.append(module)
    schema = "ai_combined_" + uuid4().hex
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            with Operations.context(MigrationContext.configure(connection)):
                for module in modules:
                    module.upgrade()
            metadata = MetaData()
            for table in Base.metadata.tables.values():
                if table.name.startswith("ai_"):
                    table.to_metadata(metadata)
            assert len(metadata.tables) == 11
            assert set(inspect(connection).get_table_names()) == set(metadata.tables)
            assert compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), metadata) == []
            for table in metadata.tables.values():
                expected = {c.name for c in table.constraints if c.__class__.__name__ == "CheckConstraint"}
                assert {c["name"] for c in inspect(connection).get_check_constraints(table.name)} == expected
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
