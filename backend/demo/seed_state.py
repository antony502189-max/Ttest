"""Resumable immutable snapshot import; no provider traffic or journal reset."""
import asyncio
import copy
import json
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import null, select, text

from app.models import ExternalListingSource, Listing, User
from app.models.ai_fact_pipeline import AiFactJob
from app.models.ai_operating_policy import AiErasureBinding
from app.repositories.ai_fact_snapshots import CapturedParserSnapshot, FactSnapshotReader
from app.repositories.ai_query_proofs import QueryProofs
from app.repositories.listings import point
from app.schemas.ai_fact_bridge import BridgeReference
from app.schemas.ai_fact_pipeline import FactQueuePolicy
from app.schemas.ai_listing_facts import digest
from app.services.ai_erasure_journal import bind_journal
from app.services.ai_pisocompartido_price import prepare_price
from demo.budget import DemoBudget

TABLE = "private_ai_demo_seed_state"
CARD_FIELDS = {"title", "city", "area", "province_code", "rental_mode", "monthly_price", "room_type", "is_external", "primary_source", "primary_source_url", "source_price_text", "source_price_currency", "source_price_period", "source_price_is_from", "external_image_urls", "furnished", "room_capacity", "room_size_m2", "bills_included", "bathroom", "kitchen", "pets_allowed", "smoking_allowed", "children_allowed", "amenities", "restrictions", "published_at"}
SOURCE_FIELDS = {"source_name", "external_id", "source_url", "source_price_text", "current_status", "last_success_at", "last_checked_at", "content_updated_at", "last_state_check_at", "last_state_check_result", "normalized_payload"}
DATES = {"last_success_at", "last_checked_at", "content_updated_at", "last_state_check_at", "published_at"}


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("DEMO_SNAPSHOT_TIMESTAMP_INVALID")
    return result


def validated_snapshot(snapshot):
    value = copy.deepcopy(snapshot)
    timestamp(value["snapshot_at"])
    records = value["records"]
    if type(records) is not list or not 1 <= len(records) <= 20:
        raise ValueError("BOUNDED_REAL_SNAPSHOT_REQUIRED")
    listings, sources = set(), set()
    for record in records:
        card, source = record["listing"], record["source"]
        lid, sid = UUID(card.pop("id")), UUID(source.pop("id"))
        if lid in listings or sid in sources or not set(card) <= CARD_FIELDS | {"latitude", "longitude"} or not set(source) <= SOURCE_FIELDS:
            raise ValueError("DEMO_SNAPSHOT_DUPLICATE_OR_UNEXPECTED_FIELD")
        listings.add(lid)
        sources.add(sid)
        lat, lng = card.pop("latitude"), card.pop("longitude")
        if (lat is None) != (lng is None) or (lat is not None and (
                type(lat) not in {int, float} or type(lng) not in {int, float} or not -90 <= lat <= 90 or not -180 <= lng <= 180)):
            raise ValueError("DEMO_PUBLIC_POSITION_INVALID")
        reference = BridgeReference(source_record_id=sid, canonical_listing_id=lid,
            source_identifier=f"PisoCompartido:{sid.hex}", snapshot_hash="a" * 64)
        prepare_price(CapturedParserSnapshot(reference, "{}", json.dumps(source["normalized_payload"]), source["source_price_text"]))
        if (card["monthly_price"] != source["normalized_payload"]["price_amount"] or card["rental_mode"] != "long"
                or card["primary_source"] != "PisoCompartido" or card["is_external"] is not True
                or source["current_status"] != "active"):
            raise ValueError("DEMO_SNAPSHOT_CARD_DISAGREEMENT")
        for fields in (card, source):
            for key in DATES & fields.keys():
                if fields[key] is not None:
                    fields[key] = timestamp(fields[key])
        record.update(lid=lid, sid=sid, latitude=lat, longitude=lng)
    return sorted(records, key=lambda r: r["sid"].hex)


def signing_keys(path: Path, snapshot_hash: str):
    if not path.exists():
        temporary = path.with_name(".signing-" + uuid4().hex + ".tmp")
        data = {"guest": secrets.token_hex(32), "cursor": secrets.token_hex(32), "seed_snapshot_sha256": snapshot_hash}
        try:
            with temporary.open("xb") as stream:
                os.chmod(temporary, 0o600)
                stream.write(json.dumps(data, sort_keys=True).encode())
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path)  # Atomic publish, never replace existing signing keys.
            if os.name != "nt":
                fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            temporary.unlink(missing_ok=True)
    if path.is_symlink():
        raise ValueError("DEMO_SIGNING_STATE_INVALID")
    keys = json.loads(path.read_bytes())
    if (set(keys) != {"guest", "cursor", "seed_snapshot_sha256"} or keys["seed_snapshot_sha256"] != snapshot_hash
            or any(not re.fullmatch(r"[0-9a-f]{64}", keys[k]) for k in ("guest", "cursor"))
            or keys["guest"] == keys["cursor"]):
        raise ValueError("DEMO_SIGNING_STATE_INVALID")
    return keys


async def verify_completed(factory, keys):
    async with factory() as session:
        row = (await session.execute(text(f"SELECT snapshot_hash,phase,signing_hash,budget_ready FROM {TABLE} WHERE id=1"))).first()
        if (row is None or row.phase != "completed" or row.snapshot_hash != keys.get("seed_snapshot_sha256")
                or row.signing_hash != digest(keys) or not row.budget_ready):
            raise ValueError("DEMO_SEED_NOT_COMPLETED")


async def noop(_name):
    pass


async def verify_catalog(factory, records, host_id):
    async with factory() as session:
        if set(await session.scalars(select(Listing.id))) != {r["lid"] for r in records} or set(
                await session.scalars(select(ExternalListingSource.id))) != {r["sid"] for r in records}:
            raise ValueError("DEMO_EXISTING_CATALOG_MISMATCH")
        for record in records:
            card, source = await session.get(Listing, record["lid"]), await session.get(ExternalListingSource, record["sid"])
            if card.owner_user_id != host_id or card.status != "published" or card.deleted_at is not None or source.canonical_listing_id != record["lid"]:
                raise ValueError("DEMO_EXISTING_CATALOG_MISMATCH")
            for obj, fields in ((card, record["listing"]), (source, record["source"])):
                for key, expected in fields.items():
                    actual = getattr(obj, key)
                    equal = actual == expected if isinstance(expected, datetime) else digest({"v": actual}) == digest({"v": expected})
                    if not equal:
                        raise ValueError("DEMO_EXISTING_CATALOG_MISMATCH")
            if source.fingerprint != digest(source.normalized_payload):
                raise ValueError("DEMO_EXISTING_CATALOG_MISMATCH")
            position = (await session.execute(text("SELECT ST_X(location::geometry),ST_Y(location::geometry) "
                "FROM listings WHERE id=:id"), {"id": record["lid"]})).one()
            expected_position = record["longitude"], record["latitude"]
            if any((actual is None) != (expected is None) or (actual is not None and abs(actual - expected) > 1e-9)
                   for actual, expected in zip(position, expected_position, strict=True)):
                raise ValueError("DEMO_EXISTING_CATALOG_MISMATCH")


async def seed_catalog(engine, factory, snapshot, state_dir: Path, journal_factory, *,
                       database_name="ai_text_demo_20261108", checkpoint=noop, budget_factory=DemoBudget):
    from app.core.security import hash_password
    from demo.entry import BINDING, pipeline
    records, snapshot_hash = validated_snapshot(snapshot), digest(snapshot)
    if database_name != "ai_text_demo_20261108" and not database_name.startswith("ai_demo_seed_test_"):
        raise ValueError("DEMO_DATABASE_REQUIRED")
    state_dir.mkdir(parents=True, exist_ok=True)
    async with engine.connect() as lock:
        if await lock.scalar(text("SELECT current_database()")) != database_name:
            raise ValueError("DEMO_DATABASE_REQUIRED")
        await lock.execute(text("SELECT pg_advisory_lock(hashtextextended(current_database() || '/private-demo-seed.v1',0))"))
        await lock.commit()
        try:
            await lock.execute(text(f"CREATE TABLE IF NOT EXISTS {TABLE}(id integer PRIMARY KEY CHECK(id=1),"
                "snapshot_hash text NOT NULL,phase text NOT NULL CHECK(phase IN ('starting','imported','proofs_ready','completed')),"
                "host_id uuid NOT NULL,signing_hash text,budget_ready boolean NOT NULL DEFAULT false)"))
            row = (await lock.execute(text(f"SELECT * FROM {TABLE} WHERE id=1"))).first()
            if row is None:
                async with factory() as session:
                    occupied = await session.scalar(select(Listing.id).limit(1)) or await session.scalar(select(ExternalListingSource.id).limit(1))
                if occupied or any((state_dir / name).exists() for name in ("signing.json", "provider.sqlite3", "erasure.sqlite3")):
                    raise ValueError("DEMO_UNMANAGED_STATE_REFUSED")
                await lock.execute(text(f"INSERT INTO {TABLE}(id,snapshot_hash,phase,host_id) VALUES(1,:hash,'starting',:host)"),
                                   {"hash": snapshot_hash, "host": uuid4()})
            elif row.snapshot_hash != snapshot_hash:
                raise ValueError("DEMO_SNAPSHOT_BINDING_MISMATCH")
            await lock.commit()
            await checkpoint("starting")
            row = (await lock.execute(text(f"SELECT * FROM {TABLE} WHERE id=1"))).first()
            await lock.commit()
            if row.signing_hash is not None and not (state_dir / "signing.json").is_file():
                raise ValueError("DEMO_SIGNING_STATE_REQUIRED")
            keys = signing_keys(state_dir / "signing.json", snapshot_hash)
            if row.signing_hash is not None and row.signing_hash != digest(keys):
                raise ValueError("DEMO_SIGNING_STATE_INVALID")
            await lock.execute(text(f"UPDATE {TABLE} SET signing_hash=:hash WHERE id=1"), {"hash": digest(keys)})
            await lock.commit()
            await checkpoint("keys_ready")
            async with factory() as session:
                bound = await session.get(AiErasureBinding, 1)
            journal = journal_factory(initialize=bound is None and row.phase == "starting")
            if journal is None:
                raise ValueError("AI_ERASURE_JOURNAL_REQUIRED")
            await bind_journal(factory, journal, initialize=bound is None and row.phase == "starting")
            budget = budget_factory(state_dir / "provider.sqlite3", corpus_sha256=BINDING, initialize=not row.budget_ready)
            if row.phase != "completed" and budget.summary()["attempts"]:
                raise ValueError("DEMO_INCOMPLETE_SEED_HAS_PROVIDER_ATTEMPTS")
            await checkpoint("budget_ready")
            await lock.execute(text(f"UPDATE {TABLE} SET budget_ready=true WHERE id=1"))
            await lock.commit()
            await checkpoint("journal_bound")
            if row.phase == "starting":
                async with factory.begin() as session:
                    session.add(User(id=row.host_id, email="catalog@closed-demo.invalid", name="PisoCompartido", role="host",
                        initials="PC", email_verified=True, password_hash=hash_password(secrets.token_urlsafe(40))))
                    await session.flush()
                    for record in records:
                        # ORM defaults otherwise replace explicit source NULL
                        # with e.g. furnished=true or room_size_m2=1.
                        fields = {k: null() if v is None else v for k, v in record["listing"].items()}
                        session.add(Listing(id=record["lid"], owner_user_id=row.host_id, **fields,
                            location=point(record["longitude"], record["latitude"]) if record["latitude"] is not None else None,
                            status="published", description="", approximate_address=""))
                        await session.flush()
                        await checkpoint("importing")
                        session.add(ExternalListingSource(id=record["sid"], canonical_listing_id=record["lid"],
                            **record["source"], raw_payload={}, fingerprint=digest(record["source"]["normalized_payload"])))
                    await session.execute(text(f"UPDATE {TABLE} SET phase='imported' WHERE id=1"))
            await checkpoint("imported")
            await verify_catalog(factory, records, row.host_id)
            if row.phase == "completed":
                # A completed rerun is verification only: never regress durable
                # phases or rebuild proofs after the approved calls were spent.
                await verify_completed(factory, keys)
                return {"real_snapshot_records": len(records), "prepared": len(records), "snapshot_at": snapshot["snapshot_at"], "model_calls": 0}
            service = pipeline(factory)
            service.policy = FactQueuePolicy(lease_seconds=10, max_attempts=2, retry_delay_seconds=1)
            reader, proofs = FactSnapshotReader(factory, max_payload_bytes=65536), QueryProofs(service)
            for record in records:
                ready = prepare_price(await reader.capture(record["sid"]))
                job_id = await service.observe(ready.source)
                await checkpoint("observed")
                while True:
                    async with factory() as session:
                        job = await session.get(AiFactJob, job_id)
                        now = await session.scalar(text("SELECT clock_timestamp()"))
                    if job is None or job.status in {"failed", "superseded"}:
                        raise ValueError("DEMO_FACT_JOB_RECONCILIATION_REQUIRED")
                    if job.status == "succeeded":
                        break
                    if job.status == "running" and job.lease_until > now:
                        await asyncio.sleep(min(.2, max(.01, (job.lease_until - now).total_seconds())))
                        continue
                    claim = await service.claim(source_name="PisoCompartido")
                    if claim is None or claim.job_id != job_id:
                        raise ValueError("DEMO_FACT_JOB_RECONCILIATION_REQUIRED")
                    await checkpoint("claimed")
                    async with factory() as session:
                        now = await session.scalar(text("SELECT clock_timestamp()"))
                    receipt = await service.complete(claim, ready.to_batch(claim, observed_at=now), ready.sanitized_fields)
                    if receipt.status != "succeeded":
                        raise ValueError("DEMO_REAL_PROOF_FAILED")
                    break
                await checkpoint("facts_ready")
                if not await proofs.prepare(record["lid"]):
                    raise ValueError("DEMO_REAL_PROOF_FAILED")
                await checkpoint("proof_ready")
            await lock.execute(text(f"UPDATE {TABLE} SET phase='proofs_ready' WHERE id=1"))
            await lock.commit()
            await checkpoint("proofs_ready")
            await lock.execute(text(f"UPDATE {TABLE} SET phase='completed' WHERE id=1"))
            await lock.commit()
            await checkpoint("completed")
            return {"real_snapshot_records": len(records), "prepared": len(records), "snapshot_at": snapshot["snapshot_at"], "model_calls": 0}
        finally:
            await lock.rollback()
            await lock.execute(text("SELECT pg_advisory_unlock(hashtextextended(current_database() || '/private-demo-seed.v1',0))"))
            await lock.commit()
