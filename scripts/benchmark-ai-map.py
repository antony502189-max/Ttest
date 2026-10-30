"""Offline R-01 experiment. Run only in the private disposable Docker lab.

No provider, worker, public runtime or HTTP registration is constructed.
Bulk fixtures are derived from real pipeline-validated templates, then sampled
through the real verifier. SQL comes from the actual map implementation.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import event, func, literal, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.sql import operators, visitors
from sqlalchemy.sql.elements import BooleanClauseList

from app.models import ExternalListingSource, Listing, User
from app.models.ai_fact_pipeline import AiFactCatalog, AiFactSource
from app.models.ai_listing_facts import (
    AiListingFact,
    AiListingFactBatch,
    AiListingSearchFeatures,
)
from app.models.ai_query_proof import AiQueryProof
from app.models.room_details import ListingRoomDetails
from app.repositories.ai_fact_pipeline import FactPipeline
from app.repositories.ai_fact_snapshots import source_snapshot_hash
from app.repositories.ai_query_proofs import QueryProofs, projection_signature
from app.repositories.ai_verified_cards import VerifiedCardSearch
from app.repositories.listings import point
from app.schemas.ai_fact_pipeline import FactQueuePolicy, SourceInput
from app.schemas.ai_listing_facts import FactBatch, FactVocabulary, digest
from app.schemas.ai_search_intent import SearchIntent
from app.schemas.listings import ListingMapRequest

DSN = "postgresql+asyncpg://r01:r01-synthetic-only@r01-db:5432/r01_synthetic"
OUT = Path("/results")
RESOLVER = "r01-synthetic.v1"
SEED_WRITERS = 8
PROTOCOL_VERSION = "r01-capacity.v2"
PROVENANCE = {}
RUN_ID = None


def now():
    return datetime.now(UTC).isoformat()


def save(name, value):
    OUT.mkdir(exist_ok=True)
    if isinstance(value, dict):
        value = {**value, "provenance": PROVENANCE, "run_id": RUN_ID}
    elif isinstance(value, list):
        value = [{**row, "provenance": PROVENANCE, "run_id": RUN_ID} if isinstance(row, dict) else row for row in value]
    temporary = OUT / (name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(OUT / name)


def log(kind, **data):
    value = {"at": now(), "kind": kind, **data, "provenance": PROVENANCE, "run_id": RUN_ID}
    print(json.dumps(value, default=str), flush=True)
    with (OUT / "progress.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(value, default=str) + "\n")


def validate_lab_environment():
    # Alembic reads DATABASE_URL, unlike the fixed-DSN query engine. Validate
    # before spawning migrations too, so direct invocation cannot migrate an
    # application DB even when the isolated-lab marker was copied accidentally.
    if os.environ.get("R01_DISPOSABLE_LAB") != "synthetic-only":
        raise RuntimeError("explicit isolated-lab marker required")
    if os.environ.get("DATABASE_URL") != DSN or os.environ.get("APP_ENV") != "test":
        raise RuntimeError("expected the fixed synthetic-only database and test environment")


def engine(pool=1, timeout=5000):
    # Fixed lab hostname/database; no CLI/environment override to application DBs.
    validate_lab_environment()
    return create_async_engine(DSN, pool_size=pool, max_overflow=0, pool_timeout=30,
        connect_args={"server_settings": {"statement_timeout": str(timeout),
            "lock_timeout": "1000", "application_name": "codex-r01-synthetic"}})


async def maintain_seed_database(connection, *, vacuum=False):
    # Bulk ingestion can overlap autovacuum's ShareUpdateExclusive relation
    # lock. The measured-query 1s timeout is too short for setup maintenance.
    # Bound this wait separately and restore the query setting on every exit.
    previous = await connection.scalar(text("SHOW lock_timeout"))
    await connection.execute(text("SELECT set_config('lock_timeout', '60s', false)"))
    try:
        await connection.execute(text("VACUUM ANALYZE" if vacuum else "ANALYZE"))
    finally:
        await connection.execute(text("SELECT set_config('lock_timeout', :value, false)"), {"value": previous})


def bind_experiment(sources, phase):
    """An output directory belongs to exactly one immutable code/DB/profile seed."""
    global PROVENANCE, RUN_ID
    fields = {key: os.environ.get(env) for key, env in (
        ("experiment_id", "R01_EXPERIMENT_ID"), ("code_revision", "R01_CODE_REVISION"),
        ("runner_image_id", "R01_IMAGE_ID"), ("archive_sha256", "R01_SOURCE_ARCHIVE_SHA256"),
        ("db_container_id", "R01_DB_ID"), ("db_image_id", "R01_DB_IMAGE_ID"))}
    patterns = {"experiment_id": r"[0-9a-f]{32}", "code_revision": r"[0-9a-f]{40}",
        "archive_sha256": r"[0-9a-f]{64}", "db_container_id": r"[0-9a-f]{64}",
        "runner_image_id": r"sha256:[0-9a-f]{64}", "db_image_id": r"sha256:[0-9a-f]{64}"}
    if any(not re.fullmatch(patterns[key], value or "") for key, value in fields.items()):
        raise RuntimeError("verified immutable experiment provenance required")
    if os.environ.get("R01_SOURCE_MODE") != "git-archive" or os.environ.get("R01_CHECKOUT_CLEAN") != "true":
        raise RuntimeError("clean archived source required")
    fields.update(sources=sources, observations=20, seed_id=fields["experiment_id"],protocol_version=PROTOCOL_VERSION)
    path = OUT / "experiment.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != fields:
            raise RuntimeError("experiment provenance mismatch; use a new experiment and seed")
    else:
        if phase != "initialize":
            raise RuntimeError("initialize the experiment before seed/measure")
        if any(OUT.iterdir()):
            raise RuntimeError("new experiment directory must be empty")
        with path.open("x", encoding="utf-8") as stream:
            json.dump(fields, stream, indent=2)
    run_id = os.environ.get("R01_RUN_ID")
    if not re.fullmatch(r"[0-9a-f]{32}", run_id or ""):
        raise RuntimeError("explicit phase run ID required")
    if list(OUT.glob(f"runner-*-{run_id}.json")):
        raise RuntimeError("phase run IDs cannot be reused")
    PROVENANCE, RUN_ID = fields, run_id


@contextmanager
def phase_file_lock():
    """An OS lock survives neither process exit nor a crash; the owner is recorded."""
    with (OUT / ".phase.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b" ")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("another phase owns this experiment output") from error
        owner = json.dumps({"run_id":RUN_ID, "pid":os.getpid(), "at":now()}).encode()
        try:
            stream.seek(0)
            stream.truncate()
            stream.write(owner)
            stream.flush()
            yield
            stream.seek(0)
            if stream.read() != owner:
                raise RuntimeError("experiment lock owner changed")
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@asynccontextmanager
async def phase_database_guard(db, phase, total):
    # This lock is database-wide, including different output/experiment IDs.
    if phase == "initialize":
        # CREATE INDEX CONCURRENTLY waits for older transaction snapshots.
        # Keep the same advisory-lock namespace without pinning a transaction
        # across the migration subprocess; session locks survive autocommit.
        async with db.connect() as c:
            await c.execution_options(isolation_level="AUTOCOMMIT")
            if not await c.scalar(text("SELECT pg_try_advisory_lock(401, 1)")):
                raise RuntimeError("another synthetic initialize/seed/measure owns the database")
            try:
                yield
            finally:
                await c.execute(text("SELECT pg_advisory_unlock(401, 1)"))
        return
    async with db.begin() as c:
        if not await c.scalar(text("SELECT pg_try_advisory_xact_lock(401, 1)")):
            raise RuntimeError("another synthetic initialize/seed/measure owns the database")
        stability = None
        if phase == "measure":
            # SHARE permits SELECT but blocks ordinary DML, TRUNCATE and DDL,
            # including writers which do not honor our advisory lock.
            tables = list(await c.scalars(text("SELECT format('%I.%I', n.nspname, c.relname) "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname=current_schema() AND c.relkind IN ('r','p') ORDER BY c.oid")))
            if not tables:
                raise RuntimeError("missing synthetic dataset tables")
            await c.execute(text("LOCK TABLE " + ", ".join(tables) + " IN SHARE MODE NOWAIT"))
            before = await c.scalar(text("SELECT data FROM r01_meta"))
            if before.get("provenance") != PROVENANCE or type(before.get("generation")) is not int:
                raise RuntimeError("dataset seed generation/provenance mismatch")
            stability = {"total":total,"started_at":now(),"write_frozen":True,
                "lock_mode":"SHARE", "tables":tables,"seed_generation_before":before["generation"],"stable":False}
        try:
            yield
            if stability is not None:
                after = await c.scalar(text("SELECT data FROM r01_meta"))
                stability.update(seed_generation_after=after.get("generation"),stable=after == before,ended_at=now())
                if not stability["stable"]:
                    raise RuntimeError("dataset changed during measurement")
        finally:
            if stability is not None:
                stability.setdefault("ended_at", now())
                save(f"dataset-stability-{total}-{RUN_ID}.json",stability)


async def verify_database_identity(db):
    async with db.connect() as c:
        await c.execute(text("SET TRANSACTION READ ONLY"))
        row = (await c.execute(text("SELECT current_database() AS db, current_user AS role, "
            "current_setting('server_version_num')::int AS version, postgis_lib_version() AS postgis"))).mappings().one()
        if row["db"] != "r01_synthetic" or row["role"] != "r01" or not 160000 <= row["version"] < 170000 or not row["postgis"].startswith("3.4."):
            raise RuntimeError("unexpected synthetic PostgreSQL/PostGIS identity")


async def validate_dataset(c, total):
    """Run before timed SQL, under one repeatable read-only snapshot."""
    template = json.loads((OUT / "template.json").read_text(encoding="utf-8"))
    dataset = json.loads((OUT / f"dataset-{total}.json").read_text(encoding="utf-8"))
    meta = await c.scalar(text("SELECT data FROM r01_meta"))
    if isinstance(meta, str):
        meta = json.loads(meta)
    if (meta.get("synthetic_only") is not True or meta.get("provenance") != PROVENANCE or
            template.get("provenance") != PROVENANCE or dataset.get("provenance") != PROVENANCE or
            meta.get("sources") != template.get("sources") or template.get("sources") != PROVENANCE.get("sources") or
            template.get("observations") != 20 or dataset.get("listings") != total or
            dataset.get("source_records_per_listing") != template["sources"] or dataset.get("observations_per_listing") != 20 or
            type(meta.get("generation")) is not int or meta["generation"] < 1 or dataset.get("seed_generation") != meta["generation"]):
        raise RuntimeError("dataset provenance/profile mismatch")
    entities = await c.scalar(text("SELECT count(*) FROM r01_entities"))
    if entities != total:
        raise RuntimeError("dataset entity count mismatch")
    for model in (Listing, ListingRoomDetails, ExternalListingSource, AiFactCatalog, AiListingFactBatch,
                  AiFactSource, AiListingFact, AiListingSearchFeatures, AiQueryProof):
        multiplier = 20 if model is AiListingFact else template["sources"] if model in (
            ExternalListingSource, AiFactSource, AiListingFactBatch) else 1
        actual = await c.scalar(select(func.count()).select_from(model))
        if actual != (total + 1) * multiplier or dataset["counts_including_template"].get(model.__tablename__) != actual:
            raise RuntimeError(f"dataset row count mismatch: {model.__tablename__}")
    providers = await c.scalar(select(func.count(func.distinct(ExternalListingSource.source_name))))
    if providers != min(10, total + template["sources"]) or dataset.get("distinct_providers") != providers:
        raise RuntimeError("dataset provider profile mismatch")
    if await c.scalar(text("SELECT tgenabled::text FROM pg_trigger WHERE tgrelid='listings'::regclass AND tgname='listings_catalog_version'")) != "O":
        raise RuntimeError("setup trigger must be restored before measurements")


def pipeline(factory):
    vocab = FactVocabulary(amenity_codes=frozenset({"wifi"}), catalog_other_codes=frozenset(),
        tenant_group_codes=frozenset({"students"}), municipality_zones=frozenset())
    return FactPipeline(factory, FactQueuePolicy(lease_seconds=600, max_attempts=2, retry_delay_seconds=1),
        vocab, resolver_version=RESOLVER)


def observations():
    def value(key, typed, qualifiers=None, status="explicit_allow"):
        return {"fact_id": uuid4(), "key": key, "status": status, "typed_value": typed,
            "qualifiers": qualifiers or {}, "origin": "source_text", "evidence": [
                {"field": "description", "quote": "Synthetic fixture", "start": 0, "end": 17}]}
    policy = lambda: {"kind": "policy", "allowed": True}
    boolean = lambda: {"kind": "boolean", "value": True}
    quantity = lambda n, unit="persons": {"kind": "quantity", "value": n, "unit": unit}
    return [value("pets", policy()), value("smoking", policy(), {"smoking_scope": "indoors"}),
        value("couples", policy()), value("children", policy()),
        value("tenant_groups", policy(), {"tenant_group": "students"}),
        value("capacity_total", quantity(2), {"inventory_scope": "rented_unit"}),
        value("current_room_residents", quantity(0), {"inventory_scope": "rented_unit"}),
        value("available_spots", quantity(2), {"inventory_scope": "rented_unit"}),
        value("price", {"kind": "money", "amount": "725", "currency": "EUR", "period": "monthly"}),
        value("deposit", {"kind": "money", "amount": "100", "currency": "EUR", "period": "one_off"}),
        *[value(k, boolean()) for k in ("furnished", "bills_included", "balcony", "terrace")],
        value("amenity", boolean(), {"amenity_code": "wifi"}),
        value("rental_mode", {"kind": "category", "value": "long"}),
        value("accommodation", {"kind": "category", "value": "room"}),
        value("geography", {"kind": "geography", "province_code": "38", "municipality_code": "38001"}),
        value("minimum_stay", quantity(1, "months")), value("maximum_stay", quantity(12, "months"))]


def fixture_signature(listing_id):
    """Equivalent digest for FAST bulk fixture certification only.

    Historical baseline runs used the OR authority expression. For their setup
    only, select the identical ID set with an indexable UNION. Once production
    uses the same indexed access, this traversal leaves it unchanged. Actual
    measured source hashes distinguish those revisions. Assert exact digest
    equality on sampled rows before accepting the dataset.
    """
    def replace(node):
        if not isinstance(node, BooleanClauseList) or node.operator is not operators.or_:
            return None
        clauses = list(node.clauses)
        if len(clauses) != 2 or getattr(clauses[0].left, "name", None) != "canonical_listing_id":
            return None
        _, right = clauses
        if getattr(right.left, "name", None) != "id" or right.operator is not operators.in_op:
            return None
        current = ExternalListingSource.__table__.alias()
        ids = select(current.c.id).where(current.c.canonical_listing_id == listing_id).correlate_except(current)
        return right.left.in_(ids.union(right.right.element))
    return visitors.replacement_traverse(projection_signature(listing_id), {}, replace)


async def initialize(sources):
    validate_lab_environment()
    if sources not in (2, 10):
        raise ValueError("20 observations are split across 2 or 10 records")
    identity = engine()
    try:
        await verify_database_identity(identity)
        async with identity.connect() as c:
            if await c.scalar(text("SELECT to_regclass('r01_meta')")) is not None:
                raise RuntimeError("database already belongs to a seed; create a fresh disposable lab")
    finally:
        await identity.dispose()
    # Environment is replaced by the launcher, not loaded from a project .env.
    process = await asyncio.create_subprocess_exec("python", "-m", "alembic", "upgrade", "head", cwd="/code/backend")
    if await process.wait():
        raise RuntimeError("lab migration failed")
    db = engine(timeout=60000)
    factory = async_sessionmaker(db, expire_on_commit=False)
    pipe = pipeline(factory)
    async with db.begin() as c:
        await c.execute(text("CREATE EXTENSION IF NOT EXISTS pg_stat_statements"))
        await c.execute(text("CREATE TABLE r01_entities (n bigint PRIMARY KEY, id uuid UNIQUE NOT NULL)"))
        await c.execute(text("CREATE TABLE r01_ids (old text PRIMARY KEY, kind text, slot int)"))
        await c.execute(text("CREATE TABLE r01_meta (data jsonb NOT NULL)"))
        await c.execute(text("INSERT INTO r01_meta VALUES (:v)"), {"v": json.dumps({"synthetic_only": True, "sources": sources, "provenance": PROVENANCE,"generation":0})})
        await c.execute(text("""CREATE FUNCTION r01_uuid(k text, n bigint, s int DEFAULT 0) RETURNS uuid
            LANGUAGE sql IMMUTABLE AS $$ SELECT md5(k || ':' || n::text || ':' || s::text)::uuid $$"""))
        await c.execute(text("""CREATE FUNCTION r01_rewrite(v jsonb, n bigint) RETURNS jsonb LANGUAGE plpgsql AS $$
            DECLARE r record; t text := v::text; BEGIN
            FOR r IN SELECT * FROM r01_ids LOOP t := replace(t, r.old, r01_uuid(r.kind,n,r.slot)::text); END LOOP;
            RETURN t::jsonb; END $$"""))
        await c.execute(text("""CREATE FUNCTION r01_new(v uuid, n bigint) RETURNS uuid LANGUAGE sql STABLE AS $$
            SELECT r01_uuid(kind,n,slot) FROM r01_ids WHERE old=v::text $$"""))
        await c.execute(text("""CREATE FUNCTION r01_canonical(v jsonb) RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
            DECLARE t text; BEGIN
            IF jsonb_typeof(v) = 'object' THEN
              SELECT '{' || coalesce(string_agg(to_jsonb(key)::text || ':' || r01_canonical(value), ',' ORDER BY key COLLATE "C"),'') || '}' INTO t FROM jsonb_each(v);
            ELSIF jsonb_typeof(v) = 'array' THEN
              SELECT '[' || coalesce(string_agg(r01_canonical(value), ',' ORDER BY ordinal),'') || ']' INTO t FROM jsonb_array_elements(v) WITH ORDINALITY AS e(value,ordinal);
            ELSE t := v::text; END IF; RETURN t; END $$"""))
    now = datetime.now(UTC)
    async with factory() as s, s.begin():
        owner = User(email="r01@example.invalid", password_hash="unused", name="Synthetic Owner", role="host", initials="SO", email_verified=True)
        s.add(owner)
        await s.flush()
        listing = Listing(owner_user_id=owner.id, title="Synthetic load fixture", city="Adeje", area="Synthetic",
            approximate_address="Synthetic only", rental_mode="long", monthly_price=725,
            room_capacity=2, location=point(-16.95, 28.05), status="published", published_at=now,
            deposit_amount=100, minimum_stay_months=1, bills_included=True, furnished=True)
        s.add(listing)
        await s.flush()
        s.add(ListingRoomDetails(listing_id=listing.id, room_capacity_v2=2, current_room_residents=0, rental_unit="room"))
        rows = []
        for slot in range(sources):
            row = ExternalListingSource(source_name=f"synth-{slot}", external_id=f"template-{slot}",
                source_url=f"https://example.invalid/template/{slot}", canonical_listing_id=listing.id,
                fingerprint=digest(f"source-{slot}"), raw_payload={"synthetic": True}, normalized_payload={},
                current_status="active", last_success_at=now, content_updated_at=now)
            s.add(row)
            rows.append(row)
        await s.flush()
        lid, source_ids = listing.id, [r.id for r in rows]
    facts = observations()
    assert len(facts) == 20
    for slot, source_id in enumerate(source_ids):
        async with factory() as s:
            _, authority = await pipe._authority(s, lid, lock=False)
        fields = {"description": "Synthetic fixture"}
        await pipe.observe(SourceInput(source_record_id=source_id, canonical_listing_id=lid,
            content_hash=digest(fields), snapshot_hash=authority[source_id].snapshot_hash,
            schema_version="ai-facts.v1", taxonomy_version="ai-search.v1", extractor_version=RESOLVER))
        claim = await pipe.claim()
        batch = FactBatch.model_validate({"batch_id": uuid4(), "canonical_listing_id": lid,
            "source_record_id": source_id, "source_generation": claim.generation,
            "content_hash": claim.content_hash, "schema_version": claim.schema_version,
            "taxonomy_version": claim.taxonomy_version, "extractor_version": claim.extractor_version,
            "observed_at": datetime.now(UTC), "source_status": "active", "last_successful_check_at": None,
            "last_content_change_at": None, "last_check_error_at": None, "facts": facts[slot::sources]})
        await pipe.complete(claim, batch, fields)
    assert await QueryProofs(pipe).prepare(lid), "real template verifier rejected fixture"
    async with factory() as s, s.begin():
        mappings = [(str(lid), "listing", 0)]
        for slot, source in enumerate((await s.scalars(select(AiFactSource).where(AiFactSource.canonical_listing_id == lid).order_by(AiFactSource.source_record_id))).all()):
            mappings += [(str(source.source_record_id), "source", slot), (str(source.batch_id), "batch", slot)]
        stored = (await s.scalars(select(AiListingFact).where(AiListingFact.batch_id.in_(
            select(AiFactSource.batch_id).where(AiFactSource.canonical_listing_id == lid))).order_by(AiListingFact.key))).all()
        assert len(stored) == 20
        for i, fact in enumerate(stored):
            # complete() replaces extractor IDs with deterministic job IDs.
            mappings.append((str(fact.id), "fact", i))
        for old, kind, slot in mappings:
            await s.execute(text("INSERT INTO r01_ids VALUES (:old,:kind,:slot)"), {"old": old, "kind": kind, "slot": slot})
    save("template.json", {"listing": lid, "vocabulary_hash": pipe.vocabulary_hash, "sources": sources,
        "observations": 20, "verified_by": "FactPipeline.complete + QueryProofs.prepare"})
    await db.dispose()
    log("initialized", sources=sources)


async def seed(total, chunk=5000):
    template = json.loads((OUT / "template.json").read_text())
    db = engine(pool=SEED_WRITERS, timeout=0)
    lid = UUID(template["listing"])
    factory = async_sessionmaker(db, expire_on_commit=False)
    pipe = pipeline(factory)
    async with db.connect() as c:
        assert (await c.scalar(text("SELECT data->>'synthetic_only' FROM r01_meta"))) == "true"
        start = await c.scalar(text("SELECT coalesce(min(g),CAST(:total AS bigint)+1) FROM generate_series(1,CAST(:total AS bigint)) g LEFT JOIN r01_entities e ON e.n=g WHERE e.n IS NULL"), {"total":total})
    models = [Listing, ListingRoomDetails, ExternalListingSource, AiFactCatalog, AiListingFactBatch,
        AiFactSource, AiListingFact, AiListingSearchFeatures]
    template_where = {Listing: "t.id=:lid", ListingRoomDetails: "t.listing_id=:lid",
        AiListingFact: "t.batch_id IN (SELECT batch_id FROM ai_fact_sources WHERE canonical_listing_id=:lid)"}
    async def seed_chunk(lo):
        hi = min(total, lo + chunk - 1)
        began = time.perf_counter()
        async with db.begin() as c:
            present=await c.scalar(text("SELECT count(*) FROM r01_entities WHERE n BETWEEN :lo AND :hi"), {"lo":lo,"hi":hi})
            if present == hi-lo+1:
                return
            if present:
                raise RuntimeError("partially overlapping seed chunk; inspect fixture before resuming")
            await c.execute(text("INSERT INTO r01_entities SELECT g,r01_uuid('listing',g) FROM generate_series(CAST(:lo AS bigint),CAST(:hi AS bigint)) g"), {"lo": lo, "hi": hi})
            for model in models:
                table = model.__tablename__
                condition = template_where.get(model, "t.canonical_listing_id=:lid")
                extra = "jsonb_build_object('canonical_listing_id',r01_uuid('listing',g))"
                if model is Listing:
                    extra = "jsonb_build_object('id',r01_uuid('listing',g),'location',ST_SetSRID(ST_MakePoint(-16.9+((g-1)%1000)*0.0001,28+((g-1)/1000)*0.0001),4326)::geography)"
                elif model is ListingRoomDetails:
                    extra = "jsonb_build_object('listing_id',r01_uuid('listing',g))"
                elif model is ExternalListingSource:
                    extra += " || jsonb_build_object('id',r01_new(t.id,g),'external_id',g::text||'-'||t.external_id,'source_url','https://example.invalid/'||g::text||'/'||t.external_id,'source_name','synth-'||((g + (SELECT slot FROM r01_ids WHERE old=t.id::text))%10)::text)"
                elif model is AiListingFactBatch:
                    extra += " || jsonb_build_object('id',r01_new(t.id,g),'source_record_id',r01_new(t.source_record_id,g))"
                elif model is AiFactSource:
                    extra += " || jsonb_build_object('source_record_id',r01_new(t.source_record_id,g),'batch_id',r01_new(t.batch_id,g))"
                elif model is AiListingFact:
                    extra = "jsonb_build_object('id',r01_new(t.id,g),'batch_id',r01_new(t.batch_id,g))"
                elif model is AiListingSearchFeatures:
                    extra += " || jsonb_build_object('features',r01_rewrite(t.features,g))"
                await c.execute(text(f"INSERT INTO {table} SELECT (filled.row).* FROM {table} t CROSS JOIN generate_series(CAST(:lo AS bigint),CAST(:hi AS bigint)) g CROSS JOIN LATERAL (SELECT jsonb_populate_record(NULL::{table},to_jsonb(t) || {extra}) AS row OFFSET 0) filled WHERE {condition}"), {"lo": lo, "hi": hi, "lid": lid})
            snapshot = select(ExternalListingSource.id.label("id"), source_snapshot_hash().label("hash")).where(
                ExternalListingSource.canonical_listing_id.in_(select(text("id")).select_from(text("r01_entities")).where(text("n BETWEEN :lo AND :hi")))).subquery()
            await c.execute(update(AiFactSource).where(AiFactSource.source_record_id == snapshot.c.id).values(snapshot_hash=snapshot.c.hash), {"lo": lo, "hi": hi})
            # Same input manifest as _projection_inputs. The canonical JSON
            # encoder matches Python digest; sampled real verifier checks this.
            await c.execute(text("""UPDATE ai_listing_search_features p SET input_hash=encode(sha256(convert_to(r01_canonical(
              jsonb_build_object('inputs',(SELECT jsonb_agg(jsonb_build_object(
                'source',s.source_record_id::text,'active',true,'fingerprint',s.source_fingerprint,'snapshot',s.snapshot_hash,
                'canonical',s.canonical_listing_id::text,'generation',s.generation,'hash',s.content_hash,
                'batch',s.batch_id::text,'schema',s.schema_version,'taxonomy',s.taxonomy_version,'extractor',s.extractor_version)
                ORDER BY s.source_record_id::text) FROM ai_fact_sources s WHERE s.canonical_listing_id=p.canonical_listing_id),
                'visible',true,'pending',false,'resolver',CAST(:resolver AS text),'vocabulary',CAST(:vocabulary AS text))), 'UTF8')),'hex')
              WHERE p.canonical_listing_id IN (SELECT id FROM r01_entities WHERE n BETWEEN :lo AND :hi)"""),
                {"lo": lo, "hi": hi, "resolver": RESOLVER, "vocabulary": pipe.vocabulary_hash})
        log("seed_chunk", lo=lo, hi=hi, seconds=round(time.perf_counter()-began, 3))
    for base in range(start,total+1,chunk*SEED_WRITERS):
        await asyncio.gather(*(seed_chunk(lo) for lo in range(base,min(total+1,base+chunk*SEED_WRITERS),chunk)))
    async with db.connect() as c:
        await c.execution_options(isolation_level="AUTOCOMMIT")
        await maintain_seed_database(c)
    # Verify actual production Python resolver/hash/card-value checks BEFORE
    # bulk certification, not merely the fact that rows exist.
    for n in sorted({1, max(1,total//2), total}):
        async with db.connect() as c:
            identifier = await c.scalar(text("SELECT id FROM r01_entities WHERE n=:n"), {"n": n})
        assert await QueryProofs(pipe).prepare(identifier), f"cloned listing {n} failed real verifier"
        async with db.connect() as c:
            assert await c.scalar(select(fixture_signature(literal(identifier)))) == await c.scalar(select(projection_signature(literal(identifier))))
    async def proof_chunk(lo):
        hi = min(total, lo+chunk-1)
        async with db.begin() as c:
            entities = text("r01_entities")
            proof_select = select(Listing.id, fixture_signature(Listing.id), literal(pipe.vocabulary_hash),
                literal(RESOLVER), AiListingSearchFeatures.feature_revision).join(
                    AiListingSearchFeatures, AiListingSearchFeatures.canonical_listing_id == Listing.id).where(
                    Listing.id.in_(select(text("id")).select_from(entities).where(text("n BETWEEN :lo AND :hi"))),
                    ~select(AiQueryProof.canonical_listing_id).where(AiQueryProof.canonical_listing_id == Listing.id).exists())
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            statement = pg_insert(AiQueryProof).from_select(["canonical_listing_id", "signature", "vocabulary_hash", "resolver_version", "feature_revision"], proof_select)
            await c.execute(statement.on_conflict_do_nothing(), {"lo": lo, "hi": hi})
        log("proof_chunk", lo=lo, hi=hi)
    for base in range(1,total+1,chunk*SEED_WRITERS):
        await asyncio.gather(*(proof_chunk(lo) for lo in range(base,min(total+1,base+chunk*SEED_WRITERS),chunk)))
    checked=[]
    for n in sorted(n for n in {2,total//7,total//3,total//2+1,total*2//3,total-1,total} if 1 <= n <= total):
        async with db.connect() as c:
            identifier=await c.scalar(text("SELECT id FROM r01_entities WHERE n=:n"),{"n":n})
            stored=await c.scalar(select(AiQueryProof.signature).where(AiQueryProof.canonical_listing_id==identifier))
            actual=await c.scalar(select(projection_signature(literal(identifier))))
            assert stored==actual, f"bulk proof mismatch at synthetic ordinal {n}"
            checked.append(n)
    async with db.connect() as c:
        generation = await c.scalar(text("SELECT (data->>'generation')::bigint FROM r01_meta"))
    save(f"proof-verification-{total}.json",{"actual_production_digest_equal":True,"ordinals":checked,"seed_generation":generation})
    async with db.connect() as c:
        await c.execution_options(isolation_level="AUTOCOMMIT")
        await maintain_seed_database(c, vacuum=True)
        counts = {m.__tablename__: await c.scalar(select(func.count()).select_from(m)) for m in models+[AiQueryProof]}
        for model in models+[AiQueryProof]:
            multiplier = (20 if model is AiListingFact else template["sources"] if model in (
                ExternalListingSource,AiFactSource,AiListingFactBatch) else 1)
            assert counts[model.__tablename__] == (total+1)*multiplier, f"wrong fixture row count for {model.__tablename__}"
        provider_count=await c.scalar(select(func.count(func.distinct(ExternalListingSource.source_name))))
        assert provider_count == min(10,total+template["sources"])
        metadata = {"listings": total, "counts_including_template": counts,"seed_generation":generation,
            "distinct_providers":provider_count,"observations_per_listing":20,"source_records_per_listing":template["sources"],
            "size_bytes": await c.scalar(text("SELECT pg_database_size(current_database())")),
            "version": await c.scalar(text("SELECT version()")), "postgis": await c.scalar(text("SELECT postgis_full_version()")),
            "settings": [dict(row) for row in (await c.execute(text("SELECT name,setting,unit FROM pg_settings WHERE name IN ('max_connections','shared_buffers','work_mem','effective_cache_size','max_parallel_workers_per_gather','jit','track_io_timing')"))).mappings()]}
        save(f"dataset-{total}.json", metadata)
    await db.dispose()
    log("seed_complete", total=total)


def viewport(count, total, zoom):
    if count == 0:
        return ListingMapRequest(west=-17.5, east=-17.4, south=27.9, north=28.1, zoom=zoom)
    if count <= 302:
        return ListingMapRequest(west=-16.90001, east=-16.9+(count-0.5)*0.0001, south=27.99999, north=28.00001, zoom=zoom)
    return ListingMapRequest(west=-16.90001, east=-16.79999, south=27.99999,
        north=28+((min(count,total)-1)//1000+0.5)*0.0001, zoom=zoom)


def capture_statement(context, statement, parameters):
    # Capture every explicit dispatch during the map call. SET is categorized
    # by our own execution option; query text/CTEs/comments are never filtered.
    return {"category":"transaction-control" if context.execution_options.get("r01_control") else "map-query",
        "sql":statement,"parameters":parameters,"sql_sha256":hashlib.sha256(statement.encode()).hexdigest()}


async def explain_statement(db, statement, parameters):
    async def fetch(prefix):
        async with db.connect() as c:
            await c.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            raw = await c.get_raw_connection()
            value = await raw.driver_connection.fetchval(prefix + statement,*parameters)
            return json.loads(value) if isinstance(value,str) else value
    try:
        return {"status":"actual","plan":await fetch("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ")}
    except Exception as error:  # noqa: BLE001 -- retain diagnostic failures as evidence
        failure = {"analyze_error":{"type":type(error).__name__,"detail":str(error)[:250] or repr(error)}}
    try:
        return {**failure,"status":"estimated-only","plan":await fetch("EXPLAIN (FORMAT JSON) ")}
    except Exception as error:  # noqa: BLE001 -- a double failure must not disappear
        return {**failure,"status":"failed","estimate_error":{"type":type(error).__name__,"detail":str(error)[:250] or repr(error)}}


async def measure(total, samples, candidate=None, baseline_only=False):
    db = engine(pool=30)
    try:
        await measure_dataset(db,total,samples,candidate,baseline_only)
    finally:
        await db.dispose()


async def measure_dataset(db, total, samples, candidate, baseline_only):
    await verify_database_identity(db)
    await preflight_dataset(db, total)
    factory = async_sessionmaker(db, expire_on_commit=False)
    pipe = pipeline(factory)
    # Direct _map_intent measures the complete shared map query/DTO path;
    # HTTP/session overhead is explicitly excluded. Pool waits are included.
    query = VerifiedCardSearch.__new__(VerifiedCardSearch)
    query.pipeline = pipe
    intent = SearchIntent.model_validate_json(json.dumps({"schema_version": "ai-search.v1", "taxonomy_version": "rental.v1", "session_id": str(uuid4()), "version": 1,
        "criteria": {"pets": {"strength": "hard", "value": [{"species": "dog", "size": "small", "count": 1}]}}}))
    captured = []
    capture_active = False
    @event.listens_for(db.sync_engine, "before_cursor_execute")
    def capture(conn, cursor, statement, parameters, context, executemany):
        if capture_active:
            captured.append(capture_statement(context,statement,parameters))
    async def request(view):
        start = time.perf_counter()
        result = {"ok": False, "started_at": now()}
        after_pool = None
        try:
            async with factory() as s, s.begin():
                await s.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY").execution_options(r01_control=True))
                after_pool = time.perf_counter()
                result["pool_ms"] = (after_pool-start)*1000
                value = await query._map_intent(s, intent, view)
                result.update(ok=True, count=sum(getattr(item,"count",1) for item in value.map.items), items=len(value.map.items),
                    pool_ms=(after_pool-start)*1000, query_ms=(time.perf_counter()-after_pool)*1000)
        except Exception as error:  # noqa: BLE001 -- retain every failed load sample
            result.update(error=type(error).__name__, detail=(str(error).splitlines() or [repr(error)])[0][:180],
                sqlstate=getattr(getattr(error,"orig",None),"sqlstate",None))
            if after_pool is not None:
                result["query_ms"] = (time.perf_counter()-after_pool)*1000
        result["ms"] = (time.perf_counter()-start)*1000
        result["ended_at"] = now()
        return result
    records = []
    for count in ([candidate] if candidate is not None else sorted({0,*(min(n,total) for n in (299,300,301,302,10000)),total})):
        for zoom in (8,12,13,21):
            view = viewport(count,total,zoom)
            captured.clear()
            capture_active = True
            try:
                first = await request(view)
            finally:
                capture_active = False
            # Untimed correctness must hold for every successful request.
            if first["ok"]:
                assert first["count"] == count, (count, zoom, first)
            record = {"total":total,"candidates": count, "zoom": zoom, "first_touch": first,
                "started_at":first["started_at"],"ended_at":first["ended_at"],
                "capture_count":len(captured),"query_count":sum(row["category"] == "map-query" for row in captured),
                "plan_count":0,"statements":[{**row,"ordinal":i} for i,row in enumerate(captured)]}
            records.append(record)
            save(f"baseline-{total}.json",records)
            log("baseline", total=total,candidates=count,zoom=zoom,result=first)
            # Explain uses precisely the emitted SQL/binds via asyncpg driver.
            for trace in record["statements"]:
                if trace["category"] != "map-query":
                    continue
                filename = f"plan-{total}-{count}-z{zoom}-{trace['ordinal']}.json"
                plan = await explain_statement(db,trace["sql"],trace["parameters"])
                save(filename,{**plan,"total":total,"candidates":count,"zoom":zoom,
                    "statement_index":trace["ordinal"],"sql_sha256":trace["sql_sha256"],"parameters":trace["parameters"]})
                trace.update(plan_file=filename,plan_status=plan["status"])
                record["plan_count"] += plan["status"] in ("actual","estimated-only")
                save(f"baseline-{total}.json",records)
                log("explain",total=total,candidates=count,zoom=zoom,file=filename,status=plan["status"])
            captured.clear()
    if baseline_only:
        return
    warmed = await asyncio.gather(*(db.connect() for _ in range(30)))
    await asyncio.gather(*(connection.close() for connection in warmed))
    scenarios=[]
    for count in sorted({min(300,total),min(10000,total),total}):
        for concurrency in (50,100,200):
            for zoom in (8,13):
                view=viewport(count,total,zoom)
                results=[]
                started_at = now()
                start=time.perf_counter()
                for offset in range(0,samples,concurrency):
                    results.extend(await asyncio.gather(*(request(view) for _ in range(min(concurrency,samples-offset)))))
                    captured.clear()
                    # At the larger scales a wholly failed first wave already
                    # rejects acceptance. Do not repeatedly saturate the lab to
                    # manufacture a percentile for unfinished SQL statements.
                    if total >= 500000 and offset == 0 and all(not r["ok"] for r in results):
                        break
                values=sorted(r["ms"] for r in results)
                if not values:
                    raise RuntimeError("load scenario produced no samples")
                assert all(not r["ok"] or r["count"] == count for r in results)
                def percentile(q, ordered=values):
                    return ordered[min(len(ordered)-1, math.ceil(q*len(ordered))-1)]
                summary={"total":total,"candidates":count,"zoom":zoom,"concurrency":concurrency,
                    "started_at":started_at,"ended_at":now(),"mode":"load" if samples == 200 else "probe",
                    "samples":len(results),"requested_samples":samples,"stopped_after_failed_wave":len(results)<samples,
                    "seconds":time.perf_counter()-start,"failures":sum(not r["ok"] for r in results),
                    "p50_ms":percentile(.5),"p95_ms":percentile(.95),"p99_ms":percentile(.99),
                    "pass":all(r["ok"] for r in results) and percentile(.95)<=500 and percentile(.99)<=1000,
                    "results":results}
                scenarios.append(summary)
                save(f"load-{total}.json",scenarios)
                log("load",**{k:v for k,v in summary.items() if k!="results"})
    save(f"cancellation-{total}.json", await cancellation_check(db, factory, request, total))


async def preflight_dataset(db, total):
    # Counting up to 20 million fixture facts is setup, outside every timed
    # request. SET LOCAL cannot relax the engine's measured-query deadline.
    async with db.connect() as connection:
        await connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        await connection.execute(text("SET LOCAL statement_timeout='60s'"))
        await validate_dataset(connection, total)


async def cancellation_check(db, factory, request, total):
    # A unique application_name and server-side pg_stat_activity barrier prove
    # all twenty SQL operations were active, even when map queries are instant.
    name = "r01-cancel-" + uuid4().hex
    started_at = now()
    async def controlled():
        async with factory() as s, s.begin():
            await s.execute(text("SELECT set_config('application_name', :name, true)"), {"name": name})
            await s.execute(text("SELECT pg_sleep(4)"))
    tasks = [asyncio.create_task(controlled()) for _ in range(20)]
    active_before = 0
    deadline = time.monotonic() + 3
    try:
        while time.monotonic() < deadline:
            async with db.connect() as c:
                active_before = await c.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:name AND state='active' AND wait_event='PgSleep'"), {"name": name})
            if active_before == 20 or any(task.done() for task in tasks):
                break
            await asyncio.sleep(.01)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    start = time.perf_counter()
    completed_before = sum(task.done() and not task.cancelled() and task.exception() is None for task in tasks)
    accepted = sum(task.cancel() for task in tasks if not task.done())
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)
    async with db.connect() as c:
        active = await c.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:name AND state='active'"), {"name": name})
    return {"tasks":20, "cancel_requested":20, "cancel_accepted":accepted,
        "cancelled":sum(isinstance(result, asyncio.CancelledError) for result in outcomes),
        "completed_before_cancel":completed_before,
        "failed":sum(isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError) for result in outcomes),
        "active_before_cancel":active_before, "remaining_active":active,
        "elapsed_ms":(time.perf_counter()-start)*1000,"started_at":started_at,"ended_at":now(),
        "pool_reusable":(await request(viewport(0,total,8)))["ok"]}


def parse_args(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=["initialize","seed","measure"])
    parser.add_argument("--sources",type=int,choices=(2,10))
    parser.add_argument("--total",type=int,default=100000)
    parser.add_argument("--samples",type=int,default=200)
    parser.add_argument("--candidate",type=int)
    parser.add_argument("--baseline-only",action="store_true")
    args=parser.parse_args(argv)
    if not 1 <= args.total <= 1000000 or not 1 <= args.samples <= 200:
        parser.error("--total must be 1..1000000 and --samples must be 1..200; large runs still require separate approval")
    if args.candidate is not None and not 0 <= args.candidate <= args.total:
        parser.error("--candidate must be between zero and --total")
    if (args.candidate is not None or args.baseline_only) and args.phase != "measure":
        parser.error("--candidate and --baseline-only require the measure phase")
    if args.candidate is not None and not args.baseline_only:
        parser.error("--candidate requires --baseline-only (load always uses the full matrix)")
    if args.sources is not None and args.phase != "initialize":
        parser.error("--sources is only supported for initialize; seed/measure use the immutable experiment profile")
    return args


async def execute_phase(args, sources):
    if args.phase=="initialize": await initialize(sources)
    elif args.phase=="seed":
        control=engine(timeout=0)
        await verify_database_identity(control)
        async with control.begin() as c:
            meta = await c.scalar(text("SELECT data FROM r01_meta"))
            template = json.loads((OUT / "template.json").read_text(encoding="utf-8"))
            if (meta.get("synthetic_only") is not True or meta.get("provenance") != PROVENANCE or
                    meta.get("sources") != sources or template.get("provenance") != PROVENANCE or
                    template.get("sources") != sources or template.get("observations") != 20):
                raise RuntimeError("seed DB provenance mismatch")
            before=await c.scalar(text("SELECT count(*) FROM r01_entities"))
            await c.execute(text("UPDATE r01_meta SET data=jsonb_set(data,'{generation}',to_jsonb(CAST(:generation AS bigint)))"),
                {"generation":meta["generation"] + 1})
            await c.execute(text("ALTER TABLE listings DISABLE TRIGGER listings_catalog_version"))
        try:
            log("fixture_trigger_suspended",note="synthetic bulk setup only; restored before measurement")
            await seed(args.total)
        finally:
            async with control.begin() as c:
                await c.execute(text("ALTER TABLE listings ENABLE TRIGGER listings_catalog_version"))
                after=await c.scalar(text("SELECT count(*) FROM r01_entities"))
                if after>before:
                    await c.execute(text("UPDATE catalog_state SET version=version+:added,updated_at=now() WHERE id=1"),{"added":after-before})
            await control.dispose()
            log("fixture_trigger_restored",inserted=after-before)
    else: await measure(args.total,args.samples,args.candidate,args.baseline_only)


async def main():
    args=parse_args()
    validate_lab_environment()
    OUT.mkdir(exist_ok=True)
    sources = (args.sources or 2) if args.phase == "initialize" else json.loads((OUT / "experiment.json").read_text(encoding="utf-8"))["sources"]
    bind_experiment(sources, args.phase)
    with phase_file_lock():
        metadata={"python":platform.python_version(),"platform":platform.platform(),"sql_timeout_ms":5000,
            "pool":30,"mode":"closed-loop repository map path; excludes HTTP/session", "source":"/code", "synthetic_only":True,
            "code_revision":os.environ.get("R01_CODE_REVISION"),"dependency_image_id":os.environ.get("R01_IMAGE_ID"),"phase":args.phase,"total":args.total,
            "source_provenance":{"mode":os.environ.get("R01_SOURCE_MODE"),"checkout_clean":True,
                "archive_sha256":os.environ.get("R01_SOURCE_ARCHIVE_SHA256")},
            "dependencies":{name:importlib.metadata.version(name) for name in ("SQLAlchemy","asyncpg","pydantic","geoalchemy2","psycopg")},
            "source_hashes":{name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in (
                "/code/scripts/benchmark-ai-map.py","/code/backend/app/repositories/ai_verified_cards.py",
                "/code/backend/app/repositories/ai_query_proofs.py","/code/backend/app/repositories/listings.py")},
            "started_at":now(),"sources":sources,"status":"running"}
        manifest_name = f"runner-{args.phase}-{args.total}-{RUN_ID}.json"
        save(manifest_name,metadata)
        guard_db = engine(timeout=60000)
        try:
            await verify_database_identity(guard_db)
            async with phase_database_guard(guard_db,args.phase,args.total):
                await execute_phase(args,sources)
        except BaseException as error:
            metadata.update(ended_at=now(),status="failed",error=type(error).__name__,detail=str(error)[:250])
            save(manifest_name,metadata)
            raise
        finally:
            await guard_db.dispose()
        metadata.update(ended_at=now(), status="complete")
        save(manifest_name, metadata)


if __name__=="__main__":
    asyncio.run(main())
