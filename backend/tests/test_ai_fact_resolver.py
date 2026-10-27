from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.ai_fact_pipeline import FactQueuePolicy
from app.schemas.ai_listing_facts import FactBatch, digest
from app.services.ai_fact_resolver import resolve_sources


def source(listing, *, status="explicit_allow", allowed=True, qualifiers=None, key="pets", origin="source_text"):
    text = "Pets allowed" if allowed else "No pets"
    unknown = status in {"unknown", "conflict", "legacy_unverified"}
    return FactBatch.model_validate({
        "schema_version": "ai-facts.v1", "taxonomy_version": "ai-search.v1", "batch_id": uuid4(),
        "canonical_listing_id": listing, "source_record_id": uuid4(), "source_generation": 1,
        "content_hash": digest({"description": text}), "extractor_version": "test.v1",
        "observed_at": datetime(2026, 10, 26, tzinfo=UTC), "source_status": "active",
        "last_successful_check_at": None, "last_content_change_at": None, "last_check_error_at": None,
        "facts": [{"fact_id": uuid4(), "key": key, "status": status,
                   "typed_value": None if unknown else {"kind": "policy", "allowed": allowed},
                   "qualifiers": qualifiers or {}, "origin": origin,
                   "evidence": [] if status in {"unknown", "legacy_unverified"} else [
                       {"field": "description", "quote": text, "start": 0, "end": len(text)},
                   ]}],
    })


def resolve(listing, batches):
    return resolve_sources(canonical_listing_id=listing, batches=batches, input_hash="a" * 64,
                           feature_revision=1, resolver_version="test.v1", computed_at=datetime(2026, 10, 26, tzinfo=UTC))


def test_equal_values_aggregate_and_conflicts_do_not_use_latest_timestamp():
    listing = uuid4()
    a, b = source(listing), source(listing)
    result = resolve(listing, [a, b])
    assert result.features[0].status == "explicit_allow"
    assert len(result.features[0].supporting_fact_ids) == 2
    deny = source(listing, status="explicit_deny", allowed=False)
    conflict = resolve(listing, [a, deny])
    assert conflict.features[0].status == "conflict"
    assert conflict.features[0].typed_value is None
    assert resolve(listing, [deny, a]) == conflict


@pytest.mark.parametrize("uncertain", ["unknown", "conditional", "conflict", "legacy_unverified"])
def test_uncertain_stays_uncertain(uncertain):
    listing = uuid4()
    batch = source(listing, status=uncertain, origin="legacy_default" if uncertain == "legacy_unverified" else "source_text")
    assert resolve(listing, [batch]).features[0].status == uncertain


def test_unknown_and_legacy_defaults_do_not_outvote_explicit_evidence():
    listing = uuid4()
    batches = [source(listing, status="unknown"),
               source(listing, status="legacy_unverified", origin="legacy_default"), source(listing)]
    assert resolve(listing, batches).features[0].status == "explicit_allow"


def test_small_dog_approval_never_becomes_blanket_pet_permission():
    listing = uuid4()
    a = source(listing)
    b = source(listing, status="conditional", qualifiers={"species": "dog", "size": "small", "approval_required": True})
    result = resolve(listing, [a, b])
    assert len(result.features) == 2
    assert all(f.status == "conditional" and f.typed_value is None for f in result.features)
    assert all(len(f.supporting_fact_ids) == 2 for f in result.features)


def test_dog_and_cat_scopes_are_not_conflated():
    listing = uuid4()
    a = source(listing, qualifiers={"species": "dog"})
    b = source(listing, status="explicit_deny", allowed=False, qualifiers={"species": "cat"})
    assert {f.status for f in resolve(listing, [a, b]).features} == {"explicit_allow", "explicit_deny"}


def test_smoking_balcony_does_not_override_indoors():
    listing = uuid4()
    a = source(listing, key="smoking", qualifiers={"smoking_scope": "balcony"})
    b = source(listing, key="smoking", status="explicit_deny", allowed=False, qualifiers={"smoking_scope": "indoors"})
    assert {f.status for f in resolve(listing, [a, b]).features} == {"explicit_allow", "explicit_deny"}
    broad = source(listing, key="smoking", qualifiers={"smoking_scope": "outdoors"})
    assert all(f.status == "conditional" for f in resolve(listing, [a, broad]).features)


@pytest.mark.parametrize("state", ["retired", "unknown", "unavailable"])
def test_inactive_batches_supply_no_features(state):
    listing = uuid4()
    batch = source(listing).model_dump()
    batch["source_status"] = state
    assert resolve(listing, [FactBatch.model_validate(batch)]).features == []


def test_cross_listing_duplicate_source_and_owner_are_rejected():
    listing = uuid4()
    a = source(listing)
    with pytest.raises(ValueError, match="canonical"):
        resolve(uuid4(), [a])
    with pytest.raises(ValueError, match="one source"):
        resolve(listing, [a, a])
    native = a.model_dump()
    native["source_record_id"] = None
    native["facts"][0]["origin"] = "owner_explicit"
    native["facts"][0]["evidence"][0]["field"] = "owner_form"
    with pytest.raises(ValueError, match="external"):
        resolve(listing, [FactBatch.model_validate(native)])


@pytest.mark.parametrize("changes", [{}, {"lease_seconds": 0}, {"max_attempts": True}, {"retry_delay_seconds": 0}])
def test_queue_policy_requires_explicit_bounded_configuration(changes):
    values = {} if not changes else {"lease_seconds": 60, "max_attempts": 2, "retry_delay_seconds": 1} | changes
    with pytest.raises(ValidationError):
        FactQueuePolicy.model_validate(values)


def test_multiple_sources_can_supply_more_observations_than_projection_feature_count():
    listing = uuid4()
    batches = []
    for _ in range(9):
        data = source(listing).model_dump()
        template = data["facts"][0]
        data["facts"] = [template | {
            "fact_id": uuid4(), "key": "amenity", "typed_value": {"kind": "boolean", "value": True},
            "qualifiers": {"amenity_code": f"test_{i}"},
        } for i in range(15)]
        batches.append(FactBatch.model_validate(data))
    projection = resolve(listing, batches)
    assert len(projection.features) == 15
    assert all(len(f.supporting_fact_ids) == 9 and f.status == "explicit_allow" for f in projection.features)
