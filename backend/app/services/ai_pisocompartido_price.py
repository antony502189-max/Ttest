"""Conservative price-only mapping of an existing PisoCompartido import.

No contacts/text/boolean defaults become facts. No HTTP or source refresh.
"""
import json
import re
from decimal import Decimal

from ..repositories.ai_fact_snapshots import CapturedParserSnapshot
from ..schemas.ai_fact_bridge import BridgeRejected
from ..schemas.ai_fact_pipeline import SourceInput
from ..schemas.ai_listing_facts import EvidenceSpan, digest
from .ai_fact_bridge import PreparedFactInput, _observation

VERSION = "pisocompartido-price.v1"


def prepare_price(snapshot: CapturedParserSnapshot) -> PreparedFactInput:
    ref = snapshot.reference
    if ref.source_identifier != f"PisoCompartido:{ref.source_record_id.hex}":
        raise BridgeRejected("SOURCE_IDENTITY_UNSUPPORTED")
    value = json.loads(snapshot.normalized_json)
    text = snapshot.source_price_text
    # Cadence comes from the existing explicit import.price_period field.
    # The amount alone cannot infer a cadence; source text must agree on EUR.
    match = re.fullmatch(r"\s*(\d{1,4})(?:[,.](\d{1,2}))?\s*€\s*(?:/\s*mes|al mes|mensual)?\s*", text or "", re.IGNORECASE)
    if not match:
        raise BridgeRejected("EXPLICIT_MONTHLY_PRICE_REQUIRED")
    amount = Decimal(match[1] + "." + (match[2] or "0"))
    if (not 0 < amount <= 1000 or value.get("source_name") != "PisoCompartido"
            or value.get("source_price_text") != text or value.get("rental_mode") != "long"
            or value.get("price_currency") != "EUR" or value.get("price_period") != "month"
            or value.get("price_is_from") is not False or type(value.get("price_amount")) is not int
            or amount != value["price_amount"]):
        raise BridgeRejected("SOURCE_PRICE_DISAGREEMENT")
    fields = {"metadata.extractor": VERSION}
    facts = []
    for key, path, raw, typed in (
        ("price", "import.price", {"text": text, "amount": value["price_amount"], "currency": "EUR", "period": "month"},
         {"kind": "money", "amount": str(amount), "currency": "EUR", "period": "monthly"}),
        ("rental_mode", "import.rental_mode", "long", {"kind": "category", "value": "long"}),
    ):
        quote = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        fields["structured." + path] = quote
        evidence = EvidenceSpan(field="structured", provider_field=path, quote=quote, start=0, end=len(quote))
        facts.append(_observation(ref, key=key, status="explicit_allow", value=typed,
                                  qualifiers={}, evidence=[evidence], origin="source_structured"))
    source = SourceInput(source_record_id=ref.source_record_id, canonical_listing_id=ref.canonical_listing_id,
        content_hash=digest(fields), snapshot_hash=ref.snapshot_hash, schema_version="ai-facts.v1",
        taxonomy_version="ai-search.v1", extractor_version=VERSION)
    return PreparedFactInput(source, tuple(sorted(fields.items())), tuple(f.model_dump_json() for f in facts))
