import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.repositories.ai_search_sessions import IntentVocabulary, intent_hash
from app.schemas.ai_search_intent import Criteria, IntentPatch, SearchIntent, apply_patch


def hard(value):
    return {"strength": "hard", "value": value}


def intent_data():
    return {
        "schema_version": "ai-search.v1",
        "taxonomy_version": "rental.v1",
        "session_id": str(uuid4()),
        "version": 7,
        "criteria": {
            "rental_mode": hard("long"),
            "budget": hard({"amount": "650.00", "currency": "EUR", "period": "monthly"}),
            "geography": hard({"province_code": "38", "municipality_code": "38001"}),
            "party": hard({"adults": 2, "children": 0, "relationship": "couple"}),
            "pets": hard([{"species": "dog", "size": "small", "count": 1}]),
        },
    }


def patch_data(current, **changes):
    return {
        "schema_version": "ai-search.v1",
        "session_id": str(current.session_id),
        "expected_version": current.version,
        "set": {},
        "remove": [],
        **changes,
    }


def test_three_followups_preserve_unnamed_criteria():
    current = SearchIntent.model_validate_json(json.dumps(intent_data()))
    original = current
    balcony = IntentPatch.model_validate_json(json.dumps(patch_data(current, set={"balcony": hard(True)})))
    current = apply_patch(current, balcony)
    budget = IntentPatch.model_validate_json(
        json.dumps(
            patch_data(
                current,
                set={
                    "budget": hard({"amount": "700.00", "currency": "EUR", "period": "monthly"}),
                },
            )
        )
    )
    current = apply_patch(current, budget)
    current = apply_patch(current, IntentPatch.model_validate_json(json.dumps(patch_data(current, remove=["balcony"]))))
    assert current.version == 10
    assert current.criteria.balcony is None
    assert current.criteria.budget.value.amount == "700.00"
    for field in ("rental_mode", "party", "pets", "geography"):
        assert getattr(current.criteria, field) == getattr(original.criteria, field)
    assert original.version == 7 and original.criteria.budget.value.amount == "650.00"
    with pytest.raises(ValueError, match="SESSION_VERSION_CONFLICT"):
        apply_patch(current, balcony)


@pytest.mark.parametrize(
    "criteria",
    [
        {"balcony": None},
        {"balcony": hard("false")},
        {"balcony": hard(1)},
        {"sort": hard("top")},
        {"quota": hard(200)},
        {"sql": "SELECT *"},
        {"raw_text": "private"},
        {"budget": hard({"amount": 650, "currency": "EUR", "period": "monthly"})},
        {"budget": hard({"amount": "NaN", "currency": "EUR", "period": "monthly"})},
        {"budget": hard({"amount": "1.001", "currency": "EUR", "period": "monthly"})},
        {"budget": hard({"amount": "1", "currency": "USD", "period": "monthly"})},
        {"budget": hard({"amount": "700.00"})},
        {"party": hard({"adults": 2})},
        {"party": hard({"adults": True, "children": 0, "relationship": "couple"})},
        {"party": hard({"adults": 10, "children": 1, "relationship": "family"})},
        {"geography": hard({"province_code": "28", "municipality_code": "38001"})},
        {"geography": hard({"province_code": "38", "municipality_code": "99999"})},
        {"geography": hard({"province_code": "38", "zone_id": "unknown"})},
        {"pets": hard([{"species": "dog", "size": "small", "count": 0}])},
        {"pets": hard([{"species": "dog", "size": "tiny", "count": 1}])},
        {"amenities": hard(["wifi", "wifi"])},
        {"dates": hard({"check_in": "2026-02-30", "check_out": "2026-03-02"})},
        {"dates": hard({"check_in": "2026-11-01", "check_out": "2026-10-31"})},
        {"accommodation": hard({"kind": "catalog_other"})},
        {"deposit": hard({"kind": "money", "amount": "0", "currency": "EUR", "period": "monthly"})},
    ],
)
def test_strict_criteria_reject_unsafe_or_ambiguous_values(criteria):
    data = intent_data()
    data["criteria"] = criteria
    with pytest.raises(ValidationError):
        SearchIntent.model_validate_json(json.dumps(data))


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": "ai-search.v2"},
        {"expected_version": True},
        {"expected_version": "7"},
        {"remove": ["party.adults"]},
        {"remove": ["pets", "pets"]},
        {"set": {"balcony": hard(True)}, "remove": ["balcony"]},
        {"owner": str(uuid4())},
        {"set": {"pets": None}},
    ],
)
def test_patch_cannot_change_owner_or_bypass_remove(changes):
    current = SearchIntent.model_validate_json(json.dumps(intent_data()))
    with pytest.raises(ValidationError):
        IntentPatch.model_validate_json(json.dumps(patch_data(current, **changes)))


def test_versions_and_required_envelope_are_not_guessed():
    for field in ("schema_version", "taxonomy_version"):
        data = intent_data()
        data[field] = "future.v2"
        with pytest.raises(ValidationError):
            SearchIntent.model_validate_json(json.dumps(data))
        del data[field]
        with pytest.raises(ValidationError):
            SearchIntent.model_validate_json(json.dumps(data))


def test_merged_cross_field_validation_and_no_currency_period_conversion():
    data = intent_data()
    data["criteria"]["dates"] = hard({"check_in": "2026-11-01", "check_out": "2026-11-08"})
    current = SearchIntent.model_validate_json(json.dumps(data))
    patch = IntentPatch.model_validate_json(
        json.dumps(patch_data(current, set={"stay": hard({"value": 8, "unit": "nights"})}))
    )
    with pytest.raises(ValidationError):
        apply_patch(current, patch)
    patch = IntentPatch.model_validate_json(
        json.dumps(
            patch_data(
                current,
                set={
                    "budget": hard(
                        {
                            "amount": "1200.00",
                            "currency": "EUR",
                            "period": "weekly",
                        }
                    )
                },
            )
        )
    )
    changed = apply_patch(current, patch)
    assert changed.criteria.budget.value.amount == "1200.00"
    assert changed.criteria.budget.value.period == "weekly"
    assert changed.criteria.rental_mode.value == "long"


def test_catalog_and_zone_codes_require_server_allowlist():
    vocabulary = IntentVocabulary(
        frozenset({"wifi"}), frozenset({"synthetic_unit"}), frozenset({("38001", "synthetic_zone")})
    )
    for criteria in (
        {"amenities": hard(["invented"])},
        {"accommodation": hard({"kind": "catalog_other", "catalog_code": "invented"})},
        {"geography": hard({"province_code": "38", "municipality_code": "38001", "zone_id": "invented"})},
    ):
        parsed = Criteria.model_validate_json(json.dumps(criteria))
        with pytest.raises(ValueError, match="unsupported"):
            vocabulary.validate(parsed)
    supported = Criteria.model_validate_json(json.dumps({"accommodation": hard({"kind": "one_bedroom"})}))
    vocabulary.validate(supported)
    assert supported.accommodation.value.kind == "one_bedroom"


def test_roundtrip_hash_is_order_independent_and_state_is_frozen():
    data = intent_data()
    current = SearchIntent.model_validate_json(json.dumps(data))
    reordered = SearchIntent.model_validate_json(json.dumps(data, sort_keys=True))
    assert intent_hash(current) == intent_hash(reordered)
    assert isinstance(current.criteria.pets.value, tuple)
    with pytest.raises(ValidationError):
        current.version = 99
