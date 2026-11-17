"""Age-neutral headcount is explicit; it must not invent adults or children."""
import copy

import pytest
from pydantic import ValidationError
from test_ai_housing_input import VOCAB, state

from app.schemas.ai_search_intent import Criteria, apply_patch
from app.services.ai_deepseek_intent import ProviderFailure
from app.services.ai_housing_input import housing_patch


@pytest.mark.parametrize("text", [
    "комната для одного человека до 650 евро в месяц",
    "a room for one person under 650 euros per month",
    "una habitación para una persona hasta seiscientos cincuenta euros al mes",
])
def test_person_count_is_preserved_without_age_assumptions(text):
    c = housing_patch(text, state(), VOCAB).set
    assert c.party.value.model_dump() == {"persons": 1}
    assert c.accommodation.value.kind == "room" and c.budget.value.amount == "650"


@pytest.mark.parametrize("value", [{"persons": 0}, {"persons": 11}, {"persons": True}, {"persons": "1"},
    {"persons": 1, "adults": 1}, {"persons": 1, "children": 0}, {"persons": 1, "relationship": "family"}])
def test_total_count_contract_is_bounded_and_not_a_partial_age_composition(value):
    with pytest.raises(ValidationError):
        Criteria.model_validate({"party": {"strength": "hard", "value": value}})


def test_legacy_party_wire_shape_is_unchanged():
    old = {"adults": 2, "children": 1, "relationship": "family"}
    assert Criteria.model_validate({"party": {"strength": "hard", "value": old}}).party.value.model_dump() == old


def test_neutral_followup_changes_only_headcount():
    current = state()
    current = apply_patch(current, housing_patch("a room for 1 person under 650 euros per month, furnished", current, VOCAB))
    changed = apply_patch(current, housing_patch("para dos personas", current, VOCAB))
    assert changed.criteria.party.value.model_dump() == {"persons": 2}
    assert changed.criteria.budget == current.criteria.budget and changed.criteria.furnished == current.criteria.furnished


@pytest.mark.parametrize("text", ["для 0 человек", "for 11 people", "for 1 person, for 2 people",
    "for 2 people, 1 adult, 0 children", "for 1 person, 1 adult", "for 1 person, unknown tail"])
def test_incomplete_conflicting_or_unknown_people_request_rejects_atomically(text):
    with pytest.raises(ProviderFailure):
        housing_patch(text, state(), VOCAB)


def test_complete_age_composition_can_refine_a_neutral_count():
    current = state()
    current = apply_patch(current, housing_patch("for 2 people", current, VOCAB))
    changed = apply_patch(current, housing_patch("1 adult, 1 child", current, VOCAB))
    assert changed.criteria.party.value.model_dump() == {"adults": 1, "children": 1, "relationship": "unspecified"}


def test_neutral_followup_never_erases_existing_child_or_relationship_requirements():
    current = state({"party": {"strength": "hard", "value": {"adults": 1, "children": 1, "relationship": "family"}}})
    before = copy.deepcopy(current)
    with pytest.raises(ProviderFailure):
        housing_patch("for 3 people", current, VOCAB)
    assert current == before
    other_change = housing_patch("for 2 people, furnished", current, VOCAB)
    assert other_change.set.party.value == current.criteria.party.value
