import json
from pathlib import Path

import pytest

from app.external_sources import public_detail_fields
from app.services.listing_evidence import extract_policy_evidence

CASES = json.loads((Path(__file__).parent / "fixtures/ai_listing_policies.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_golden_policy_evidence(case):
    facts = extract_policy_evidence(description=case["text"])
    for field, (status, value, quote) in case["expected"].items():
        fact = facts[field]
        assert (fact.status, fact.value) == (status, value)
        if quote:
            assert quote in [span.quote for span in fact.evidence]
            assert all(span.source == "description" for span in fact.evidence)
        else:
            assert not fact.evidence
        if field in {"pets_allowed", "children_allowed", "smoking_allowed", "room_capacity"}:
            assert public_detail_fields({"description": case["text"]}).get(field) == (
                value if status == "explicit" else None
            )


def test_title_and_description_disagreement_keeps_both_evidence_spans():
    fact = extract_policy_evidence(title="No pets", description="Pets allowed")["pets_allowed"]
    assert fact.status == "conflict"
    assert {span.source for span in fact.evidence} == {"title", "description"}


@pytest.mark.parametrize("text", ["Pets allowed?", "Pets allowed? No.", "Se admiten mascotas?", "¿Se admiten mascotas?"])
def test_questions_are_not_confirmed_permissions(text):
    fact = extract_policy_evidence(description=text)["pets_allowed"]
    assert fact.status == "unknown" and fact.value is None
    assert public_detail_fields({"description": text})["pets_allowed"] is None


@pytest.mark.parametrize(
    "text,field,condition",
    [
        ("Se admiten mascotas. Solo gatos.", "pets_allowed", "Solo gatos"),
        ("Pets allowed. Only with prior approval.", "pets_allowed", "Only with prior approval"),
        ("Se permite fumar. Solo en la terraza.", "smoking_allowed", "Solo en la terraza"),
        ("Children allowed; only with prior approval.", "children_allowed", "only with prior approval"),
        ("Para 4 personas. Solo con autorizacion.", "room_capacity", "Solo con autorizacion"),
    ],
)
def test_following_restriction_is_retained_as_conditional(text, field, condition):
    fact = extract_policy_evidence(description=text)[field]
    assert fact.status == "conditional" and fact.value is None
    assert condition in [span.quote for span in fact.evidence]
    assert public_detail_fields({"description": text})[field] is None


def test_description_can_qualify_title_but_unrelated_sentences_clear_context():
    fact = extract_policy_evidence(title="Pets allowed", description="Only with prior approval.")["pets_allowed"]
    assert fact.status == "conditional" and fact.value is None
    assert {span.source for span in fact.evidence} == {"title", "description"}
    fact = extract_policy_evidence(description="Pets allowed. Bright room. Only students.")["pets_allowed"]
    assert fact.status == "explicit" and fact.value is True


def test_question_does_not_conflict_with_actual_denial():
    fact = extract_policy_evidence(description="Pets allowed? No pets.")["pets_allowed"]
    assert fact.status == "explicit" and fact.value is False


@pytest.mark.parametrize(
    "text,field",
    [("No smoking?", "smoking_allowed"), ("Para 4 personas?", "room_capacity"),
     ("Children allowed?!", "children_allowed"), ("No couples?", "couples_allowed")],
)
def test_questions_do_not_establish_denials_or_numeric_facts(text, field):
    fact = extract_policy_evidence(description=text)[field]
    assert fact.status == "unknown" and fact.value is None


def test_independent_student_rule_does_not_qualify_pets():
    facts = extract_policy_evidence(description="Pets allowed. Solo estudiantes.")
    assert facts["pets_allowed"].status == "explicit"
    assert facts["pets_allowed"].value is True
    assert facts["students_only"].value is True


def test_conditional_continuation_does_not_erase_an_explicit_conflict():
    fact = extract_policy_evidence(
        description="No pets. Pets allowed. Only with prior approval."
    )["pets_allowed"]
    assert fact.status == "conflict" and fact.value is None


@pytest.mark.parametrize(
    "rule,condition,field",
    [
        ("No pets", "Except small dogs", "pets_allowed"),
        ("No se admiten mascotas", "Excepto perros pequenos", "pets_allowed"),
        ("No smoking", "Except on the terrace", "smoking_allowed"),
        ("Prohibido fumar", "Salvo en la terraza", "smoking_allowed"),
        ("No children", "Except with prior approval", "children_allowed"),
        ("Pets allowed", "Subject to prior approval", "pets_allowed"),
        ("Se admiten mascotas", "Previa autorizacion", "pets_allowed"),
    ],
)
@pytest.mark.parametrize("condition_first", [False, True])
def test_adjacent_exceptions_qualify_both_permissions_and_denials(rule, condition, field, condition_first):
    clauses = (condition, rule) if condition_first else (rule, condition)
    text = ". ".join(clauses) + "."
    fact = extract_policy_evidence(description=text)[field]
    assert fact.status == "conditional" and fact.value is None
    assert {span.quote for span in fact.evidence} == {rule, condition}
    assert public_detail_fields({"description": text})[field] is None


@pytest.mark.parametrize(
    "restriction",
    ["No perros", "No perros grandes", "Sin gatos", "Solo gatos", "Only small dogs",
     "No dogs", "No cats", "Dogs are not allowed"],
)
@pytest.mark.parametrize("condition_first", [False, True])
def test_species_restrictions_are_not_unconditional_permissions_in_either_order(restriction, condition_first):
    rule = "Se admiten mascotas"
    text = ". ".join((restriction, rule) if condition_first else (rule, restriction)) + "."
    fact = extract_policy_evidence(description=text)["pets_allowed"]
    assert fact.status == "conditional" and fact.value is None
    assert restriction in [span.quote for span in fact.evidence]
    assert public_detail_fields({"description": text})["pets_allowed"] is None


def test_description_exception_qualifies_title_denial_with_both_sources():
    fact = extract_policy_evidence(title="No pets", description="Except small dogs.")["pets_allowed"]
    assert fact.status == "conditional" and fact.value is None
    assert {span.source for span in fact.evidence} == {"title", "description"}


def test_unrelated_clause_and_question_clear_forward_condition_context():
    for middle in ("Bright room.", "Small dogs?"):
        fact = extract_policy_evidence(
            description=f"Only with prior approval. {middle} Pets allowed."
        )["pets_allowed"]
        assert fact.status == "explicit" and fact.value is True


def test_species_scope_and_exception_do_not_erase_explicit_conflict():
    fact = extract_policy_evidence(
        description="No pets. Except small dogs. Pets allowed. No dogs."
    )["pets_allowed"]
    assert fact.status == "conflict" and fact.value is None
