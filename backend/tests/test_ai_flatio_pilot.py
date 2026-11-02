from uuid import UUID

import pytest

from app.schemas.ai_fact_bridge import BridgeReference
from app.services.ai_flatio_pilot import prepare_flatio_room

REF = BridgeReference(source_record_id=UUID(int=1), canonical_listing_id=UUID(int=2),
                      source_identifier="Flatio:fixture", snapshot_hash="a" * 64)


def prepare(**room):
    return prepare_flatio_room(room, REF)


def test_missing_is_unknown_and_sensitive_fields_never_survive():
    ready = prepare(name="private", description="private name phone +34 612345678", address={"streetAddress": "private"},
                    image=["https://example.invalid/private"], smokingAllowed=True)
    assert all(f.status == "unknown" for f in ready.facts)
    assert "private" not in str(ready.sanitized_fields)
    assert not any(f.key in {"smoking", "availability", "available_spots"} for f in ready.facts)


@pytest.mark.parametrize("raw", [True, False])
def test_explicit_pets_boolean_and_original_quote(raw):
    fact = prepare(petsAllowed=raw).facts[0]
    assert fact.status == ("explicit_allow" if raw else "explicit_deny")
    assert fact.evidence[0].quote == str(raw).lower()


def test_conflict_and_unhandled_rules_do_not_become_allow():
    conflict = prepare(petsAllowed=True, additionalProperty=[{"propertyID": "petsPolicy", "value": "forbidden"}])
    assert conflict.facts[0].status == "conflict"
    assert any(e.quote == '"forbidden"' for e in conflict.facts[0].evidence)
    for value in ("on_request", "small_dogs_only", "unknown"):
        assert prepare(petsAllowed=True, additionalProperty=[{"propertyID": "petsPolicy", "value": value}]).facts[0].status == "unknown"
    assert prepare(petsAllowed=True, description="No pets.").facts[0].status == "unknown"


@pytest.mark.parametrize("change", [{"priceCurrency": "USD"}, {"price": 200},
                                  {"referenceQuantity": {"value": 1, "unitCode": "DAY"}}])
def test_price_requires_agreement_currency_and_period(change):
    spec = {"price": 100, "priceCurrency": "EUR", "referenceQuantity": {"value": 1, "unitCode": "MON"}}
    good = {"price": 100, "priceCurrency": "EUR", "priceSpecification": spec}
    assert next(f for f in prepare(offers=good).facts if f.key == "price").typed_value.amount == "100.00"
    assert not any(f.key == "price" for f in prepare(offers=good | {"priceSpecification": spec | change}).facts)


def test_capacity_is_not_available_spots_and_false_furnished_is_confirmed():
    ready = prepare(occupancy={"maxValue": 2}, additionalProperty=[{"propertyID": "furnished", "value": False}],
                    offers={"availability": "https://schema.org/InStock"})
    facts = {f.key: f for f in ready.facts}
    assert facts["capacity_total"].qualifiers.inventory_scope == "rented_unit"
    assert facts["furnished"].typed_value.value is False
    assert not {"available_spots", "availability", "couples", "children"} & facts.keys()


def test_existing_santa_cruz_policy_accepts_structured_tenerife_but_not_other_island():
    from app.external_sources import is_in_import_scope
    assert is_in_import_scope({"province": "Tenerife", "city": "Santa Cruz de Tenerife", "country": "ES"}, "santa_cruz")
    assert not is_in_import_scope({"province": "Las Palmas", "city": "Las Palmas", "country": "ES"}, "santa_cruz")
