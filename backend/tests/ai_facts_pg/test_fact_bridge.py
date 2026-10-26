"""Coherent capture -> injected fixture builder -> actual AI-04 transactions."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.models.ai_fact_pipeline import AiFactJob, AiFactRematchEvent, AiFactSource
from app.models.ai_listing_facts import AiListingFact, AiListingSearchFeatures
from app.repositories.ai_fact_snapshots import FactSnapshotReader
from app.schemas.ai_fact_bridge import BridgeMapping, BridgeRejected, ParserEvidencePacket
from app.schemas.ai_fact_pipeline import SourceIdentityConflict
from app.services.ai_fact_bridge import prepare_captured_source

pytestmark = pytest.mark.integration
CASES = json.loads((Path(__file__).parents[1] / "fixtures/ai_fact_bridge/parser-373-synthetic.json").read_text(encoding="utf-8"))


def rules():
    return BridgeMapping(structured_fields={"rules.pets": "pets_allowed", "details.unit_capacity": "room_capacity"},
                         rented_unit_capacity_fields=frozenset({"details.unit_capacity"}), text_capacity_scope=None,
                         structured_smoking_scopes={}, text_smoking_scopes={"smoking_outdoors_allowed": "terrace"},
                         amenity_codes={})


async def seed_snapshot(pipeline, case="pets_deny", *, listing_id=None):
    _, sessions = pipeline
    listing_id, source_id = listing_id or uuid4(), uuid4()
    packet = next(c["packet"] for c in CASES["cases"] if c["name"] == case)
    async with sessions() as session, session.begin():
        await session.execute(text("INSERT INTO listings(id,status) VALUES(:id,'published') ON CONFLICT DO NOTHING"),
                              {"id": listing_id})
        await session.execute(text("INSERT INTO external_listing_sources "
                                   "(id,canonical_listing_id,fingerprint,current_status,raw_payload,normalized_payload, "
                                   "last_success_at,content_updated_at) VALUES(:id,:listing,:hash,'active',CAST(:raw AS jsonb),"
                                   "CAST(:normalized AS jsonb),clock_timestamp(),clock_timestamp()-interval '1 day')"),
                              {"id": source_id, "listing": listing_id, "hash": "c" * 64,
                               "raw": json.dumps({"private_fixture_marker": "NEVER_EXPORT_PRIVATE_FIXTURE", "contact": "fixture@example.invalid"}),
                               "normalized": json.dumps({"fixture_sanitized_packet": packet, "furnished": True,
                                                         "pets_allowed": False, "deposit_amount": 0, "room_capacity": 1})})
    return source_id, listing_id


def fixture_builder(snapshot):
    # Test double only: the stored fixture was already sanitized by #373's
    # pinned historical builder. This is not a production minimizer.
    value = json.loads(snapshot.normalized_json)["fixture_sanitized_packet"]
    value.update(source_identifier=snapshot.reference.source_identifier,
                 canonical_listing_identifier=str(snapshot.reference.canonical_listing_id))
    return ParserEvidencePacket.model_validate_json(json.dumps(value))


async def prepare(pipeline, source_id, *, builder=fixture_builder, max_bytes=131_072):
    service, sessions = pipeline
    return await prepare_captured_source(FactSnapshotReader(sessions, max_payload_bytes=max_bytes), source_id,
        builder=builder, mapping=rules(), vocabulary=service.vocabulary, extractor_version="fixture-bridge.v1")


async def count(pipeline, model):
    async with pipeline[1]() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_coherent_snapshot_prepares_claim_and_commits_original_negative(pipeline):
    service, sessions = pipeline
    source_id, listing_id = await seed_snapshot(pipeline)
    ready = await prepare(pipeline, source_id)
    await service.observe(ready.source)
    claim = await service.claim()
    batch = ready.to_batch(claim, observed_at=datetime.now(UTC))
    receipt = await service.complete(claim, batch, ready.sanitized_fields)
    assert receipt.status == "succeeded"
    assert await service.complete(claim, batch, ready.sanitized_fields) == receipt
    async with sessions() as session:
        row = await session.get(AiListingSearchFeatures, listing_id)
        pets = next(f for f in row.features if f["key"] == "pets")
        assert pets["status"] == "explicit_deny"
        facts = (await session.scalars(select(AiListingFact))).all()
        assert not any(f.key in {"furnished", "deposit", "capacity_total", "available_spots"} for f in facts)
        assert all("NEVER_EXPORT_PRIVATE_FIXTURE" not in json.dumps(f.evidence) for f in facts)
    assert await count(pipeline, AiFactRematchEvent) == 2
    assert "fixture@example.invalid" not in str(ready.sanitized_fields)


async def test_capture_uses_same_pg_snapshot_hash_and_hides_raw_from_repr(pipeline):
    service, sessions = pipeline
    source_id, listing_id = await seed_snapshot(pipeline)
    captured = await FactSnapshotReader(sessions, max_payload_bytes=131_072).capture(source_id)
    async with sessions() as session, session.begin():
        _, authority = await service._authority(session, listing_id)
        assert captured.reference.snapshot_hash == authority[source_id].snapshot_hash
    assert "NEVER_EXPORT_PRIVATE_FIXTURE" not in repr(captured)
    assert "fixture@example.invalid" not in repr(captured)
    assert captured.reference.source_identifier == f"synthetic:{source_id.hex}"


async def test_builder_runs_after_capture_releases_source_lock(pipeline):
    _, sessions = pipeline
    source_id, _ = await seed_snapshot(pipeline)
    captured = await FactSnapshotReader(sessions, max_payload_bytes=131_072).capture(source_id)
    async with sessions() as session, session.begin():
        # NOWAIT would raise if capture leaked a transaction/row lock.
        await session.execute(text("SELECT id FROM external_listing_sources WHERE id=:id FOR UPDATE NOWAIT"), {"id": source_id})
    assert fixture_builder(captured).source_identifier == captured.reference.source_identifier


async def test_update_between_capture_and_observe_rejects_old_input(pipeline):
    service, sessions = pipeline
    source_id, _ = await seed_snapshot(pipeline)
    ready = await prepare(pipeline, source_id)
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET raw_payload=jsonb_build_object('new_revision',true)"))
    with pytest.raises(SourceIdentityConflict, match="before observe"):
        await service.observe(ready.source)
    assert await count(pipeline, AiFactJob) == 0


async def test_same_sanitized_content_new_snapshot_gets_new_generation_without_raw_in_mapping(pipeline):
    service, sessions = pipeline
    source_id, _ = await seed_snapshot(pipeline)
    old = await prepare(pipeline, source_id)
    await service.observe(old.source)
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET raw_payload=jsonb_build_object('unselected_metadata',true)"))
    new = await prepare(pipeline, source_id)
    assert old.source.content_hash == new.source.content_hash
    assert old.source.snapshot_hash != new.source.snapshot_hash
    await service.observe(new.source)
    async with sessions() as session:
        assert (await session.get(AiFactSource, source_id)).generation == 2
    assert "unselected_metadata" not in str(new.sanitized_fields)


async def test_structured_and_text_conflict_survives_whole_bridge_and_resolver(pipeline):
    service, sessions = pipeline
    source_id, listing_id = await seed_snapshot(pipeline, "structured_text_conflict")
    ready = await prepare(pipeline, source_id)
    await service.observe(ready.source)
    claim = await service.claim()
    await service.complete(claim, ready.to_batch(claim, observed_at=datetime.now(UTC)), ready.sanitized_fields)
    async with sessions() as session:
        row = await session.get(AiListingSearchFeatures, listing_id)
        pets = next(f for f in row.features if f["key"] == "pets")
        assert pets["status"] == "conflict" and pets["typed_value"] is None
        assert len(pets["supporting_fact_ids"]) == 2


@pytest.mark.parametrize("change", ["source_missing", "source_retired", "listing_hidden", "listing_missing"])
async def test_capture_fail_closed_for_missing_or_inactive_source_identity(pipeline, change):
    _, sessions = pipeline
    source_id, _ = await seed_snapshot(pipeline)
    async with sessions() as session, session.begin():
        if change == "source_missing":
            await session.execute(text("DELETE FROM external_listing_sources"))
        elif change == "source_retired":
            await session.execute(text("UPDATE external_listing_sources SET current_status='missing'"))
        elif change == "listing_hidden":
            await session.execute(text("UPDATE listings SET status='hidden'"))
        else:
            await session.execute(text("DELETE FROM listings"))
    with pytest.raises(BridgeRejected, match="SOURCE_SNAPSHOT_UNAVAILABLE"):
        await prepare(pipeline, source_id)


async def test_capture_payload_limit_uses_pg_bytes_without_truncation(pipeline):
    source_id, _ = await seed_snapshot(pipeline)
    with pytest.raises(BridgeRejected, match="SOURCE_SNAPSHOT_UNAVAILABLE"):
        await prepare(pipeline, source_id, max_bytes=32)
    assert await count(pipeline, AiFactJob) == 0


async def test_builder_failure_is_redacted_and_cannot_fall_back_to_scalar_defaults(pipeline):
    source_id, _ = await seed_snapshot(pipeline)

    def rejecting_builder(snapshot):
        raise RuntimeError(snapshot.raw_json)

    with pytest.raises(BridgeRejected) as error:
        await prepare(pipeline, source_id, builder=rejecting_builder)
    assert str(error.value) == "SANITIZED_BUILDER_REJECTED"
    assert "NEVER_EXPORT_PRIVATE_FIXTURE" not in repr(error.value)
    assert await count(pipeline, AiFactJob) == 0


async def test_mismatched_builder_routing_is_rejected_before_any_job(pipeline):
    source_id, _ = await seed_snapshot(pipeline)

    def mismatched(snapshot):
        data = fixture_builder(snapshot).model_dump() | {"canonical_listing_identifier": uuid4()}
        return ParserEvidencePacket.model_validate(data)

    with pytest.raises(BridgeRejected, match="PACKET_IDENTITY_MISMATCH"):
        await prepare(pipeline, source_id, builder=mismatched)
    assert await count(pipeline, AiFactJob) == 0


async def test_no_default_minimizer_or_background_ingest_is_available(pipeline):
    _, sessions = pipeline
    source_id, _ = await seed_snapshot(pipeline)
    with pytest.raises(TypeError):
        await prepare_captured_source(FactSnapshotReader(sessions, max_payload_bytes=131_072), source_id)
    assert await count(pipeline, AiFactJob) == 0
