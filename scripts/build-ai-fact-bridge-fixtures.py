"""Explicit offline fixture regeneration from two pinned #373 Git objects.

No fetch/network. Executes that historical pure builder only in this standalone
test-data process. Does not install/import its code into the application or CI.
"""

import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path
from uuid import UUID

REVISION = "fcae378d9dbbc8447f18df150327180f6f2c8231"
EXPECTED_SHA256 = {
    "backend/app/services/listing_evidence.py": "dcbf3fa055e59da77cbbd5a88d0af19fc17ad722128eac719f00b987d71f3af6",
    "backend/app/services/ai_listing_input.py": "1fc88d388c2d20a74b7847ee53a651d8c4e00556816e8db47e19dcd102222508",
}
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "backend/tests/fixtures/ai_fact_bridge/parser-373-synthetic.json"


def main():
    package = types.ModuleType("offline_parser_fixture")
    package.__path__ = []
    sys.modules[package.__name__] = package
    blobs = {}
    for name in ("listing_evidence", "ai_listing_input"):
        path = f"backend/app/services/{name}.py"
        result = subprocess.run(["git", "show", f"{REVISION}:{path}"], cwd=ROOT, capture_output=True, check=True)
        blobs[path] = hashlib.sha256(result.stdout).hexdigest()
        if blobs[path] != EXPECTED_SHA256[path]:
            raise SystemExit("Pinned fixture builder source mismatch")
        module = types.ModuleType(f"{package.__name__}.{name}")
        module.__package__ = package.__name__
        sys.modules[module.__name__] = module
        # Explicit fixture-only execution of two literal, SHA-256-verified Git objects.
        exec(compile(result.stdout, f"{REVISION}:{path}", "exec"), module.__dict__)  # noqa: S102
    builder = sys.modules[f"{package.__name__}.ai_listing_input"]
    cases = []

    def add(name, description, *, title="Synthetic listing", provider_facts=()):
        packet = builder.build_listing_evidence_input(
            source_identifier="synthetic:fixture", canonical_listing_identifier=UUID("11111111-1111-4111-8111-111111111111"),
            title=title, description=description, property_category="room", rental_category="long",
            source_language="mixed", provider_facts=provider_facts,
        )
        cases.append({"name": name, "packet": packet.model_dump(mode="json")})

    def structured(name, value, path, quote):
        return builder.ProviderFact(field=name, value=value,
            evidence=builder.EvidenceSpan(source="structured", provider_field=path, quote=quote))

    add("pets_deny", "No pets.")
    add("pets_allow", "Se aceptan mascotas.")
    add("capacity_couple", "Habitación para dos personas. Se admiten parejas.")
    add("small_dog_conditional", "Solo perros pequeños y gatos.")
    add("pets_conflict", "Pets allowed. No pets.")
    add("smoking_scoped", "No fumar dentro del piso. Se permite fumar solo en la terraza.")
    add("smoking_unscoped", "No smoking.")
    add("repeated_negative", "No pets. No pets.")
    add("unicode_newline", "Квартира 🏠\n  No pets.\n")
    add("structured_false_and_amenities", "Datos de la vivienda.", provider_facts=(
        structured("furnished", False, "details.furnished", "Sin amueblar"),
        structured("bills_included", False, "details.bills", "Gastos aparte"),
        structured("amenities", ("wifi", "balcony"), "details.amenities", "Wifi y balcón"),
    ))
    add("structured_text_conflict", "No pets.", provider_facts=(
        structured("pets_allowed", True, "rules.pets", "Mascotas permitidas"),
    ))
    add("structured_capacity", "Datos de la habitación.", provider_facts=(
        structured("room_capacity", 3, "details.unit_capacity", "3 personas en la habitación"),
    ))
    add("structured_smoking", "Datos de la habitación.", provider_facts=(
        structured("smoking_allowed", False, "rules.smoking_indoors", "No fumar dentro"),
    ))
    add("students_only", "Solo estudiantes.")
    add("insufficient", "", title="")
    add("sanitized_fixture_contacts", "<script>DO_NOT_EXPORT</script><p>No pets.</p>"
        "<p>Contact: fixture@example.invalid +34 600 000 000</p>")
    add("marketing_capacity_unknown", "La casa tiene 6 plazas.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"synthetic": True, "upstream_revision": REVISION, "source_sha256": blobs,
                                  "cases": cases}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(cases)} synthetic packets from pinned local Git objects; no application code ported")


if __name__ == "__main__":
    main()
