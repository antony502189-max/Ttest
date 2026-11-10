"""Closed-cohort reconcile; only a completely prepared generation is readable."""

import argparse
import asyncio
import json
import sys
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, text

from app.models import ExternalListingSource, Listing
from app.models.ai_fact_pipeline import AiFactJob
from app.models.ai_query_proof import AiQueryProof
from app.repositories.ai_fact_snapshots import FactSnapshotReader
from app.repositories.ai_query_proofs import QueryProofs
from app.repositories.listings import point
from app.schemas.ai_listing_facts import digest
from app.services.ai_pisocompartido_price import prepare_price
from demo.entry import pipeline
from demo.seed_state import CARD_FIELDS, timestamp, validated_snapshot
from pilot.catalog_health import CatalogHealth, cohort_hash


async def noop(_phase, _index):
    pass


def receipt(original, incoming):
    cohort = validated_snapshot(original)
    expected = {(r["lid"], r["sid"]) for r in cohort}
    v2 = incoming.get("schema") == "pilot-cohort.v2"
    if set(incoming) != (
        {"schema", "cohort", "records", "tombstones", "snapshot_at"} if v2 else {"records", "snapshot_at"}
    ):
        raise ValueError("PILOT_REFRESH_RECEIPT_INVALID")
    if not isinstance(incoming["records"], list):
        raise TypeError("PILOT_REFRESH_RECEIPT_INVALID")
    records = validated_snapshot(incoming) if incoming["records"] else []
    price_fields={'source_name','source_price_text','rental_mode','price_currency','price_period','price_is_from','price_amount'}
    if any(set(r['source']['normalized_payload'])!=price_fields for r in records):
        raise ValueError('PILOT_REFRESH_SOURCE_FIELDS_INVALID')
    active = {(r["lid"], r["sid"]) for r in records}
    removed = []
    if v2:
        manifest = [(UUID(r["listing_id"]), UUID(r["source_id"])) for r in incoming["cohort"]]
        if len(manifest) != len(expected) or set(manifest) != expected:
            raise ValueError("PILOT_REFRESH_COHORT_MISMATCH")
        for item in incoming["tombstones"]:
            if set(item) != {"listing_id", "source_id", "reason"} or item["reason"] != "ineligible":
                raise ValueError("PILOT_REFRESH_TOMBSTONE_INVALID")
            removed.append((UUID(item["listing_id"]), UUID(item["source_id"])))
        for r in records:
            if set(r["listing"]) != CARD_FIELDS:
                raise ValueError("PILOT_REFRESH_PUBLIC_FIELDS_INCOMPLETE")
    if active & set(removed) or len(removed) != len(set(removed)) or active | set(removed) != expected:
        raise ValueError("PILOT_REFRESH_COHORT_MISMATCH")
    return records, removed


async def refresh(factory, original, incoming, *, health, token=None, checkpoint=noop):
    if health.cohort_hash != cohort_hash(original):
        raise ValueError("PILOT_REFRESH_COHORT_MISMATCH")
    facts = pipeline(factory)
    async with factory() as lock:
        locked = await lock.scalar(
            text("SELECT pg_try_advisory_lock(hashtextextended(current_database() || '/pilot-refresh.v1',0))")
        )
        if not locked:
            raise ValueError("PILOT_REFRESH_ALREADY_RUNNING")
        claim = None
        try:
            if token is None:
                token = health.begin()
            else:
                state = health._read()
                if state["token"] != token or state["phase"] != "refreshing":
                    raise ValueError("PILOT_REFRESH_FENCED")
            records, removed = receipt(original, incoming)
            captured = timestamp(incoming["snapshot_at"])
            original_sources = {UUID(r["source"]["id"]): r["source"] for r in original["records"]}
            async with factory.begin() as session:
                now = await session.scalar(text("SELECT clock_timestamp()"))
                if not now - timedelta(minutes=10) <= captured <= now:
                    raise ValueError("PILOT_REFRESH_RECEIPT_EXPIRED")
                for r in records:
                    source = r["source"]
                    observed = source["last_success_at"]
                    checked = source.get("last_checked_at")
                    if not now - timedelta(seconds=86400) <= observed <= captured or (
                        checked
                        and checked > observed
                        and (
                            source.get("last_state_check_result") != "active"
                            or source.get("last_state_check_at") != checked
                            or checked > captured
                        )
                    ):
                        raise ValueError("PILOT_REFRESH_SOURCE_NOT_FRESH")
                    row = await session.get(ExternalListingSource, r["sid"], with_for_update=True)
                    card = await session.get(Listing, r["lid"], with_for_update=True)
                    if (
                        row is None
                        or card is None
                        or row.canonical_listing_id != r["lid"]
                        or source["source_url"] != original_sources[r["sid"]]["source_url"]
                        or row.source_url != source["source_url"]
                        or row.source_name != "PisoCompartido"
                        or card.deleted_at is not None
                        or card.status not in {"published", "draft"}
                    ):
                        raise ValueError("PILOT_REFRESH_IDENTITY_MISMATCH")
                    if row.last_success_at and row.last_success_at > observed:
                        raise ValueError("PILOT_REFRESH_OBSERVATION_ROLLBACK")
                    for key, value in r["listing"].items():
                        setattr(card, key, value)
                    card.location = point(r["longitude"], r["latitude"]) if r["latitude"] is not None else None
                    card.status = "published"
                    for key, value in source.items():
                        setattr(row, key, value)
                    row.raw_payload = {
                        "pilot_import_observation.v2": {
                            "observed_at": observed.isoformat(),
                            "public_payload_sha256": digest(
                                {
                                    "listing": {
                                        k: v.isoformat() if isinstance(v, datetime) else v
                                        for k, v in r["listing"].items()
                                    },
                                    "source": source["normalized_payload"],
                                    "latitude": r["latitude"],
                                    "longitude": r["longitude"],
                                }
                            ),
                        }
                    }
                    row.fingerprint = digest(source["normalized_payload"])
                for lid, sid in removed:
                    row = await session.get(ExternalListingSource, sid, with_for_update=True)
                    card = await session.get(Listing, lid, with_for_update=True)
                    if row is None or card is None or row.canonical_listing_id != lid:
                        raise ValueError("PILOT_REFRESH_IDENTITY_MISMATCH")
                    card.status = "draft"
                    row.current_status = "inactive"
                    await session.execute(delete(AiQueryProof).where(AiQueryProof.canonical_listing_id == lid))
            await checkpoint("source_commit", 0)
            for lid, _ in removed:
                await facts.reconcile_listing(lid)
            reader = FactSnapshotReader(factory, max_payload_bytes=65536)
            proofs = QueryProofs(facts)
            for index, r in enumerate(records):
                prepared = prepare_price(await reader.capture(r["sid"]))
                job_id = await facts.observe(prepared.source)
                await checkpoint("observe", index)
                async with factory() as session:
                    job = await session.get(AiFactJob, job_id)
                if job is None:
                    raise ValueError("PILOT_REFRESH_JOB_MISSING")
                if job.status == "failed":
                    # At most one replacement per source/run; old failures and
                    # attempts remain immutable. No provider work is scheduled.
                    job_id = await facts.restart_failed_job(job_id)
                if job.status != "succeeded":
                    deadline = asyncio.get_running_loop().time() + 75
                    while claim is None:
                        claim = await facts.claim(source_name="PisoCompartido", job_id=job_id)
                        if claim is not None:
                            break
                        async with factory() as session:
                            job = await session.get(AiFactJob, job_id)
                        if job is None or job.status in {"failed", "superseded"}:
                            raise ValueError("PILOT_REFRESH_JOB_FAILED")
                        if asyncio.get_running_loop().time() >= deadline:
                            raise ValueError("PILOT_REFRESH_JOB_TIMEOUT")
                        await asyncio.sleep(0.1)
                    await checkpoint("claimed", index)
                    result = await facts.complete(
                        claim,
                        prepared.to_batch(claim, observed_at=r["source"]["last_success_at"]),
                        prepared.sanitized_fields,
                    )
                    claim = None
                    if result.status != "succeeded":
                        raise ValueError("PILOT_REFRESH_FACTS_FAILED")
                await checkpoint("complete", index)
            for index, r in enumerate(records):
                if not await proofs.prepare(r["lid"]):
                    raise ValueError("PILOT_REFRESH_PROOF_FAILED")
                await checkpoint("proof", index)
            health.publish(token, snapshot_at=incoming["snapshot_at"], active=len(records), removed=len(removed))
            return {
                "refreshed": len(records),
                "removed": len(removed),
                "snapshot_at": incoming["snapshot_at"],
                "generation": health._read()["generation"],
                "provider_calls": 0,
                "reseed": False,
            }
        except BaseException:
            if token is not None:
                health.fail(token)
            if claim is not None:
                with suppress(Exception):
                    await facts.fail(claim, retryable=True, code="EXTRACTOR_FAILED")
            raise
        finally:
            await lock.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(current_database() || '/pilot-refresh.v1',0))")
            )
            await lock.commit()


async def main():
    from app.db.session import SessionLocal
    from pilot.entry import require_pilot

    require_pilot()
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt")
    parser.add_argument("--token")
    args = parser.parse_args()
    original = json.loads(Path("/demo-input/catalog.json").read_text())
    health = CatalogHealth(Path("/demo-state/catalog-health.json"), cohort_hash(original))
    incoming = json.loads(sys.stdin.read() if args.receipt == "-" else Path(args.receipt).read_text())
    print(json.dumps(await refresh(SessionLocal, original, incoming, health=health, token=args.token)))


if __name__ == "__main__":
    asyncio.run(main())
