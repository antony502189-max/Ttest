"""Single-snapshot authority reads on disposable synthetic sources."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_fact_pipeline import count, fake_extract, seed

from app.models.ai_fact_pipeline import AiFactCatalog, AiFactJob, AiFactRematchEvent
from app.models.ai_listing_facts import AiListingFact
from app.repositories.ai_fact_pipeline import FactPipeline
from app.schemas.ai_listing_facts import FactVocabulary

pytestmark = pytest.mark.integration


async def completed(pipeline):
    service, _ = pipeline
    source = await seed(pipeline)
    await service.observe(source)
    claim = await service.claim()
    await service.complete(claim, fake_extract(claim), {"description": "Pets allowed"})
    return source


async def test_current_read_is_detached_and_has_no_writes(pipeline, monkeypatch):
    service, _ = pipeline
    source = await completed(pipeline)
    before = [await count(pipeline, model) for model in (AiFactCatalog, AiFactJob, AiFactRematchEvent, AiListingFact)]
    original = service._projection_inputs

    async def inspect(session, *args):
        assert await session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        assert await session.scalar(text("SHOW transaction_read_only")) == "on"
        return await original(session, *args)

    monkeypatch.setattr(service, "_projection_inputs", inspect)
    first = await service.read_current_projection(source.canonical_listing_id)
    assert first is not None and first.features[0].status == "explicit_allow"
    first.features.clear()
    assert len((await service.read_current_projection(source.canonical_listing_id)).features) == 1
    assert [await count(pipeline, model) for model in (AiFactCatalog, AiFactJob, AiFactRematchEvent, AiListingFact)] == before
    assert await service.read_current_projection(uuid4()) is None
    assert await count(pipeline, AiFactCatalog) == 1


@pytest.mark.parametrize("change", [
    "raw_payload", "normalized_payload", "price", "fingerprint", "retire", "delete", "remap",
    "hide", "delete_listing", "new_source", "new_generation", "missing_projection", "revision",
    "corrupt_projection", "invalid_projection", "corrupt_fact", "corrupt_batch",
])
async def test_stored_projection_does_not_survive_authority_or_evidence_change(pipeline, change):
    service, sessions = pipeline
    source = await completed(pipeline)
    if change == "new_source":
        await seed(pipeline, listing_id=source.canonical_listing_id)
    elif change == "new_generation":
        # A pending generation must not be interpreted as verified zero results.
        await service.observe(source.model_copy(update={"extractor_version": "fake.v2"}))
    else:
        statements = {
            "raw_payload": "UPDATE external_listing_sources SET raw_payload=jsonb_build_object('changed',true)",
            "normalized_payload": "UPDATE external_listing_sources SET normalized_payload=jsonb_build_object('changed',true)",
            "price": "UPDATE external_listing_sources SET source_price_text='changed synthetic price'",
            "fingerprint": "UPDATE external_listing_sources SET fingerprint=repeat('b',64)",
            "retire": "UPDATE external_listing_sources SET current_status='removed'",
            "delete": "DELETE FROM external_listing_sources",
            "remap": "UPDATE external_listing_sources SET canonical_listing_id=:new_id",
            "hide": "UPDATE listings SET status='hidden'",
            "delete_listing": "DELETE FROM listings",
            "missing_projection": "DELETE FROM ai_listing_search_features",
            "revision": "UPDATE ai_fact_catalogs SET revision=revision+1",
            "corrupt_projection": "UPDATE ai_listing_search_features SET features='[]'::jsonb",
            "invalid_projection": "UPDATE ai_listing_search_features SET features=jsonb_build_array(jsonb_build_object('bad',true))",
            "corrupt_fact": "UPDATE ai_listing_facts SET typed_value=jsonb_build_object('kind','policy','allowed',false)",
            "corrupt_batch": "UPDATE ai_listing_fact_batches SET extractor_version='different.v1'",
        }
        async with sessions() as session, session.begin():
            await session.execute(text(statements[change]), {"new_id": uuid4()})
    assert await service.read_current_projection(source.canonical_listing_id) is None


async def test_retired_peer_requires_reconciliation_then_keeps_active_support(pipeline):
    service, sessions = pipeline
    source = await completed(pipeline)
    second = await seed(pipeline, listing_id=source.canonical_listing_id)
    await service.observe(second)
    claim = await service.claim()
    await service.complete(claim, fake_extract(claim), {"description": "Pets allowed"})
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET current_status='removed' WHERE id=:id"),
                              {"id": source.source_record_id})
    assert await service.read_current_projection(source.canonical_listing_id) is None
    await service.reconcile_listing(source.canonical_listing_id)
    current = await service.read_current_projection(source.canonical_listing_id)
    assert current is not None and len(current.features[0].supporting_fact_ids) == 1


async def test_unknown_and_conflict_remain_unverified(pipeline):
    service, _ = pipeline
    source = await completed(pipeline)
    second = await seed(pipeline, listing_id=source.canonical_listing_id, description="No pets")
    await service.observe(second)
    claim = await service.claim()
    await service.complete(claim, fake_extract(claim, allow=False), {"description": "No pets"})
    current = await service.read_current_projection(source.canonical_listing_id)
    assert current is not None and current.features[0].status == "conflict"
    assert current.features[0].typed_value is None


async def test_version_and_vocabulary_changes_invalidate_read(pipeline):
    service, sessions = pipeline
    source = await completed(pipeline)
    for resolver, vocabulary in (("new.v1", service.vocabulary), (service.resolver_version, FactVocabulary(
        amenity_codes=frozenset({"different_wifi"}), catalog_other_codes=frozenset(),
        tenant_group_codes=frozenset(), municipality_zones=frozenset(),
    ))):
        other = FactPipeline(sessions, service.policy, vocabulary, resolver_version=resolver)
        assert await other.read_current_projection(source.canonical_listing_id) is None


async def test_read_snapshot_does_not_mix_concurrent_source_change(pipeline, monkeypatch):
    service, sessions = pipeline
    source = await completed(pipeline)
    original = service._authority

    async def concurrent_change(session, listing_id, **kwargs):
        # Anchor/projection reads have established the reader's snapshot. A
        # concurrent writer can commit: the reader holds no source/anchor locks.
        async with sessions() as writer, writer.begin():
            await writer.execute(text("UPDATE external_listing_sources SET raw_payload=jsonb_build_object('changed',true)"))
            await writer.execute(text("INSERT INTO external_listing_sources(id,canonical_listing_id,fingerprint,current_status) "
                                      "VALUES (:id,:listing,repeat('c',64),'active')"),
                                 {"id": uuid4(), "listing": listing_id})
        return await original(session, listing_id, **kwargs)

    monkeypatch.setattr(service, "_authority", concurrent_change)
    assert await service.read_current_projection(source.canonical_listing_id) is not None
    monkeypatch.setattr(service, "_authority", original)
    assert await service.read_current_projection(source.canonical_listing_id) is None


async def test_storage_failure_propagates_without_old_projection_fallback(pipeline, monkeypatch):
    service, _ = pipeline
    source = await completed(pipeline)

    async def unavailable(*args, **kwargs):
        raise DBAPIError("synthetic", None, RuntimeError("fixture failure"))

    monkeypatch.setattr(service, "_authority", unavailable)
    with pytest.raises(DBAPIError):
        await service.read_current_projection(source.canonical_listing_id)


async def test_excess_sources_are_unavailable_instead_of_partial_support(pipeline):
    service, sessions = pipeline
    source = await completed(pipeline)
    async with sessions() as session, session.begin():
        await session.execute(text("INSERT INTO external_listing_sources(id,canonical_listing_id,fingerprint,current_status) "
                                  "SELECT gen_random_uuid(),:listing,repeat('d',64),'active' FROM generate_series(1,128)"),
                              {"listing": source.canonical_listing_id})
    assert await service.read_current_projection(source.canonical_listing_id) is None
