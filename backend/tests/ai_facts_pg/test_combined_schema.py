"""Exercise all new AI migrations together, separate from historical CI upgrade."""
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, Table, inspect, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.db.base import Base
from app.models import SavedSearch

pytestmark = pytest.mark.integration


def test_linear_combined_schema_matches_all_ai_models(pg):
    engine, _ = pg
    names = ("0067_ai_search_quota", "0068_ai_search_sessions", "0069_ai_listing_facts", "0070_ai_fact_pipeline",
             "0071_ai_query_proofs", "0072_ai_session_commands", "0073_ai_command_seed", "0074_ai_saved_searches",
             "0075_ai_proof_population")
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
            # Clearly synthetic pre-0072 legacy parents; the complete historical
            # chain is independently upgraded and checked by this CI job.
            connection.execute(text("CREATE TABLE users (id uuid PRIMARY KEY)"))
            connection.execute(text("CREATE TYPE rental_mode AS ENUM ('long','holiday')"))
            connection.execute(text("CREATE TABLE saved_searches (id uuid PRIMARY KEY, "
                "user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, name varchar(120) NOT NULL, "
                "query varchar(240) NOT NULL, rental_mode rental_mode NOT NULL, filters jsonb NOT NULL, "
                "polygon jsonb NOT NULL, alerts_enabled boolean NOT NULL, province_code varchar(2), "
                "created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())"))
            connection.execute(text("CREATE INDEX ix_saved_searches_user_id ON saved_searches(user_id)"))
            with Operations.context(MigrationContext.configure(connection)):
                for module in modules:
                    module.upgrade()
            metadata = MetaData()
            Table("users", metadata, Column("id", PGUUID(as_uuid=True), primary_key=True))
            SavedSearch.__table__.to_metadata(metadata)
            for table in Base.metadata.tables.values():
                if table.name.startswith("ai_"):
                    table.to_metadata(metadata)
            assert len([name for name in metadata.tables if name.startswith("ai_")]) == 16
            assert set(inspect(connection).get_table_names()) == set(metadata.tables)
            assert compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), metadata) == []
            for table in metadata.tables.values():
                expected = {c.name for c in table.constraints if c.__class__.__name__ == "CheckConstraint"}
                assert {c["name"] for c in inspect(connection).get_check_constraints(table.name)} == expected
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
