"""Offline code capabilities; never measures real source coverage or freshness."""
import ast
import json
from pathlib import Path
from typing import get_args

from app.schemas.ai_listing_facts import FactKey

# Reviewed bridge outputs, not legacy normalized fields or model capabilities.
TEXT = {"pets", "children", "couples", "smoking", "capacity_total"}
STRUCTURED = TEXT | {"furnished", "bills_included", "balcony", "terrace", "amenity"}


def matrix(root: Path) -> dict:
    tree = ast.parse((root / "app/external_sources.py").read_text(encoding="utf-8"))
    sources = sorted(node.name for node in tree.body if isinstance(node, ast.ClassDef)
                     and any(isinstance(b, ast.Name) and b.id == "ExternalListingSource" for b in node.bases))
    rows = []
    for adapter in ["bridge_text", "bridge_structured", *sources]:
        supported = TEXT if adapter == "bridge_text" else STRUCTURED if adapter == "bridge_structured" else None
        for key in sorted(get_args(FactKey)):
            rows.append({"adapter": adapter, "field": key,
                         "capability": "unknown" if supported is None else "supported" if key in supported else "unsupported",
                         "real_coverage": "unknown", "real_freshness": "unknown",
                         "evidence": "app/external_sources.py:" + adapter if supported is None else
                         "app/services/ai_fact_bridge.py:bridge_packet",
                         "condition": "reviewed mapping and exact evidence required; smoking/capacity require scope"
                         if supported is not None and key in supported else "no attested source-to-AI-field mapping"})
    return {"schema": "offline-source-field.v1", "real_records_measured": 0, "rows": rows}


if __name__ == "__main__":
    print(json.dumps(matrix(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
