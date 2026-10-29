"""Tiny PostgreSQL evidence/cancellation regressions, never a capacity run."""
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import text
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
    "ai_listing_facts", "ai_listing_search_features", "ai_query_proofs", "profile", "trigger"])
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
            "synthetic_only":True,"sources":10 if damage == "profile" else 2,"provenance":provenance})})
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
        "observations_per_listing":20,"counts_including_template":counts,"distinct_providers":5,"provenance":provenance}))
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
