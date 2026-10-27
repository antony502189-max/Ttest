"""Explicit offline adapter subset and evidence sufficiency, without extraction."""
import re

SUPPORTED_PROVIDER_FIELDS = frozenset({
    "pets_allowed", "children_allowed", "smoking_allowed", "room_capacity",
    "couples_allowed", "furnished", "bills_included", "amenities",
})


def has_evidence_text(value: str) -> bool:
    return bool(re.search(r"\w", re.sub(r"\[(?:contact|advertiser|link|secret)\]", "", value)))
