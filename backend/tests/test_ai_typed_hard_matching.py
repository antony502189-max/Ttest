import copy
import json

import pytest
from ai_facts_pg.typed_match_cases import CASES, VOCABULARY, edge_cases, intent, plan, projection

from app.services.ai_hard_matching import compile_hard_match, evaluate_hard_match


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_every_hard_criterion_and_uncertainty(case):
    compiled = plan(case)
    assert evaluate_hard_match(compiled, projection(case["features"])) == ()
    assert evaluate_hard_match(compiled, projection([])) == (case["name"],)
    assert evaluate_hard_match(plan(case, "soft"), projection([])) == ()
    for status in ("unknown", "conflict", "conditional", "legacy_unverified"):
        changed = copy.deepcopy(case["features"])
        changed[0].update(status=status, typed_value=None)
        assert evaluate_hard_match(compiled, projection(changed)) == (case["name"],)


def test_no_dropped_hard_fields_and_combined_preserved_criteria():
    criteria = {case["name"]: {"strength": "hard", "value": case["value"]} for case in CASES}
    features = {json.dumps([f["key"], f["qualifiers"]], sort_keys=True): f for case in CASES for f in case["features"]}
    compiled = compile_hard_match(intent(criteria), VOCABULARY)
    assert {g.name for g in compiled.criteria} == set(criteria)
    assert evaluate_hard_match(compiled, projection(list(features.values()))) == ()
    assert set(evaluate_hard_match(compiled, projection([]))) == set(criteria)


def test_vocabulary_and_relationship_gaps_fail_explicitly():
    case = next(c for c in CASES if c["name"] == "party")
    request = intent({"party": {"strength": "hard", "value": dict(case["value"], relationship="friends")}})
    empty = VOCABULARY.model_copy(update={"tenant_group_codes": frozenset()})
    with pytest.raises(ValueError, match="friends"):
        compile_hard_match(request, empty)
    with pytest.raises(ValueError, match="amenity"):
        compile_hard_match(intent({"amenities": {"strength": "hard", "value": ["invented"]}}), VOCABULARY)


def test_currency_period_deposit_and_stay_do_not_convert():
    case = copy.deepcopy(next(c for c in CASES if c["name"] == "budget"))
    case["features"][0]["typed_value"]["period"] = "weekly"
    assert evaluate_hard_match(plan(case), projection(case["features"])) == ("budget",)
    case = copy.deepcopy(next(c for c in CASES if c["name"] == "deposit"))
    case["features"][0]["typed_value"] = {"kind": "money", "amount": "1", "currency": "EUR", "period": "one_off"}
    assert evaluate_hard_match(plan(case), projection(case["features"])) == ("deposit",)
    case = copy.deepcopy(next(c for c in CASES if c["name"] == "dates"))
    case["features"][1]["typed_value"]["unit"] = "months"
    assert evaluate_hard_match(plan(case), projection(case["features"])) == ("dates",)


@pytest.mark.parametrize("case,features,expected", edge_cases())
def test_semantic_boundaries(case, features, expected):
    # Invalid policy status/value combinations must be rejected at validation.
    if features[0]["status"] == "explicit_allow" and features[0]["typed_value"].get("allowed") is False:
        with pytest.raises(ValueError):
            projection(features)
        return
    assert (not evaluate_hard_match(plan(case), projection(features))) is expected


