import json
from uuid import uuid4

import pytest

from app.repositories.ai_fact_snapshots import CapturedParserSnapshot
from app.schemas.ai_fact_bridge import BridgeReference, BridgeRejected
from app.schemas.ai_search_intent import Criteria, SearchIntent
from app.services.ai_deepseek_intent import ProviderFailure
from app.services.ai_pisocompartido_price import prepare_price
from demo.entry import BINDING, PHRASES, DemoBudget, DemoGate


def snapshot(**updates):
    sid = uuid4()
    value = {"source_name": "PisoCompartido", "source_price_text": "450 €/mes", "rental_mode": "long",
        "price_currency": "EUR", "price_period": "month", "price_is_from": False, "price_amount": 450,
        "pets_allowed": True, "phone": "PRIVATE_CONTACT", "description": "PRIVATE_TEXT"}
    value.update(updates)
    return CapturedParserSnapshot(BridgeReference(source_record_id=sid, canonical_listing_id=uuid4(),
        source_identifier=f"PisoCompartido:{sid.hex}", snapshot_hash="a" * 64), "{}", json.dumps(value), value["source_price_text"])


def test_price_mapping_never_admits_contacts_or_default_booleans():
    ready = prepare_price(snapshot())
    assert {f.key for f in ready.facts} == {"price", "rental_mode"}
    data = json.dumps(ready.sanitized_fields)
    assert "PRIVATE" not in data and "phone" not in data and "pets" not in data
    assert ready.source.snapshot_hash == "a" * 64


@pytest.mark.parametrize("update", [{"price_amount": 451}, {"price_is_from": True},
    {"price_currency": "USD"}, {"price_period": "week"}, {"rental_mode": "holiday"},
    {"source_name": "Other"}, {"source_price_text": "desde 450 €/mes"},
    {"price_period": None}, {"source_price_text": "450 €/mes, 20€ gastos"}])
def test_unconfirmed_or_disagreeing_price_is_rejected(update):
    with pytest.raises(BridgeRejected):
        prepare_price(snapshot(**update))


def test_independent_demo_budget_reopen_cannot_reset_three_attempt_limit(tmp_path):
    path = tmp_path / "demo.sqlite3"
    budget = DemoBudget(path, corpus_sha256=BINDING)
    for _ in range(3):
        budget.reserve()
    with pytest.raises(ProviderFailure, match="BUDGET_EXHAUSTED"):
        DemoBudget(path, corpus_sha256=BINDING).reserve()
    assert budget.summary()["attempts"] == 3
    assert budget.summary()["reserved_micro_usd"] == 33180
    with pytest.raises(ProviderFailure, match="JOURNAL_MISMATCH"):
        DemoBudget(path, corpus_sha256="b" * 64)


async def test_exact_demo_phrases_and_states_only_before_provider_io():
    gate = DemoGate()
    current = SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1", session_id=uuid4(),
        version=0, criteria=Criteria.model_validate_json('{"rental_mode":{"strength":"hard","value":"long"}}'))
    value = await gate.prepare(PHRASES[0], current)
    assert set(value.model_dump()) == {"schema_version", "provider", "purpose", "text", "criteria"}
    for text in ("PRIVATE_EMAIL@example.invalid", PHRASES[1], PHRASES[0] + " "):
        with pytest.raises(ProviderFailure, match="INPUT_NOT_APPROVED"):
            await gate.prepare(text, current)
    budget = {"strength": "hard", "value": {"amount": "600.00", "currency": "EUR", "period": "monthly"}}
    refined = current.model_copy(update={"criteria": Criteria.model_validate_json(json.dumps({
        "rental_mode": {"strength": "hard", "value": "long"}, "budget": budget}))})
    await gate.prepare(PHRASES[1], refined)
