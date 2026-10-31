"""Opt-in measured public Flatio sample on disposable PG; no network in this test."""
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select, text
from test_query_proofs import guard
from test_query_proofs import proofs as proof_fixture
from typed_match_cases import intent

from app.models import Listing
from app.repositories.ai_fact_pipeline import FactPipeline
from app.repositories.ai_fact_quality import audit_catalog, source_freshness_predicate
from app.repositories.ai_query_proofs import QueryProofs, current_projection_predicate
from app.schemas.ai_fact_pipeline import SourceInput
from app.schemas.ai_listing_facts import FactVocabulary, digest
from app.services.ai_fact_bridge import PreparedFactInput
from app.services.ai_fact_quality import FactQualityPolicy
from app.services.ai_hard_matching import compile_hard_match

pytestmark = pytest.mark.integration
proofs = proof_fixture


async def test_authorized_flatio_sample_pipeline_proof_quality_and_cleanup(pipeline, proofs):
    dataset = os.getenv("AI_FLATIO_PILOT_DATA")
    if not dataset:
        pytest.skip("explicit authorized local pilot dataset required")
    records = json.loads(Path(dataset).read_text(encoding="utf-8"))
    assert 0 < len(records) <= 100
    base, sessions = pipeline
    vocabulary = FactVocabulary(amenity_codes=frozenset({"wifi"}), catalog_other_codes=frozenset(),
                                tenant_group_codes=frozenset(), municipality_zones=frozenset())
    service = FactPipeline(sessions, base.policy, vocabulary, resolver_version="flatio-resolver.v1")
    proofs = QueryProofs(service)
    policy = FactQualityPolicy(price_max_age_seconds=86400, policy_max_age_seconds=604800,
                               evidence_retention_seconds=2592000)
    async with sessions() as session, session.begin():
        await session.execute(text("ALTER TABLE listings ADD COLUMN monthly_price numeric, "
                                   "ADD COLUMN rental_mode text, ADD COLUMN source_price_currency text, "
                                   "ADD COLUMN source_price_is_from boolean, ADD COLUMN room_capacity integer"))
    admitted = []
    for record in records:
        listing_id, source_id = UUID(record["listing_id"]), UUID(record["source_id"])
        price = next((f["typed_value"]["amount"] for f in record["facts"] if f["key"] == "price"), None)
        capacity = next((f["typed_value"]["value"] for f in record["facts"] if f["key"] == "capacity_total"), None)
        async with sessions() as session, session.begin():
            await session.execute(text("INSERT INTO listings(id,status,monthly_price,rental_mode,source_price_currency,"
                                       "source_price_is_from,room_capacity) VALUES(:id,:status,:price,'long','EUR',false,:capacity)"),
                                  {"id": listing_id, "status": "published" if record["eligible"] else "hidden",
                                   "price": price, "capacity": capacity})
            await session.execute(text("INSERT INTO external_listing_sources(id,canonical_listing_id,fingerprint,current_status,"
                                       "last_success_at,normalized_payload,source_name,external_id,source_url) VALUES "
                                       "(:id,:listing,:fingerprint,'active',:checked,CAST(:payload AS jsonb),'Flatio',:external,:url)"),
                                  {"id": source_id, "listing": listing_id, "fingerprint": record["source_hash"],
                                   "checked": datetime.fromisoformat(record["checked_at"]),
                                   "payload": json.dumps(record["fields"]), "external": record["record_id"], "url": record["url"]})
            _, authority = await service._authority(session, listing_id)
            snapshot = authority[source_id].snapshot_hash
        if not record["eligible"]:
            continue
        source = SourceInput(source_record_id=source_id, canonical_listing_id=listing_id,
                             content_hash=digest(record["fields"]), snapshot_hash=snapshot,
                             schema_version="ai-facts.v1", taxonomy_version="ai-search.v1", extractor_version="flatio-closed.v1")
        prepared = PreparedFactInput(source, tuple(sorted(record["fields"].items())),
                                     tuple(json.dumps(f) for f in record["facts"]))
        await service.observe(source)
        claim = await service.claim(extractor_version="flatio-closed.v1")
        assert claim.source_record_id == source_id
        receipt = await service.complete(claim, prepared.to_batch(claim, observed_at=datetime.now(UTC)), prepared.sanitized_fields)
        assert receipt.status == "succeeded"
        assert await proofs.prepare(listing_id)
        assert await guard(proofs, listing_id)
        assert await service.purge_expired_evidence(listing_id, retention_seconds=policy.evidence_retention_seconds) == 0
        admitted.append(record)
    assert admitted, "no eligible real records: report gaps rather than certify an empty cohort"
    eligibility = (Listing.monthly_price > 0) & (Listing.monthly_price <= 1000)
    scenarios = {
        "pets_small_dog": {"pets": {"strength": "hard", "value": [{"species": "dog", "size": "small", "count": 1}]}},
        "budget_1000_monthly": {"budget": {"strength": "hard", "value": {"amount": "1000.00", "currency": "EUR", "period": "monthly"}}},
        "budget_1_monthly": {"budget": {"strength": "hard", "value": {"amount": "1.00", "currency": "EUR", "period": "monthly"}}},
        "wifi": {"amenities": {"strength": "hard", "value": ["wifi"]}},
        "party_two_adults": {"party": {"strength": "hard", "value": {"adults": 2, "children": 0, "relationship": "unspecified"}}},
    }
    results = {}
    for name, criteria in scenarios.items():
        plan = compile_hard_match(intent(criteria), vocabulary)
        results[name] = await audit_catalog(service, eligibility=eligibility, plan=plan, policy=policy, limit=100)
        async with sessions() as session:
            verified = current_projection_predicate(Listing.id, resolver_version=service.resolver_version,
                                                    vocabulary_hash=service.vocabulary_hash, match_plan=plan)
            query = select(func.count()).select_from(Listing).where(Listing.status == "published", Listing.deleted_at.is_(None),
                eligibility, verified, source_freshness_predicate(Listing.id, plan, policy))
            assert await session.scalar(query) == results[name]["match"]
    selected = UUID(admitted[0]["listing_id"])
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET current_status='removed' WHERE canonical_listing_id=:id"), {"id": selected})
    assert not await guard(proofs, selected)
    await service.reconcile_listing(selected)
    summary = {"scanned": len(records), "eligible": len(admitted), "pipeline_complete": len(admitted),
               "proof_prepared": len(admitted), "quality": results, "local_retirement_invalidates_proof": True,
               "retention_30_days_keeps_new_evidence": True, "dataset_teardown": "fresh schema dropped by fixture"}
    Path(os.environ["AI_FLATIO_PILOT_RESULT"]).write_text(json.dumps(summary, indent=2), encoding="utf-8")
