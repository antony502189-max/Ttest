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
