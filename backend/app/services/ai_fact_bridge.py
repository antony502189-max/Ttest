"""Offline protocol adapter. No upstream parser/cleaner import or default builder."""

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid5

from ..repositories.ai_fact_snapshots import CapturedParserSnapshot, FactSnapshotReader
from ..schemas.ai_fact_bridge import BridgeMapping, BridgeReference, BridgeRejected, ParserEvidencePacket, ParserSpan
from ..schemas.ai_fact_pipeline import FactJobClaim, SourceInput
from ..schemas.ai_listing_facts import EvidenceSpan, FactBatch, FactObservation, FactVocabulary, Version, digest

BRIDGE_VERSION = "offline-fact-bridge.v1"


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def upstream_content(packet: ParserEvidencePacket) -> dict:
    """Exactly #373's hashed content shape, separate from its routing/evidence."""
    return packet.model_dump(mode="json", include={"schema_version", "title", "description", "property_category",
                                                  "rental_category", "source_language", "provider_facts"})


@dataclass(frozen=True)
class PreparedFactInput:
    source: SourceInput
    _fields: tuple[tuple[str, str], ...] = field(repr=False)
    _facts: tuple[str, ...] = field(repr=False)

    @property
    def sanitized_fields(self) -> dict[str, str]:
        return dict(self._fields)

    @property
    def facts(self) -> tuple[FactObservation, ...]:
        return tuple(FactObservation.model_validate_json(value) for value in self._facts)

    def to_batch(self, claim: FactJobClaim, *, observed_at: datetime) -> FactBatch:
        if any(getattr(claim, key) != getattr(self.source, key) for key in SourceInput.model_fields):
            raise BridgeRejected("CLAIM_INPUT_MISMATCH")
        facts = [FactObservation.model_validate(f.model_dump() | {
            "fact_id": uuid5(claim.job_id, f"{f.key}:{f.scope_hash}:{f.origin}")}) for f in self.facts]
        batch = FactBatch(
            schema_version=claim.schema_version, taxonomy_version=claim.taxonomy_version,
            batch_id=claim.job_id, canonical_listing_id=claim.canonical_listing_id, source_record_id=claim.source_record_id,
            source_generation=claim.generation, content_hash=claim.content_hash, extractor_version=claim.extractor_version,
            observed_at=observed_at, source_status="active", last_successful_check_at=None,
            last_content_change_at=None, last_check_error_at=None, facts=facts,
        )
        batch.validate_evidence_against(dict(self.sanitized_fields))
        return batch


def _text_spans(spans: list[ParserSpan], fields: dict[str, str]) -> list[EvidenceSpan]:
    """Reconstruct complete sanitized clauses; never pick a substring of a negation."""
    groups: dict[tuple[str, str], int] = {}
    for span in spans:
        groups[(span.source, span.quote)] = groups.get((span.source, span.quote), 0) + 1
    result: list[EvidenceSpan] = []
    for (name, quote), expected in sorted(groups.items()):
        text = fields[name]
        offsets, start = [], 0
        while (at := text.find(quote, start)) >= 0:
            left, right = text[:at].rstrip(" \t\r"), text[at + len(quote):].lstrip(" \t\r")
            if (not left or left[-1] in ".!?;\n") and (not right or right[0] in ".!?;\n"):
                offsets.append(at)
            start = at + len(quote)
        if len(offsets) != expected:
            raise BridgeRejected("EVIDENCE_SPAN_AMBIGUOUS_OR_MISSING")
        result.extend(EvidenceSpan.model_validate({"field": name, "quote": quote, "start": at,
                                                  "end": at + len(quote)}) for at in offsets)
    return result


def _observation(reference: BridgeReference, *, key: str, status: str, value: dict | None,
                 qualifiers: dict, evidence: list[EvidenceSpan], origin: str) -> FactObservation:
    return FactObservation.model_validate({
        "fact_id": uuid5(reference.source_record_id, digest({"key": key, "qualifiers": qualifiers, "origin": origin})),
        "key": key, "status": status, "typed_value": value, "qualifiers": qualifiers,
        "evidence": [s.model_dump() for s in evidence], "origin": origin,
    })


def _merge(facts: list[FactObservation], reference: BridgeReference) -> list[FactObservation]:
    groups: dict[tuple[str, str, str], list[FactObservation]] = {}
    for fact in facts:
        groups.setdefault((fact.key, fact.scope_hash, fact.origin), []).append(fact)
    result = []
    for identity in sorted(groups):
        peers = groups[identity]
        explicit = [f for f in peers if f.status in {"explicit_allow", "explicit_deny"}]
        values = {digest({"status": f.status, "value": f.typed_value.model_dump(mode="json")})
                  for f in explicit if f.typed_value is not None}
        value = None
        if any(f.status == "conflict" for f in peers) or len(values) > 1:
            status = "conflict"
        elif any(f.status == "conditional" for f in peers):
            status = "conditional"
        elif explicit:
            status, value = explicit[0].status, explicit[0].typed_value.model_dump() if explicit[0].typed_value else None
        else:
            status = "unknown"
        evidence = {s.model_dump_json(): s for f in peers for s in f.evidence}
        if len(evidence) > 16:
            raise BridgeRejected("EVIDENCE_BOUND_EXCEEDED")
        result.append(_observation(reference, key=identity[0], status=status, value=value,
                                   qualifiers=peers[0].qualifiers.model_dump(exclude_none=True),
                                   evidence=[evidence[k] for k in sorted(evidence)], origin=identity[2]))
    return result


def bridge_packet(packet: ParserEvidencePacket, reference: BridgeReference, mapping: BridgeMapping,
                  vocabulary: FactVocabulary, *, extractor_version: Version) -> PreparedFactInput:
    """Caller must supply a reviewed sanitized packet and server-owned mappings."""
    try:
        packet = ParserEvidencePacket.model_validate(packet.model_dump())
        reference = BridgeReference.model_validate(reference)
        mapping = BridgeMapping.model_validate(mapping)
        vocabulary = FactVocabulary.model_validate(vocabulary)
        if (packet.canonical_listing_identifier, packet.source_identifier) != (
            reference.canonical_listing_id, reference.source_identifier
        ):
            raise BridgeRejected("PACKET_IDENTITY_MISMATCH")
        if digest(upstream_content(packet)) != packet.content_hash:
            raise BridgeRejected("UPSTREAM_CONTENT_HASH_MISMATCH")
        if packet.data_status != "ready":
            raise BridgeRejected("INSUFFICIENT_SOURCE_DATA")
        fields = {"title": packet.title, "description": packet.description,
                  "metadata.upstream_content": _json(upstream_content(packet)),
                  "metadata.policy_evidence": _json(packet.model_dump(mode="json")["policy_evidence"]),
                  "metadata.bridge_version": BRIDGE_VERSION,
                  "metadata.mapping": _json(mapping.model_dump(mode="json") | {
                      "rented_unit_capacity_fields": sorted(mapping.rented_unit_capacity_fields)})}
        facts: list[FactObservation] = []
        direct = {"pets_allowed": "pets", "children_allowed": "children", "couples_allowed": "couples",
                  "smoking_indoors_allowed": "smoking", "smoking_allowed": "smoking",
                  "smoking_outdoors_allowed": "smoking", "room_capacity": "capacity_total"}
        scoped_smoking = Counter((s.source, s.quote) for name in ("smoking_indoors_allowed", "smoking_outdoors_allowed")
            if name == "smoking_indoors_allowed" or "smoking_outdoors_allowed" in mapping.text_smoking_scopes
            for s in packet.policy_evidence[name].evidence)
        for old_key, policy in sorted(packet.policy_evidence.items()):
            if old_key == "students_only":
                if policy.status != "unknown":
                    raise BridgeRejected("UNSUPPORTED_TENANT_RULE")
                continue
            qualifiers: dict = {}
            if old_key == "room_capacity":
                if mapping.text_capacity_scope is None:
                    if policy.status != "unknown":
                        raise BridgeRejected("CAPACITY_SCOPE_UNVERIFIED")
                    continue
                qualifiers = {"inventory_scope": mapping.text_capacity_scope}
            elif old_key.startswith("smoking"):
                if old_key == "smoking_allowed" and policy.status == "conditional" and (
                    Counter((s.source, s.quote) for s in policy.evidence) <= scoped_smoking
                ):
                    # #373 repeats its precise scoped clauses as a generic
                    # conditional. Keep the same evidence in the precise fields;
                    # do not manufacture a single scope for the combined rule.
                    continue
                scope = "indoors" if old_key == "smoking_indoors_allowed" else mapping.text_smoking_scopes.get(
                    "smoking_allowed" if old_key == "smoking_allowed" else "smoking_outdoors_allowed")
                if scope is None:
                    if policy.status != "unknown":
                        raise BridgeRejected("SMOKING_SCOPE_UNVERIFIED")
                    continue
                qualifiers = {"smoking_scope": scope}
            status: str = policy.status
            value: dict | None = None
            if status == "explicit":
                status = "explicit_allow" if old_key == "room_capacity" or policy.value is True else "explicit_deny"
                value = ({"kind": "quantity", "value": policy.value, "unit": "persons"} if old_key == "room_capacity"
                         else {"kind": "policy", "allowed": policy.value})
            facts.append(_observation(reference, key=direct[old_key], status=status, value=value,
                                       qualifiers=qualifiers, evidence=_text_spans(policy.evidence, fields), origin="source_text"))
        for provider in packet.provider_facts:
            path = provider.evidence.provider_field
            if path is None or mapping.structured_fields.get(path) != provider.field:
                raise BridgeRejected("UNAPPROVED_STRUCTURED_FIELD")
            name = f"structured.{path}"
            quote = provider.evidence.quote
            if name in fields and fields[name] != quote:
                raise BridgeRejected("STRUCTURED_SPAN_COLLISION")
            fields[name] = quote
            span = EvidenceSpan(field="structured", provider_field=path, quote=quote, start=0, end=len(quote))
            values = []
            if provider.field == "room_capacity":
                if path not in mapping.rented_unit_capacity_fields:
                    raise BridgeRejected("CAPACITY_SCOPE_UNVERIFIED")
                values.append(("capacity_total", "explicit_allow", {"kind": "quantity", "value": provider.value, "unit": "persons"},
                               {"inventory_scope": "rented_unit"}))
            elif provider.field in {"pets_allowed", "children_allowed", "couples_allowed", "smoking_allowed"}:
                qualifiers = {}
                if provider.field == "smoking_allowed":
                    smoke = mapping.structured_smoking_scopes.get(path)
                    if smoke is None:
                        raise BridgeRejected("SMOKING_SCOPE_UNVERIFIED")
                    qualifiers = {"smoking_scope": smoke}
                values.append((direct[provider.field], "explicit_allow" if provider.value is True else "explicit_deny",
                               {"kind": "policy", "allowed": provider.value}, qualifiers))
            elif provider.field in {"furnished", "bills_included"}:
                values.append((provider.field, "explicit_allow", {"kind": "boolean", "value": provider.value}, {}))
            elif provider.field == "amenities" and isinstance(provider.value, list):
                for code in sorted(provider.value):
                    if code in {"balcony", "terrace"}:
                        values.append((code, "explicit_allow", {"kind": "boolean", "value": True}, {}))
                    elif code in mapping.amenity_codes:
                        values.append(("amenity", "explicit_allow", {"kind": "boolean", "value": True},
                                       {"amenity_code": mapping.amenity_codes[code]}))
                    else:
                        raise BridgeRejected("UNAPPROVED_AMENITY_MAPPING")
            else:
                raise BridgeRejected("UNSUPPORTED_SOURCE_FACT")
            for key, status, typed, qualifiers in values:
                facts.append(_observation(reference, key=key, status=status, value=typed, qualifiers=qualifiers,
                                           evidence=[span], origin="source_structured"))
        facts = _merge(facts, reference)
        for fact in facts:
            vocabulary.validate_fact(fact)
        source = SourceInput(source_record_id=reference.source_record_id, canonical_listing_id=reference.canonical_listing_id,
                             content_hash=digest(fields), snapshot_hash=reference.snapshot_hash,
                             schema_version="ai-facts.v1", taxonomy_version="ai-search.v1", extractor_version=extractor_version)
        # Enforce the exact AI-04 mapping/JSON limits before enqueue, not after claim.
        if len(fields) > 256 or sum(len(k.encode()) + len(v.encode()) for k, v in fields.items()) > 1_048_576 or len(facts) > 128:
            raise BridgeRejected("BRIDGE_INPUT_BOUND_EXCEEDED")
        return PreparedFactInput(source, tuple(sorted(fields.items())), tuple(f.model_dump_json() for f in facts))
    except BridgeRejected:
        raise
    except (ValueError, TypeError, AttributeError):
        raise BridgeRejected("INVALID_SANITIZED_PACKET_OR_MAPPING") from None


async def prepare_captured_source(reader: FactSnapshotReader, source_record_id: UUID, *,
                                  builder: Callable[[CapturedParserSnapshot], ParserEvidencePacket],
                                  mapping: BridgeMapping, vocabulary: FactVocabulary,
                                  extractor_version: Version) -> PreparedFactInput:
    # No default builder. The reviewed future minimizer runs after capture has
    # released its DB connection; old snapshot tokens fail AI-04 observe CAS.
    captured = await reader.capture(source_record_id)
    try:
        packet = builder(captured)
    except Exception:  # noqa: BLE001 -- Redact payloads in untrusted builder exception messages.
        raise BridgeRejected("SANITIZED_BUILDER_REJECTED") from None
    return bridge_packet(packet, captured.reference, mapping, vocabulary, extractor_version=extractor_version)
