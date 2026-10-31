"""Bounded Flatio JSON-LD mapping for the explicitly authorized closed pilot.

No HTTP, LLM, defaults, full text, contacts, address or photos are retained.
Generic smoking and InStock never become scoped/date inventory guarantees.
"""
import json
from decimal import Decimal, InvalidOperation

from ..schemas.ai_fact_bridge import BridgeReference
from ..schemas.ai_fact_pipeline import SourceInput
from ..schemas.ai_listing_facts import EvidenceSpan, digest
from .ai_fact_bridge import PreparedFactInput, _merge, _observation
from .ai_listing_input import clean_evidence_text
from .listing_evidence import extract_policy_evidence

VERSION = "flatio-closed.v1"


def prepare_flatio_room(room: dict, reference: BridgeReference) -> PreparedFactInput:
    fields = {"metadata.extractor": VERSION}
    facts = []

    def emit(key, path, raw, value, *, status="explicit_allow", qualifiers=None):
        quote = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        fields["structured." + path] = quote
        span = EvidenceSpan(field="structured", provider_field=path, quote=quote, start=0, end=len(quote))
        facts.append(_observation(reference, key=key, status=status, value=value,
                                  qualifiers=qualifiers or {}, evidence=[span], origin="source_structured"))

    # Only status/value, never the clause or description, survives minimization.
    policies = extract_policy_evidence(description=clean_evidence_text(str(room.get("description") or "")))
    pet_text = policies["pets_allowed"]
    fields["metadata.text_pets_status"] = pet_text.status
    pet_values = []
    if type(room.get("petsAllowed")) is bool:
        pet_values.append(("petsAllowed", room["petsAllowed"], room["petsAllowed"]))
    extras = room.get("additionalProperty")
    extras = extras if isinstance(extras, list) else []
    pet_rules = [(i, p.get("value")) for i, p in enumerate(extras)
                 if isinstance(p, dict) and p.get("propertyID") == "petsPolicy"]
    unhandled_pet_rule = any(v not in ("allowed", "not_allowed", "forbidden") for _, v in pet_rules)
    for i, value in pet_rules:
        if value in ("allowed", "not_allowed", "forbidden"):
            pet_values.append((f"additionalProperty[{i}].value", value, value == "allowed"))
    # Any text policy or unhandled restriction prevents a broad guarantee.
    # A later reviewed text mapping may recover coverage; absence is not allow.
    if pet_text.status == "unknown" and not unhandled_pet_rule:
        for path, raw, allowed in pet_values:
            emit("pets", path, raw, {"kind": "policy", "allowed": allowed},
                 status="explicit_allow" if allowed else "explicit_deny")
    else:
        fields["metadata.pets_withheld"] = "unhandled_rule_or_text_policy"
    occupancy = room.get("occupancy")
    capacity = occupancy.get("maxValue") if isinstance(occupancy, dict) else None
    if type(capacity) is int and 1 <= capacity <= 99:
        emit("capacity_total", "occupancy.maxValue", capacity,
             {"kind": "quantity", "value": capacity, "unit": "persons"}, qualifiers={"inventory_scope": "rented_unit"})
    offer = room.get("offers")
    offer = offer if isinstance(offer, dict) else {}
    offer_extras = offer.get("additionalProperty")
    offer_extras = offer_extras if isinstance(offer_extras, list) else []
    for key, code, entries, prefix in (("furnished", "furnished", extras, "additionalProperty"),
                                       ("bills_included", "utilitiesIncluded", offer_extras, "offers.additionalProperty")):
        for i, entry in enumerate(entries):
            if isinstance(entry, dict) and entry.get("propertyID") == code and type(entry.get("value")) is bool:
                emit(key, f"{prefix}[{i}].value", entry["value"], {"kind": "boolean", "value": entry["value"]})
    for i, entry in enumerate(room.get("amenityFeature") or []):
        if isinstance(entry, dict) and entry.get("propertyID") == "wifi" and type(entry.get("value")) is bool:
            emit("amenity", f"amenityFeature[{i}].value", entry["value"], {"kind": "boolean", "value": entry["value"]},
                 qualifiers={"amenity_code": "wifi"})
    spec = offer.get("priceSpecification")
    spec = spec if isinstance(spec, dict) else {}
    reference_quantity = spec.get("referenceQuantity")
    reference_quantity = reference_quantity if isinstance(reference_quantity, dict) else {}
    try:
        amount = Decimal(str(offer.get("price")))
        same = amount == Decimal(str(spec.get("price")))
        valid = amount.is_finite() and 0 < amount <= Decimal("9999999.99") and amount == amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        valid = same = False
        amount = Decimal(0)
    if (valid and same and offer.get("priceCurrency") == spec.get("priceCurrency") == "EUR"
            and reference_quantity.get("unitCode") == "MON" and reference_quantity.get("value") == 1):
        money = {"kind": "money", "amount": format(amount, ".2f"), "currency": "EUR", "period": "monthly"}
        emit("price", "offers.priceSpecification", {"price": spec["price"], "priceCurrency": "EUR",
             "referenceQuantity": {"value": 1, "unitCode": "MON"}}, money)
    fields["metadata.in_stock"] = str(offer.get("availability") == "https://schema.org/InStock").lower()
    # Every unsupported/missing field is represented as unknown by consumers.
    # Keep one unknown fact if absolutely no supported evidence was admitted.
    if not facts:
        facts.append(_observation(reference, key="pets", status="unknown", value=None,
                                  qualifiers={}, evidence=[], origin="source_structured"))
    merged = _merge(facts, reference)
    source = SourceInput(source_record_id=reference.source_record_id, canonical_listing_id=reference.canonical_listing_id,
                         content_hash=digest(fields), snapshot_hash=reference.snapshot_hash, schema_version="ai-facts.v1",
                         taxonomy_version="ai-search.v1", extractor_version=VERSION)
    return PreparedFactInput(source, tuple(sorted(fields.items())), tuple(f.model_dump_json() for f in merged))
