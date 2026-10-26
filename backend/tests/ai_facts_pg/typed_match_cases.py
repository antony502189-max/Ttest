"""Synthetic contract cases, not real catalog or model quality evidence."""


import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.schemas.ai_listing_facts import FactVocabulary, SearchProjection
from app.schemas.ai_search_intent import SearchIntent
from app.services.ai_hard_matching import compile_hard_match

CASES = json.loads((Path(__file__).parents[1] / "fixtures/ai_hard_match/synthetic.json").read_text())


VOCABULARY = FactVocabulary(amenity_codes=frozenset({"synthetic_wifi"}), catalog_other_codes=frozenset({"synthetic_house"}),
    tenant_group_codes=frozenset({"friends"}), municipality_zones=frozenset({("38001", "synthetic_zone")}))


def intent(criteria):
    return SearchIntent.model_validate_json(json.dumps({"schema_version": "ai-search.v1", "taxonomy_version": "rental.v1",
        "session_id": str(uuid4()), "version": 0, "criteria": criteria}))


def plan(case, strength="hard"):
    return compile_hard_match(intent({case["name"]: {"strength": strength, "value": case["value"]}}), VOCABULARY)


def projection(features):
    return SearchProjection.model_validate_json(json.dumps({"schema_version": "ai-facts.v1", "taxonomy_version": "ai-search.v1",
        "canonical_listing_id": str(uuid4()), "feature_revision": 1, "resolver_version": "test.v1", "input_hash": "a" * 64,
        "computed_at": datetime.now(UTC).isoformat(), "features": features}))


def edge_cases():
    cases = []

    def changed(name, field, value, expected=False, *, qualifier=False):
        case = copy.deepcopy(next(c for c in CASES if c["name"] == name))
        case["features"][0]["qualifiers" if qualifier else "typed_value"][field] = value
        if name == "geography" and field == "municipality_code" and value is None:
            case["features"][0]["typed_value"]["zone_id"] = None
        cases.append((case, case["features"], expected))

    changed("budget", "amount", "700.00", True)
    changed("budget", "amount", "700.01")
    changed("budget", "period", "weekly")
    changed("deposit", "value", 2, True)
    changed("deposit", "value", 3)
    changed("deposit", "value", 0, True)
    changed("geography", "municipality_code", "38002")
    changed("geography", "municipality_code", None)
    changed("accommodation", "value", "studio")
    changed("party", "value", 2)
    changed("pets", "max_count", 1, qualifier=True)
    changed("pets", "species", "cat", qualifier=True)
    changed("pets", "size", "large", qualifier=True)
    changed("smoking", "smoking_scope", "indoors", qualifier=True)
    changed("smoking", "smoking_scope", "terrace", qualifier=True)
    changed("amenities", "amenity_code", "synthetic_wifi", True, qualifier=True)
    changed("dates", "start", "2026-11-02")
    changed("dates", "end", "2026-11-03")
    changed("stay", "value", 4)
    changed("stay", "unit", "months")
    for name in ("pets", "smoking"):
        changed(name, "allowed", False)
        case = copy.deepcopy(next(c for c in CASES if c["name"] == name))
        case["features"][0].update(status="explicit_deny")
        case["features"][0]["typed_value"]["allowed"] = False
        cases.append((case, case["features"], False))
        case = copy.deepcopy(next(c for c in CASES if c["name"] == name))
        case["features"][0].update(status="conditional")
        case["features"][0]["qualifiers"]["approval_required"] = True
        cases.append((case, case["features"], False))
    # A requested unspecified size cannot be confirmed by small-only permission.
    case = copy.deepcopy(next(c for c in CASES if c["name"] == "pets"))
    case["value"][0]["size"] = "unspecified"
    cases.append((case, copy.deepcopy(case["features"]), False))
    broad = copy.deepcopy(case["features"])
    broad[0]["qualifiers"].pop("size")
    cases.append((case, broad, True))
    # A narrow balcony permission cannot confirm outdoors generally.
    case = copy.deepcopy(next(c for c in CASES if c["name"] == "smoking"))
    case["value"]["scope"] = "outdoors"
    narrow = copy.deepcopy(case["features"])
    narrow[0]["qualifiers"]["smoking_scope"] = "balcony"
    cases.append((case, narrow, False))
    # Explicit money deposit variant, with no monthly rent conversion.
    case = copy.deepcopy(next(c for c in CASES if c["name"] == "deposit"))
    case["value"] = {"kind": "money", "amount": "100.50", "currency": "EUR", "period": "one_off"}
    features = copy.deepcopy(case["features"])
    features[0]["typed_value"] = {"kind": "money", "amount": "100.50", "currency": "EUR", "period": "one_off"}
    cases.append((case, features, True))
    # Validate bounded catalog_other rather than narrowing supported types.
    case = copy.deepcopy(next(c for c in CASES if c["name"] == "accommodation"))
    case["value"] = {"kind": "catalog_other", "catalog_code": "synthetic_house"}
    features = copy.deepcopy(case["features"])
    features[0]["typed_value"] = {"kind": "category", "value": "catalog_other", "catalog_code": "synthetic_house"}
    cases.append((case, features, True))
    return cases


