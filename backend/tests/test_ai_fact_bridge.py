import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.ai_fact_bridge import BridgeMapping, BridgeReference, BridgeRejected, ParserEvidencePacket
from app.schemas.ai_fact_pipeline import FactJobClaim
from app.schemas.ai_listing_facts import FactVocabulary, digest
from app.services.ai_fact_bridge import BRIDGE_VERSION, bridge_packet, upstream_content
from app.services.ai_fact_resolver import resolve_sources

FIXTURES = json.loads((Path(__file__).parent / "fixtures/ai_fact_bridge/parser-373-synthetic.json").read_text(encoding="utf-8"))


def packet(name):
    return ParserEvidencePacket.model_validate_json(json.dumps(next(c["packet"] for c in FIXTURES["cases"] if c["name"] == name)))


def mapping(**changes):
    return BridgeMapping.model_validate({
        "structured_fields": {"details.furnished": "furnished", "details.bills": "bills_included", "details.amenities": "amenities",
                              "rules.pets": "pets_allowed", "rules.pets_other": "pets_allowed",
                              "details.unit_capacity": "room_capacity", "rules.smoking_indoors": "smoking_allowed"},
        "rented_unit_capacity_fields": frozenset({"details.unit_capacity"}), "text_capacity_scope": None,
        "structured_smoking_scopes": {"rules.smoking_indoors": "indoors"},
        "text_smoking_scopes": {"smoking_outdoors_allowed": "terrace"},
        "amenity_codes": {"wifi": "test_wifi", "internet": "test_wifi"},
    } | changes)


def vocabulary():
    return FactVocabulary(amenity_codes=frozenset({"test_wifi"}), catalog_other_codes=frozenset(),
                          tenant_group_codes=frozenset(), municipality_zones=frozenset())


def reference(value):
    return BridgeReference(source_record_id=uuid4(), canonical_listing_id=value.canonical_listing_identifier,
                           source_identifier=value.source_identifier, snapshot_hash="a" * 64)


def prepare(value, *, rules=None, ref=None):
    return bridge_packet(value, ref or reference(value), rules or mapping(), vocabulary(), extractor_version="fixture-bridge.v1")


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=lambda c: c["name"])
def test_exact_pinned_upstream_packet_hash_and_protocol(case):
    value = ParserEvidencePacket.model_validate_json(json.dumps(case["packet"]))
    assert digest(upstream_content(value)) == value.content_hash
    assert FIXTURES["synthetic"] is True
    assert FIXTURES["upstream_revision"] == "fcae378d9dbbc8447f18df150327180f6f2c8231"


@pytest.mark.parametrize("name,status", [("pets_deny", "explicit_deny"), ("pets_allow", "explicit_allow"),
                                       ("small_dog_conditional", "conditional"), ("pets_conflict", "conflict")])
def test_policy_translation_preserves_uncertainty_and_negative_quotes(name, status):
    ready = prepare(packet(name))
    fact = next(f for f in ready.facts if f.key == "pets")
    assert fact.status == status
    if status in {"conditional", "conflict"}:
        assert fact.typed_value is None
    assert all(s.quote == ready.sanitized_fields[s.field][s.start:s.end] for s in fact.evidence)
    assert not any(f.key in {"rental_mode", "accommodation", "geography", "price", "available_spots"} for f in ready.facts)


def test_structured_false_is_confirmed_boolean_and_amenities_keep_supported_keys():
    ready = prepare(packet("structured_false_and_amenities"))
    facts = {f.key: f for f in ready.facts if f.origin == "source_structured"}
    assert facts["furnished"].status == "explicit_allow" and facts["furnished"].typed_value.value is False
    assert facts["bills_included"].typed_value.value is False
    assert facts["balcony"].typed_value.value is True
    assert facts["amenity"].qualifiers.amenity_code == "test_wifi"
    assert facts["amenity"].evidence[0].provider_field == "details.amenities"


def test_generic_smoking_duplicate_is_replaced_only_by_its_exact_scoped_evidence():
    ready = prepare(packet("smoking_scoped"))
    smoking = {f.qualifiers.smoking_scope: f for f in ready.facts if f.key == "smoking" and f.status != "unknown"}
    assert set(smoking) == {"indoors", "terrace"}
    assert smoking["indoors"].status == "explicit_deny"
    assert smoking["terrace"].status == "explicit_allow"
    assert "terraza" in smoking["terrace"].evidence[0].quote


@pytest.mark.parametrize("name,reason", [("capacity_couple", "CAPACITY_SCOPE_UNVERIFIED"),
                                       ("smoking_unscoped", "SMOKING_SCOPE_UNVERIFIED"),
                                       ("students_only", "UNSUPPORTED_TENANT_RULE"),
                                       ("insufficient", "INSUFFICIENT_SOURCE_DATA")])
def test_unreviewed_scope_or_unsupported_narrowing_is_rejected(name, reason):
    with pytest.raises(BridgeRejected, match=reason):
        prepare(packet(name))


def test_capacity_is_total_only_with_explicit_server_scope_never_available_spots():
    ready = prepare(packet("capacity_couple"), rules=mapping(text_capacity_scope="rented_unit"))
    capacity = next(f for f in ready.facts if f.key == "capacity_total")
    assert capacity.typed_value.value == 2 and capacity.qualifiers.inventory_scope == "rented_unit"
    assert not any(f.key == "available_spots" for f in ready.facts)
    structured = prepare(packet("structured_capacity"))
    assert next(f for f in structured.facts if f.key == "capacity_total").typed_value.value == 3
    with pytest.raises(BridgeRejected, match="CAPACITY_SCOPE_UNVERIFIED"):
        prepare(packet("structured_capacity"), rules=mapping(rented_unit_capacity_fields=frozenset()))


def test_policy_is_not_inferred_from_marketing_or_metadata():
    ready = prepare(packet("marketing_capacity_unknown"))
    assert all(f.status == "unknown" for f in ready.facts)


def test_repeated_whole_clauses_and_unicode_offsets_are_exact():
    repeated = prepare(packet("repeated_negative"))
    spans = next(f.evidence for f in repeated.facts if f.key == "pets")
    assert [s.start for s in spans] == sorted({s.start for s in spans})
    assert len(spans) == 2
    unicode = prepare(packet("unicode_newline"))
    span = next(f for f in unicode.facts if f.key == "pets").evidence[0]
    assert unicode.sanitized_fields[span.field][span.start:span.end] == "No pets"
    assert span.start != len(unicode.sanitized_fields[span.field][:span.start].encode())


def test_clipped_negative_or_lost_duplicate_evidence_is_rejected():
    value = packet("pets_allow").model_dump()
    value["description"] = "No Se aceptan mascotas."
    altered = ParserEvidencePacket.model_validate(value)
    value["content_hash"] = digest(upstream_content(altered))
    with pytest.raises(BridgeRejected, match="EVIDENCE_SPAN"):
        prepare(ParserEvidencePacket.model_validate(value))
    repeated = packet("repeated_negative").model_dump()
    repeated["policy_evidence"]["pets_allowed"]["evidence"].pop()
    with pytest.raises(BridgeRejected, match="EVIDENCE_SPAN"):
        prepare(ParserEvidencePacket.model_validate(repeated))


def test_source_identity_and_hash_bind_packet_before_enqueue():
    value = packet("pets_deny")
    ref = reference(value)
    for field, replacement in (("canonical_listing_id", uuid4()), ("source_identifier", "synthetic:different")):
        bad = BridgeReference.model_validate(ref.model_dump() | {field: replacement})
        with pytest.raises(BridgeRejected, match="PACKET_IDENTITY_MISMATCH"):
            prepare(value, ref=bad)
    changed = value.model_dump() | {"description": "Pets allowed"}
    with pytest.raises(BridgeRejected, match="UPSTREAM_CONTENT_HASH_MISMATCH"):
        prepare(ParserEvidencePacket.model_validate(changed))


def test_compatibility_hash_binds_policy_decisions_omitted_by_upstream_hash():
    value = packet("pets_allow")
    ref = reference(value)
    original = prepare(value, ref=ref)
    changed = value.model_dump()
    changed["policy_evidence"]["pets_allowed"]["value"] = False
    other = ParserEvidencePacket.model_validate(changed)
    assert digest(upstream_content(other)) == value.content_hash
    assert prepare(other, ref=ref).source.content_hash != original.source.content_hash
    assert original.sanitized_fields["metadata.bridge_version"] == BRIDGE_VERSION


def test_rule_or_typed_value_changes_change_bridge_hash_even_when_quote_is_identical():
    value = packet("structured_capacity")
    ref = reference(value)
    ready = prepare(value, ref=ref)
    changed = value.model_dump()
    changed["provider_facts"][0]["value"] = 4
    changed["content_hash"] = digest(upstream_content(ParserEvidencePacket.model_validate(changed)))
    assert prepare(ParserEvidencePacket.model_validate(changed), ref=ref).source.content_hash != ready.source.content_hash
    rules = mapping(text_capacity_scope="rented_unit")
    assert prepare(value, rules=rules, ref=ref).source.content_hash != ready.source.content_hash


def test_provider_paths_are_explicit_and_cannot_supply_owner_or_sql_fields():
    with pytest.raises(BridgeRejected, match="UNAPPROVED_STRUCTURED_FIELD"):
        prepare(packet("structured_capacity"), rules=mapping(structured_fields={}, rented_unit_capacity_fields=frozenset(),
                                                            structured_smoking_scopes={}))
    bad = packet("pets_deny").model_dump() | {"owner_user_id": uuid4()}
    with pytest.raises(ValidationError):
        ParserEvidencePacket.model_validate(bad)


def test_prepared_payload_is_detached_and_claim_bound():
    ready = prepare(packet("pets_deny"))
    copy = ready.sanitized_fields
    copy["description"] = "mutated"
    next(f for f in ready.facts if f.key == "pets").evidence.clear()
    claim = FactJobClaim(**ready.source.model_dump(), job_id=uuid4(), generation=1, fence=1,
                         lease_until=datetime(2027, 1, 1, tzinfo=UTC))
    batch = ready.to_batch(claim, observed_at=datetime(2026, 10, 26, tzinfo=UTC))
    batch.validate_evidence_against(ready.sanitized_fields)
    assert "No pets" not in repr(ready)
    with pytest.raises(BridgeRejected, match="CLAIM_INPUT_MISMATCH"):
        ready.to_batch(claim.model_copy(update={"snapshot_hash": "b" * 64}), observed_at=datetime(2026, 10, 26, tzinfo=UTC))


def test_structured_text_contradiction_reaches_existing_resolver_as_conflict():
    ready = prepare(packet("structured_text_conflict"))
    claim = FactJobClaim(**ready.source.model_dump(), job_id=uuid4(), generation=1, fence=1,
                         lease_until=datetime(2027, 1, 1, tzinfo=UTC))
    batch = ready.to_batch(claim, observed_at=datetime(2026, 10, 26, tzinfo=UTC))
    result = resolve_sources(canonical_listing_id=batch.canonical_listing_id, batches=[batch], input_hash="a" * 64,
                             feature_revision=1, resolver_version="test.v1", computed_at=batch.observed_at)
    assert next(f for f in result.features if f.key == "pets").status == "conflict"


def test_fixture_cleaner_results_are_not_a_privacy_approval():
    value = packet("sanitized_fixture_contacts")
    ready = prepare(value)
    assert all("fixture@example.invalid" not in s for s in ready.sanitized_fields.values())
    assert "DO_NOT_EXPORT" not in value.description
    # The adapter consumes this fixture already cleaned by the historical builder.
    # It neither imports that cleaner nor claims to detect all PII itself.


@pytest.mark.parametrize("change", [
    {"schema_version": "listing-evidence-v2"}, {"raw_payload": {}}, {"title": 1},
    {"source_identifier": "https://example.invalid/listing"}, {"content_hash": "bad"},
])
def test_strict_packet_rejects_unknown_version_raw_envelope_and_coercion(change):
    with pytest.raises(ValidationError):
        ParserEvidencePacket.model_validate(packet("pets_deny").model_dump() | deepcopy(change))


def rehash(data):
    value = ParserEvidencePacket.model_validate(data)
    return ParserEvidencePacket.model_validate(data | {"content_hash": digest(upstream_content(value))})


def test_two_structured_fields_merge_without_last_value_winning():
    data = packet("structured_text_conflict").model_dump()
    second = deepcopy(data["provider_facts"][0])
    second["value"] = False
    second["evidence"].update(provider_field="rules.pets_other", quote="No mascotas")
    data["provider_facts"].append(second)
    ready = prepare(rehash(data))
    fact = next(f for f in ready.facts if f.key == "pets" and f.origin == "source_structured")
    assert fact.status == "conflict" and fact.typed_value is None
    assert {e.provider_field for e in fact.evidence} == {"rules.pets", "rules.pets_other"}


def test_one_structured_path_cannot_claim_two_different_quotes():
    data = packet("structured_text_conflict").model_dump()
    other = deepcopy(data["provider_facts"][0])
    other["evidence"]["quote"] = "Different text"
    data["provider_facts"].append(other)
    with pytest.raises(BridgeRejected, match="STRUCTURED_SPAN_COLLISION"):
        prepare(rehash(data))


def test_unapproved_amenity_code_and_unsupported_provider_fact_fail_closed():
    with pytest.raises(BridgeRejected, match="INVALID_SANITIZED_PACKET_OR_MAPPING"):
        prepare(packet("structured_false_and_amenities"), rules=mapping(amenity_codes={"wifi": "unapproved"}))
    data = packet("structured_text_conflict").model_dump()
    data["provider_facts"][0]["field"] = "empadronamiento_allowed"
    custom = mapping(structured_fields={"rules.pets": "empadronamiento_allowed"},
                     rented_unit_capacity_fields=frozenset(), structured_smoking_scopes={})
    with pytest.raises(BridgeRejected, match="UNSUPPORTED_SOURCE_FACT"):
        prepare(rehash(data), rules=custom)


@pytest.mark.parametrize("old_key,value", [("room_capacity", True), ("pets_allowed", 2), ("pets_allowed", "false")])
def test_policy_field_types_never_coerce_boolean_and_capacity(old_key, value):
    data = packet("pets_allow").model_dump()
    data["policy_evidence"][old_key].update(status="explicit", value=value,
        evidence=[{"source": "description", "quote": "Se aceptan mascotas", "provider_field": None}])
    with pytest.raises(ValidationError):
        ParserEvidencePacket.model_validate(data)


def test_mapping_capacity_attestation_requires_exact_provider_field():
    with pytest.raises(ValidationError, match="capacity scope"):
        mapping(rented_unit_capacity_fields=frozenset({"rules.pets"}))
