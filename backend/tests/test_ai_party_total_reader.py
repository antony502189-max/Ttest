"""Retained total-only snapshots can be read without changing producer grammar."""
import json

import pytest
from pydantic import ValidationError

from app.schemas.ai_search_intent import Criteria


@pytest.mark.parametrize("value", [{"persons": 0}, {"persons": 11}, {"persons": True}, {"persons": "1"},
    {"persons": 1, "adults": 1}, {"persons": 1, "children": 0}, {"persons": 1, "relationship": "family"}])
def test_reader_rejects_partial_or_conflicting_party_shapes(value):
    with pytest.raises(ValidationError):
        Criteria.model_validate({"party": {"strength": "hard", "value": value}})


@pytest.mark.parametrize("value", [{"persons": 1}, {"persons": 10},
    {"adults": 2, "children": 1, "relationship": "family"}])
def test_retained_party_wire_value_round_trips_without_age_inference(value):
    criterion = {"strength": "hard", "value": value}
    party = Criteria.model_validate({"party": criterion}).party
    assert party.model_dump() == criterion
    assert json.loads(party.model_dump_json()) == criterion
    assert party.value.headcount == (value["persons"] if "persons" in value else value["adults"] + value["children"])


@pytest.mark.parametrize("text", ["a room for one person under 650 euros per month",
    "комната для одного человека до 650 евро в месяц"])
def test_compatibility_release_does_not_enable_total_only_generation(text):
    from test_ai_housing_input import VOCAB, state

    from app.services.ai_deepseek_intent import ProviderFailure
    from app.services.ai_housing_input import housing_patch
    with pytest.raises(ProviderFailure):
        housing_patch(text, state(), VOCAB)


def test_other_followups_preserve_a_retained_total_only_snapshot():
    from test_ai_housing_input import VOCAB, state

    from app.schemas.ai_search_intent import apply_patch
    from app.services.ai_housing_input import housing_patch
    current = state({"party": {"strength": "hard", "value": {"persons": 1}}})
    updated = apply_patch(current, housing_patch("furnished", current, VOCAB))
    assert updated.criteria.party == current.criteria.party
    assert updated.criteria.furnished.value is True
