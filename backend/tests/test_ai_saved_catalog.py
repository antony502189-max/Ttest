import json
from dataclasses import replace

import pytest
from test_ai_housing_source import URL, snapshot

from app.schemas.ai_fact_bridge import BridgeRejected
from app.services.ai_saved_catalog import prepare_imported_housing


def imported():
    original = snapshot({})
    normalized = json.loads(original.normalized_json) | {"city": "Madrid", "title": "Habitación amueblada",
        "description": "Gastos incluidos. Contact PRIVATE_CONTACT +34600123456.", "source_url": URL,
        "furnished": True, "room_capacity": 9, "housing_evidence": {"clauses": ["invented"]}}
    return replace(original, normalized_json=json.dumps(normalized),
        raw_json=json.dumps({"html": '<nav>PRIVATE_CONTACT<li>Terraza</li></nav>'}), source_url=URL)


def test_minimized_existing_import_keeps_original_snapshot_cas_and_no_defaults():
    source = imported()
    prepared = prepare_imported_housing(source)
    assert prepared.source.snapshot_hash == source.reference.snapshot_hash
    assert prepared.source.source_record_id == source.reference.source_record_id
    facts = {fact.key for fact in prepared.facts}
    assert {"price", "rental_mode", "furnished", "bills_included", "geography", "accommodation"} <= facts
    assert not {"capacity_total", "terrace", "availability"} & facts
    assert "PRIVATE_CONTACT" not in str(prepared.sanitized_fields)
    assert "600123456" not in str(prepared.sanitized_fields)
    assert "PRIVATE_CONTACT" not in repr(source)


@pytest.mark.parametrize("url", [None, "https://www.pisocompartido.com/habitacion/different/"])
def test_missing_or_disagreeing_authoritative_source_url_fails_closed(url):
    with pytest.raises(BridgeRejected, match="SOURCE_URL"):
        prepare_imported_housing(replace(imported(), source_url=url))


def test_legacy_boolean_defaults_do_not_become_housing_evidence():
    source = imported()
    normalized = json.loads(source.normalized_json) | {"title": "", "description": "", "city": ""}
    prepared = prepare_imported_housing(replace(source, normalized_json=json.dumps(normalized)))
    assert {fact.key for fact in prepared.facts} == {"price", "rental_mode", "accommodation"}
