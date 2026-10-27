"""Synthetic storage contracts, not source extraction or real inventory quality."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.ai_listing_facts import FactBatch, FactObservation, FactValue, FactVocabulary, SearchProjection, digest


def observation(**changes):
    return {"fact_id": uuid4(), "key": "pets", "status": "explicit_deny", "typed_value": {"kind": "policy", "allowed": False},
                "qualifiers": {}, "origin": "source_text", "evidence": [{"field": "description", "quote": "No pets", "start": 0, "end": 7}]} | changes


def batch(**changes):
    now = datetime(2026, 10, 26, tzinfo=UTC)
    return {"schema_version": "ai-facts.v1", "taxonomy_version": "ai-search.v1", "batch_id": uuid4(),
                "canonical_listing_id": uuid4(), "source_record_id": uuid4(), "source_generation": 1,
                "content_hash": digest({"description": "No pets"}), "extractor_version": "rules.test.v1", "observed_at": now,
                "source_status": "active", "last_successful_check_at": now, "last_content_change_at": now - timedelta(days=1),
                "last_check_error_at": None, "facts": [observation()]} | changes


def projection(source, **changes):
    fact = source.facts[0]
    feature = fact.model_dump(include={"key", "status", "typed_value", "qualifiers"})
    feature["supporting_fact_ids"] = [fact.fact_id]
    return {"schema_version": "ai-facts.v1", "taxonomy_version": "ai-search.v1",
                "canonical_listing_id": source.canonical_listing_id, "feature_revision": 1,
                "resolver_version": "resolver.test.v1", "input_hash": "a" * 64,
                "computed_at": source.observed_at, "features": [feature]} | changes


@pytest.mark.parametrize("key,value,qualifiers", [
    ("capacity_total", {"kind": "quantity", "value": 3, "unit": "persons"}, {"inventory_scope": "rented_unit"}),
    ("current_room_residents", {"kind": "quantity", "value": 0, "unit": "persons"}, {"inventory_scope": "rented_unit"}),
    ("available_spots", {"kind": "quantity", "value": 2, "unit": "persons"}, {"inventory_scope": "rented_unit"}),
    ("price", {"kind": "money", "amount": "650.50", "currency": "EUR", "period": "monthly"}, {}),
    ("deposit", {"kind": "quantity", "value": 2, "unit": "months"}, {}),
    ("deposit", {"kind": "money", "amount": "0", "currency": "EUR", "period": "one_off"}, {}),
    ("geography", {"kind": "geography", "province_code": "38", "municipality_code": "38001"}, {}),
    ("availability", {"kind": "date_range", "start": "2027-01-01", "end": "2027-02-01"}, {"inventory_scope": "rented_unit"}),
    ("rental_mode", {"kind": "category", "value": "holiday"}, {}),
    ("accommodation", {"kind": "category", "value": "one_bedroom"}, {}),
    ("accommodation", {"kind": "category", "value": "catalog_other", "catalog_code": "test_unit"}, {}),
    ("minimum_stay", {"kind": "quantity", "value": 3, "unit": "months"}, {}),
    ("maximum_stay", {"kind": "quantity", "value": 30, "unit": "nights"}, {}),
    *[(key, {"kind": "boolean", "value": False}, {}) for key in ("furnished", "bills_included", "balcony", "terrace")],
    ("amenity", {"kind": "boolean", "value": True}, {"amenity_code": "test_wifi"}),
    ("pets", {"kind": "policy", "allowed": True}, {}),
    ("smoking", {"kind": "policy", "allowed": True}, {"smoking_scope": "balcony"}),
    ("couples", {"kind": "policy", "allowed": True}, {}),
    ("children", {"kind": "policy", "allowed": True}, {}),
    ("tenant_groups", {"kind": "policy", "allowed": True}, {"tenant_group": "test_students"}),
])
def test_typed_keys_round_trip(key, value, qualifiers):
    item = FactValue(key=key, status="explicit_allow", typed_value=value, qualifiers=qualifiers)
    assert FactValue.model_validate_json(item.model_dump_json()) == item
    assert item.typed_value is not None


@pytest.mark.parametrize("changes", [
    {"status": "unknown"}, {"status": "conflict"}, {"status": "legacy_unverified"},
    {"status": "explicit_allow"}, {"typed_value": None}, {"typed_value": {"kind": "policy", "allowed": "false"}},
    {"typed_value": {"kind": "policy", "allowed": 0}}, {"typed_value": {"kind": "boolean", "value": False}},
    {"qualifiers": {"inventory_scope": "rented_unit"}}, {"qualifiers": {"smoking_scope": "indoors"}},
    {"qualifiers": {"approval_required": True}}, {"key": "model_sql"}, {"status": "explicit"},
    {"evidence": []}, {"origin": "legacy_default"}, {"unknown_extra": True},
    {"evidence": [{"field": "raw_html", "quote": "No pets", "start": 0, "end": 7}]},
    {"evidence": [{"field": "description", "quote": "No pets", "start": 0, "end": 6}]},
])
def test_reject_unsafe_observations(changes):
    with pytest.raises(ValidationError):
        FactObservation.model_validate(observation(**changes))


@pytest.mark.parametrize("key,value,qualifiers", [
    ("capacity_total", {"kind": "quantity", "value": True, "unit": "persons"}, {"inventory_scope": "rented_unit"}),
    ("available_spots", {"kind": "quantity", "value": 0, "unit": "persons"}, {"inventory_scope": "rented_unit"}),
    ("capacity_total", {"kind": "quantity", "value": 3, "unit": "persons"}, {}),
    ("price", {"kind": "money", "amount": 650, "currency": "EUR", "period": "monthly"}, {}),
    ("price", {"kind": "money", "amount": "NaN", "currency": "EUR", "period": "monthly"}, {}),
    ("price", {"kind": "money", "amount": "650", "currency": "USD", "period": "monthly"}, {}),
    ("price", {"kind": "money", "amount": "650", "currency": "EUR", "period": "one_off"}, {}),
    ("deposit", {"kind": "quantity", "value": 1.5, "unit": "months"}, {}),
    ("deposit", {"kind": "quantity", "value": 2, "unit": "persons"}, {}),
    ("minimum_stay", {"kind": "quantity", "value": 0, "unit": "months"}, {}),
    ("rental_mode", {"kind": "category", "value": "room"}, {}),
    ("accommodation", {"kind": "category", "value": "long"}, {}),
    ("accommodation", {"kind": "category", "value": "studio", "catalog_code": "test_unit"}, {}),
    ("geography", {"kind": "geography", "province_code": "28", "municipality_code": "38001"}, {}),
    ("geography", {"kind": "geography", "province_code": "38", "municipality_code": "38999"}, {}),
    ("availability", {"kind": "date_range", "start": "2027-02-30", "end": "2027-03-02"}, {"inventory_scope": "rented_unit"}),
    ("availability", {"kind": "date_range", "start": "2027-02-02", "end": "2027-01-01"}, {"inventory_scope": "rented_unit"}),
    ("amenity", {"kind": "boolean", "value": True}, {}),
    ("smoking", {"kind": "policy", "allowed": True}, {}),
])
def test_reject_wrong_units_scopes_and_categories(key, value, qualifiers):
    with pytest.raises(ValidationError):
        FactValue(key=key, status="explicit_allow", typed_value=value, qualifiers=qualifiers)


@pytest.mark.parametrize("status", ["unknown", "conflict", "legacy_unverified"])
def test_unresolved_has_no_winning_value(status):
    fact = FactValue(key="pets", status=status, typed_value=None, qualifiers={})
    assert fact.typed_value is None


def test_conditional_is_scoped_and_legacy_is_not_evidence():
    fact = FactObservation.model_validate(observation(status="conditional", typed_value={"kind": "policy", "allowed": True},
                                                     qualifiers={"species": "dog", "size": "small", "approval_required": True}))
    assert fact.status == "conditional"
    assert fact.scope_hash != FactObservation.model_validate(observation()).scope_hash
    legacy = FactObservation.model_validate(observation(status="legacy_unverified", origin="legacy_default", typed_value=None, evidence=[]))
    assert legacy.typed_value is None


def test_evidence_hash_and_exact_negative_span():
    item = FactBatch.model_validate(batch())
    item.validate_evidence_against({"description": "No pets"})
    with pytest.raises(ValueError, match="hash mismatch"):
        item.validate_evidence_against({"description": "pets"})
    forged = batch(content_hash=digest({"description": "pets ok"}))
    with pytest.raises(ValueError, match="evidence does not match"):
        FactBatch.model_validate(forged).validate_evidence_against({"description": "pets ok"})
    assert digest({"a": "1", "b": "2"}) == digest({"b": "2", "a": "1"})


def test_structured_field_identity_is_preserved_in_sanitized_mapping():
    fields = {"structured.rules.pets": "No pets"}
    data = batch(content_hash=digest(fields), facts=[observation(origin="source_structured", evidence=[{
        "field": "structured", "provider_field": "rules.pets", "quote": "No pets", "start": 0, "end": 7,
    }])])
    FactBatch.model_validate(data).validate_evidence_against(fields)
    del data["facts"][0]["evidence"][0]["provider_field"]
    with pytest.raises(ValidationError, match="named provider field"):
        FactBatch.model_validate(data)


@pytest.mark.parametrize("changes", [
    {"schema_version": "ai-facts.v2"}, {"taxonomy_version": "ai-search.v2"},
    {"source_generation": 0}, {"source_generation": True}, {"content_hash": "bad"},
    {"observed_at": datetime(2026, 10, 26, tzinfo=UTC).replace(tzinfo=None)},
    {"last_successful_check_at": datetime(2027, 1, 1, tzinfo=UTC)},
    {"source_record_id": None}, {"source_status": "published"}, {"facts": []},
])
def test_batch_boundaries(changes):
    with pytest.raises(ValidationError):
        FactBatch.model_validate(batch(**changes))


def test_owner_and_source_identity_and_duplicate_observations():
    data = batch(source_record_id=None, facts=[observation(origin="owner_explicit", evidence=[
        {"field": "owner_form", "quote": "No pets", "start": 0, "end": 7},
    ])])
    assert FactBatch.model_validate(data).source_record_id is None
    with pytest.raises(ValidationError):
        FactBatch.model_validate(data | {"source_record_id": uuid4()})
    item = batch()
    item["facts"].append(deepcopy(item["facts"][0]) | {"fact_id": uuid4()})
    with pytest.raises(ValidationError, match="duplicate observation"):
        FactBatch.model_validate(item)


def test_projection_support_is_scoped_and_listing_bound():
    source = FactBatch.model_validate(batch())
    value = SearchProjection.model_validate(projection(source))
    value.validate_support([source])
    assert SearchProjection.model_validate_json(value.model_dump_json()) == value
    with pytest.raises(ValueError, match="supporting observation"):
        value.validate_support([])
    with pytest.raises(ValueError, match="cross-listing"):
        value.validate_support([FactBatch.model_validate(batch())])
    changed = source.model_dump()
    changed["facts"][0]["qualifiers"] = {"species": "cat"}
    with pytest.raises(ValueError, match="differently scoped"):
        value.validate_support([FactBatch.model_validate(changed)])
    data = projection(source)
    data["features"].append(deepcopy(data["features"][0]))
    with pytest.raises(ValidationError, match="duplicate feature"):
        SearchProjection.model_validate(data)


@pytest.mark.parametrize("changes", [
    {"schema_version": "ai-facts.v0"}, {"feature_revision": 0}, {"feature_revision": True},
    {"input_hash": "stale"}, {"computed_at": datetime(2026, 10, 26, tzinfo=UTC).replace(tzinfo=None)},
])
def test_projection_boundaries(changes):
    with pytest.raises(ValidationError):
        SearchProjection.model_validate(projection(FactBatch.model_validate(batch()), **changes))


@pytest.mark.parametrize("status", ["unknown", "unavailable", "retired"])
def test_inactive_sources_cannot_support_explicit_features(status):
    source = FactBatch.model_validate(batch(source_status=status))
    with pytest.raises(ValueError, match="inactive evidence"):
        SearchProjection.model_validate(projection(source)).validate_support([source])


def test_feature_cannot_invert_supporting_negative():
    source = FactBatch.model_validate(batch())
    data = projection(source)
    data["features"][0]["status"] = "explicit_allow"
    data["features"][0]["typed_value"] = {"kind": "policy", "allowed": True}
    with pytest.raises(ValueError, match="contradictory"):
        SearchProjection.model_validate(data).validate_support([source])


def test_required_server_vocabulary_has_no_permissive_default():
    with pytest.raises(ValidationError):
        FactVocabulary()
    empty = FactVocabulary(amenity_codes=frozenset(), catalog_other_codes=frozenset(),
                           tenant_group_codes=frozenset(), municipality_zones=frozenset())
    fact = FactValue(key="amenity", status="explicit_allow", typed_value={"kind": "boolean", "value": True},
                     qualifiers={"amenity_code": "test_wifi"})
    with pytest.raises(ValueError, match="unsupported amenity"):
        empty.validate_fact(fact)
    vocabulary = FactVocabulary(amenity_codes=frozenset({"test_wifi"}), catalog_other_codes=frozenset(),
                                tenant_group_codes=frozenset(), municipality_zones=frozenset())
    vocabulary.validate_fact(fact)


def test_owner_evidence_cannot_be_claimed_from_external_text():
    with pytest.raises(ValidationError, match="evidence field"):
        FactObservation.model_validate(observation(origin="owner_explicit"))


def test_projection_byte_budget_is_bounded_before_storage():
    source = FactBatch.model_validate(batch())
    features = [{
        "key": "amenity", "status": "unknown", "typed_value": None,
        "qualifiers": {"amenity_code": f"synthetic_{i}"},
        "supporting_fact_ids": [uuid4() for _ in range(128)],
    } for i in range(128)]
    with pytest.raises(ValidationError, match="storage byte budget"):
        SearchProjection.model_validate(projection(source, features=features))


@pytest.mark.parametrize("key,value,qualifiers", [
    ("capacity_total", {"kind": "quantity", "value": 3, "unit": "persons"}, {"inventory_scope": "rented_unit"}),
    ("furnished", {"kind": "boolean", "value": False}, {}),
    ("price", {"kind": "money", "amount": "650", "currency": "EUR", "period": "monthly"}, {}),
])
def test_confirmed_values_cannot_use_policy_deny_status(key, value, qualifiers):
    with pytest.raises(ValidationError, match="confirmed values"):
        FactValue(key=key, status="explicit_deny", typed_value=value, qualifiers=qualifiers)
