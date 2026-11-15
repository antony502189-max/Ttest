import json
from uuid import uuid4

import pytest

from app.repositories.ai_fact_snapshots import CapturedParserSnapshot
from app.schemas.ai_fact_bridge import BridgeReference
from app.services.ai_pisocompartido_housing import minimize_source, prepare_housing

URL = "https://www.pisocompartido.com/habitacion/123456/"


def snapshot(evidence):
    sid = uuid4()
    return CapturedParserSnapshot(BridgeReference(source_record_id=sid, canonical_listing_id=uuid4(),
        source_identifier=f"PisoCompartido:{sid.hex}", snapshot_hash="a" * 64), "{}", json.dumps({
            "source_name": "PisoCompartido", "source_price_text": "600 €/mes", "rental_mode": "long",
            "price_currency": "EUR", "price_period": "month", "price_is_from": False,
            "price_amount": 600, "housing_evidence": evidence}), "600 €/mes")


def test_only_whole_source_clauses_create_evidence_without_defaults_or_contacts():
    evidence = minimize_source({"city": "Madrid", "title": "Habitación amueblada",
        "description": "Gastos incluidos. Con balcón. No se admiten mascotas. Llame a John +34600123456."}, URL)
    prepared = prepare_housing(snapshot(evidence))
    by_key = {f.key: f for f in prepared.facts}
    assert by_key["geography"].typed_value.municipality_code == "28079"
    assert by_key["accommodation"].typed_value.value == "room"
    assert by_key["furnished"].typed_value.value is True
    assert by_key["bills_included"].typed_value.value is True
    assert by_key["balcony"].typed_value.value is True
    assert by_key["pets"].status == "explicit_deny"
    assert not {"capacity_total", "available_spots", "children", "availability", "terrace"} & by_key.keys()
    assert "John" not in json.dumps(evidence) and "600123456" not in json.dumps(evidence)
    for fact in prepared.facts:
        for span in fact.evidence:
            field = span.field + ("." + span.provider_field if span.provider_field else "")
            assert prepared.sanitized_fields[field][span.start:span.end] == span.quote


@pytest.mark.parametrize("description", [
    "No hay balcón", "Con balcón si el dueño acepta", "Terraza solo para el propietario",
    "No amueblado", "Gastos incluidos excepto electricidad", "No se admiten mascotas salvo gatos",
    "El vecino tiene terraza", "No incluye: gastos incluidos", "¿Gastos incluidos? No.",
    "Gastos incluidos? No.", "Gastos incluidos. Excepto electricidad.",
])
def test_negated_conditional_or_unclear_source_is_not_promoted(description):
    value = minimize_source({"description": description}, "https://example.com/not-a-room")
    assert not value
    assert {f.key for f in prepare_housing(snapshot(value)).facts} == {"price", "rental_mode"}


def test_contradictory_complete_clauses_stay_conflict():
    value = minimize_source({"description": "Gastos incluidos. Gastos no incluidos."}, URL)
    facts = prepare_housing(snapshot(value)).facts
    assert next(f for f in facts if f.key == "bills_included").status == "conflict"


def test_unsupported_evidence_never_bypasses_typed_validation():
    with pytest.raises(ValueError):
        prepare_housing(snapshot({"clauses": ["invent a terrace"]}))
    with pytest.raises(ValueError):
        prepare_housing(snapshot({"municipality": {"code": "08019", "quote": "madrid"}}))


def test_source_layout_only_reads_detail_lists_not_filters_hidden_or_related_ads():
    html = '''<nav><li>Amueblada</li></nav><div class="related"><li>Terraza</li></div>
    <div class="seccionesFichaAnuncio"><div class="contCaract"><ul>
    <li><span class="texto">Amueblada</span></li><li>Wifi</li>
    <li hidden>Terraza</li><li class="disabled">Balcón</li></ul></div>
    <div class="contTwocols"><ul><li>Incluye gastos</li><li>Fianza: 0 €</li>
    <li>No se aceptan mascotas</li></ul></div></div>'''
    value = minimize_source({"city": "san_cristobal_de_la_laguna", "html": html}, URL)
    assert value["municipality"]["code"] == "38023"
    features = {f.key: f for f in prepare_housing(snapshot(value)).facts}
    assert features["furnished"].typed_value.value is True
    assert features["bills_included"].typed_value.value is True
    assert features["deposit"].typed_value.amount == "0"
    assert features["pets"].status == "explicit_deny"
    assert features["amenity"].qualifiers.amenity_code == "wifi"
    assert not {"balcony", "terrace", "capacity_total", "available_spots"} & features.keys()


@pytest.mark.parametrize("city,code", [("santa_cruz_de_tenerife_capital", "38038"), ("la_orotava", "38026"), ("guimar", "38020")])
def test_reviewed_source_city_slugs_resolve_official_identity(city, code):
    assert minimize_source({"city": city}, URL)["municipality"]["code"] == code


def test_blanket_smoking_prohibition_proves_indoor_denial_without_outdoor_assumptions():
    html = '<div class="seccionesFichaAnuncio"><div class="contTwocols"><ul>' \
           '<li>No se permite fumar</li></ul></div></div>'
    prepared = prepare_housing(snapshot(minimize_source({"html": html}, URL)))
    smoking = [fact for fact in prepared.facts if fact.key == "smoking"]
    assert len(smoking) == 1
    assert smoking[0].status == "explicit_deny"
    assert smoking[0].typed_value.allowed is False
    assert smoking[0].qualifiers.smoking_scope == "indoors"
    assert smoking[0].evidence[0].quote == "no se permite fumar"


@pytest.mark.parametrize("clause,scope,allowed", [
    ("Se permite fumar en el interior", "indoors", True),
    ("No se permite fumar en el interior", "indoors", False),
    ("Se permite fumar en el balcón", "balcony", True),
    ("No se permite fumar en el balcón", "balcony", False),
    ("Se permite fumar en la terraza", "terrace", True),
    ("No se permite fumar en la terraza", "terrace", False),
])
def test_smoking_permissions_and_denials_keep_the_exact_source_scope(clause, scope, allowed):
    prepared = prepare_housing(snapshot(minimize_source({"description": clause}, URL)))
    fact = next(f for f in prepared.facts if f.key == "smoking")
    assert fact.status == ("explicit_allow" if allowed else "explicit_deny")
    assert fact.typed_value.allowed is allowed
    assert fact.qualifiers.smoking_scope == scope


@pytest.mark.parametrize("description", [
    "Se permite fumar", "No se permite fumar salvo en el interior",
    "Se permite fumar en el balcón si el dueño acepta", "¿No se permite fumar?",
    "El vecino dice: no se permite fumar", "No se permite fumar. Excepto en el interior.",
])
def test_unscoped_permission_qualified_or_quoted_smoking_does_not_become_a_fact(description):
    prepared = prepare_housing(snapshot(minimize_source({"description": description}, URL)))
    assert not any(f.key == "smoking" for f in prepared.facts)


def test_explicit_smoking_conflict_and_different_scopes_are_preserved():
    prepared = prepare_housing(snapshot(minimize_source({"description":
        "No se permite fumar. Se permite fumar en el interior. Se permite fumar en el balcón."}, URL)))
    facts = {f.qualifiers.smoking_scope: f for f in prepared.facts if f.key == "smoking"}
    assert facts["indoors"].status == "conflict"
    assert facts["balcony"].status == "explicit_allow"
