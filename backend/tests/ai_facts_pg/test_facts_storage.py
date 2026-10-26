import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.models.ai_listing_facts import AiListingFact, AiListingFactBatch, AiListingSearchFeatures
from app.schemas.ai_listing_facts import FactBatch, SearchProjection, digest

pytestmark = pytest.mark.integration


def batch():
    now = datetime(2026, 10, 26, tzinfo=UTC)
    return {
        "schema_version": "ai-facts.v1", "taxonomy_version": "ai-search.v1", "batch_id": uuid4(),
        "canonical_listing_id": uuid4(), "source_record_id": uuid4(), "source_generation": 1,
        "content_hash": digest({"description": "No pets"}), "extractor_version": "rules.test.v1", "observed_at": now,
        "source_status": "active", "last_successful_check_at": now,
        "last_content_change_at": now - timedelta(days=1), "last_check_error_at": None,
        "facts": [{"fact_id": uuid4(), "key": "pets", "status": "explicit_deny",
                   "typed_value": {"kind": "policy", "allowed": False}, "qualifiers": {}, "origin": "source_text",
                   "evidence": [{"field": "description", "quote": "No pets", "start": 0, "end": 7}]}],
    }


def projection(source):
    feature = source.facts[0].model_dump(include={"key", "status", "typed_value", "qualifiers"})
    feature["supporting_fact_ids"] = [source.facts[0].fact_id]
    return {
        "schema_version": "ai-facts.v1", "taxonomy_version": "ai-search.v1",
        "canonical_listing_id": source.canonical_listing_id, "feature_revision": 1,
        "resolver_version": "resolver.test.v1", "input_hash": "a" * 64,
        "computed_at": source.observed_at, "features": [feature],
    }


def store_batch(connection, value):
    data = value.model_dump(exclude={"facts", "batch_id"})
    connection.execute(AiListingFactBatch.__table__.insert().values(id=value.batch_id, **data))
    for item in value.facts:
        data = item.model_dump(mode="json", exclude={"fact_id"})
        connection.execute(AiListingFact.__table__.insert().values(
            id=item.fact_id, batch_id=value.batch_id, scope_hash=item.scope_hash, **data,
        ))


def store_projection(connection, value):
    data = value.model_dump(exclude={"features"})
    data["features"] = value.model_dump(mode="json")["features"]
    connection.execute(AiListingSearchFeatures.__table__.insert().values(**data))


def test_actual_migration_and_full_new_table_metadata(pg):
    engine, _ = pg
    metadata = MetaData()
    for table in (AiListingFactBatch.__table__, AiListingFact.__table__, AiListingSearchFeatures.__table__):
        assert table.name in Base.metadata.tables
        table.to_metadata(metadata)
    with engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == set(metadata.tables)
        assert compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), metadata) == []
        # Alembic does not compare CHECK bodies. Check their names against the ORM separately.
        for table in metadata.tables.values():
            expected = {c.name for c in table.constraints if c.__class__.__name__ == "CheckConstraint"}
            assert {c["name"] for c in inspect(connection).get_check_constraints(table.name)} == expected
        # Existing models retain no new relationship or FK to these inert tables.
        assert not inspect(connection).get_foreign_keys("ai_listing_fact_batches")


def test_roundtrip_support_freshness_and_no_raw_content(pg):
    engine, _ = pg
    source = FactBatch.model_validate(batch())
    result = SearchProjection.model_validate(projection(source))
    result.validate_support([source])
    with engine.begin() as connection:
        store_batch(connection, source)
        store_projection(connection, result)
    with engine.connect() as connection:
        row = connection.execute(select(AiListingFactBatch.__table__)).mappings().one()
        assert row["last_content_change_at"] < row["last_successful_check_at"]
        assert row["content_hash"] == source.content_hash
        fact = connection.execute(select(AiListingFact.__table__)).mappings().one()
        assert fact["status"] == "explicit_deny"
        assert fact["typed_value"] == {"kind": "policy", "allowed": False}
        projected = connection.execute(select(AiListingSearchFeatures.__table__)).mappings().one()
        assert SearchProjection.model_validate_json(json.dumps(dict(projected), default=str)) == result
        columns = {c["name"] for c in inspect(connection).get_columns("ai_listing_fact_batches")}
        assert not columns & {"raw_payload", "description", "transcript", "audio", "normalized_payload"}


@pytest.mark.parametrize("owner", [False, True])
def test_duplicate_batch_identity_including_null_source(pg, owner):
    engine, _ = pg
    data = batch()
    if owner:
        data["source_record_id"] = None
        data["facts"][0]["origin"] = "owner_explicit"
        data["facts"][0]["evidence"][0]["field"] = "owner_form"
    source = FactBatch.model_validate(data)
    with engine.begin() as connection:
        store_batch(connection, source)
    copy = source.model_dump()
    copy["batch_id"] = uuid4()
    copy["facts"][0]["fact_id"] = uuid4()
    with pytest.raises(IntegrityError), engine.begin() as connection:
        store_batch(connection, FactBatch.model_validate(copy))
    # A new generation is separate history, including when its hash is unchanged.
    copy["source_generation"] += 1
    with engine.begin() as connection:
        store_batch(connection, FactBatch.model_validate(copy))
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(AiListingFactBatch)) == 2


def test_owner_and_source_uuid_namespaces_do_not_collide(pg):
    engine, _ = pg
    external = batch()
    external["source_record_id"] = external["canonical_listing_id"]
    owner = batch()
    owner["canonical_listing_id"] = external["canonical_listing_id"]
    owner["source_record_id"] = None
    owner["facts"][0]["origin"] = "owner_explicit"
    owner["facts"][0]["evidence"][0]["field"] = "owner_form"
    with engine.begin() as connection:
        store_batch(connection, FactBatch.model_validate(external))
        store_batch(connection, FactBatch.model_validate(owner))
        assert connection.scalar(select(func.count()).select_from(AiListingFactBatch)) == 2


@pytest.mark.parametrize("changes", [
    {"status": "explicit"}, {"key": "unbounded_model_key"}, {"origin": "untrusted"},
    {"status": "unknown"}, {"typed_value": None}, {"origin": "legacy_default"},
    {"evidence": []}, {"qualifiers": []}, {"scope_hash": "invalid"},
])
def test_database_rejects_bypassed_observation_contract(pg, changes):
    engine, _ = pg
    source = FactBatch.model_validate(batch())
    with engine.begin() as connection:
        store_batch(connection, source)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(AiListingFact.__table__.update().values(**changes))


@pytest.mark.parametrize("changes", [
    {"source_generation": 0}, {"content_hash": "bad"}, {"schema_version": "ai-facts.v2"},
    {"source_status": "published"}, {"extractor_version": ""},
    {"last_successful_check_at": datetime(2027, 1, 1, tzinfo=UTC)},
])
def test_database_rejects_invalid_batch_state(pg, changes):
    engine, _ = pg
    with engine.begin() as connection:
        store_batch(connection, FactBatch.model_validate(batch()))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(AiListingFactBatch.__table__.update().values(**changes))


def test_evidence_and_projection_rollback_atomically(pg):
    engine, _ = pg
    source = FactBatch.model_validate(batch())
    with pytest.raises(RuntimeError, match="simulated failure"), engine.begin() as connection:
        store_batch(connection, source)
        store_projection(connection, SearchProjection.model_validate(projection(source)))
        raise RuntimeError("simulated failure before commit")
    with engine.connect() as connection:
        for model in (AiListingFact, AiListingFactBatch, AiListingSearchFeatures):
            assert connection.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("changes", [
    {"feature_revision": 0}, {"input_hash": "bad"}, {"schema_version": "ai-facts.v2"},
    {"taxonomy_version": "ai-search.v0"}, {"resolver_version": ""}, {"features": [None] * 129},
])
def test_database_projection_bounds(pg, changes):
    engine, _ = pg
    source = FactBatch.model_validate(batch())
    with engine.begin() as connection:
        store_projection(connection, SearchProjection.model_validate(projection(source)))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(AiListingSearchFeatures.__table__.update().values(**changes))


def test_check_does_not_change_content_timestamp_and_downgrade_preserves_data(pg):
    engine, migration = pg
    source = FactBatch.model_validate(batch())
    with engine.begin() as connection:
        store_batch(connection, source)
        connection.execute(AiListingFactBatch.__table__.update().values(
            last_successful_check_at=source.observed_at + timedelta(minutes=1),
            observed_at=source.observed_at + timedelta(minutes=1),
        ))
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
    with engine.connect() as connection:
        row = connection.execute(select(AiListingFactBatch.__table__)).mappings().one()
        assert row["last_content_change_at"] == source.last_content_change_at
        assert row["last_successful_check_at"] > source.last_successful_check_at
        assert connection.scalar(text("SELECT count(*) FROM ai_listing_facts")) == 1
