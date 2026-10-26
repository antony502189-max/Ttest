"""Conservative source-only resolver. No owner precedence, scoring or query matcher."""

from datetime import datetime
from uuid import UUID

from ..schemas.ai_listing_facts import (
    FactBatch,
    FactObservation,
    FactStatus,
    FactValue,
    SearchFeature,
    SearchProjection,
    digest,
)

MAX_SOURCE_OBSERVATIONS = 1024


def _overlap(a: FactValue, b: FactValue) -> bool:
    if a.key != b.key:
        return False
    x, y = a.qualifiers, b.qualifiers
    if a.key == "amenity":
        return x.amenity_code == y.amenity_code
    if a.key == "pets":
        if x.species is not None and y.species is not None and x.species != y.species:
            return False
        if x.size not in {None, "unspecified"} and y.size not in {None, "unspecified"} and x.size != y.size:
            return False
    if a.key == "smoking":
        if x.smoking_scope == y.smoking_scope:
            return True
        if "indoors" in {x.smoking_scope, y.smoking_scope}:
            return False
        return "outdoors" in {x.smoking_scope, y.smoking_scope}
    # Unknown catalog tenant-group relationships, count ranges and approval
    # qualifiers are conservatively overlapping, never assumed disjoint.
    return True


def resolve_sources(
    *, canonical_listing_id: UUID, batches: list[FactBatch], input_hash: str,
    feature_revision: int, resolver_version: str, computed_at: datetime,
) -> SearchProjection:
    if len(batches) > 128 or sum(len(b.facts) for b in batches) > MAX_SOURCE_OBSERVATIONS:
        raise ValueError("offline resolver input exceeds supported bound")
    observations: list[FactObservation] = []
    sources = set()
    for item in batches:
        batch = FactBatch.model_validate(item)
        if batch.canonical_listing_id != canonical_listing_id or batch.source_record_id is None:
            raise ValueError("source resolver requires external facts for exactly one canonical listing")
        if batch.source_record_id in sources:
            raise ValueError("multiple current batches for one source")
        sources.add(batch.source_record_id)
        if batch.source_status == "active":
            observations.extend(batch.facts)
    identities = [(f.key, f.scope_hash) for f in observations]
    groups = sorted(set(identities))
    features = []
    for key, scope_hash in groups:
        own = [f for f in observations if (f.key, f.scope_hash) == (key, scope_hash)]
        peers = [f for f in observations if _overlap(own[0], f)]
        signals = [f for f in peers if f.status not in {"unknown", "legacy_unverified"}]
        exact = [f for f in own if f.status in {"explicit_allow", "explicit_deny"}]
        signatures = {digest({"status": f.status, "value": f.typed_value.model_dump(mode="json")})
                      for f in exact if f.typed_value is not None}
        status: FactStatus
        value = None
        support = own
        if any(f.status == "conflict" for f in peers) or len(signatures) > 1:
            status, support = "conflict", peers
        elif any(f.scope_hash != scope_hash for f in signals):
            # Differently qualified rules may be exceptions or conditional
            # restrictions. Do not promote the broad rule into a guarantee.
            status, support = "conditional", peers
        elif any(f.status == "conditional" for f in signals):
            status, support = "conditional", peers
        elif exact:
            status, value, support = exact[0].status, exact[0].typed_value, exact
        elif any(f.status == "legacy_unverified" for f in own):
            status = "legacy_unverified"
        else:
            status = "unknown"
        features.append(SearchFeature(
            key=key, status=status, typed_value=value, qualifiers=own[0].qualifiers,
            supporting_fact_ids=sorted({f.fact_id for f in support}, key=str),
        ))
    projection = SearchProjection(
        schema_version="ai-facts.v1", taxonomy_version="ai-search.v1", canonical_listing_id=canonical_listing_id,
        feature_revision=feature_revision, resolver_version=resolver_version, input_hash=input_hash,
        computed_at=computed_at, features=features,
    )
    projection.validate_support(batches)
    return projection
