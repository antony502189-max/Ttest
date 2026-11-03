"""Manifest validation must survive python -O and never approve a release."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/ai-search-acceptance.py"
SPEC = importlib.util.spec_from_file_location("acceptance_inventory", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def catalog(tmp_path):
    root = tmp_path / "repo"
    (root / "docs/ai-search-developer").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "scripts/ai-search-acceptance.py").write_bytes(SCRIPT.read_bytes())
    (root / "suite.py").write_text("# synthetic fixture\n", encoding="utf-8")
    (root / "plan.md").write_text("# fixture\n", encoding="utf-8")
    data = {"schema": "ai-search-acceptance.v1", "base_sha": "a" * 40, "plan": "plan.md",
        "suites": [{"id": "fixture", "kind": "unit", "paths": ["suite.py"], "limit": "synthetic only"}],
        "criteria": [{"id": f"A{i}", "stage": "S2.2", "status": "partial", "suites": ["fixture"],
                      "gaps": ["not accepted"]} for i in range(1, 13)]}
    return root, data


def write(catalog):
    root, data = catalog
    (root / "docs/ai-search-developer/acceptance-matrix.v1.json").write_text(json.dumps(data), encoding="utf-8")
    return root


@pytest.mark.parametrize("optimized", [False, True])
@pytest.mark.parametrize("fault", ["schema", "criterion", "duplicate_suite", "outside_path", "kind"])
def test_bad_inventory_is_rejected_in_normal_and_optimized_python(catalog, optimized, fault):
    root, data = catalog
    if fault == "schema":
        data["schema"] = "typo"
    elif fault == "criterion":
        data["criteria"].pop()
    elif fault == "duplicate_suite":
        data["suites"].append(dict(data["suites"][0]))
    elif fault == "outside_path":
        (root.parent / "outside.py").write_text("# outside\n", encoding="utf-8")
        data["suites"][0]["paths"] = ["../outside.py"]
    else:
        data["suites"][0]["kind"] = "anything"
    write(catalog)
    code = """
import importlib.util, sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('inventory',sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    module.inventory(Path(sys.argv[2]))
except (ValueError, AssertionError):
    sys.exit(0)
sys.exit(1)
"""
    result = subprocess.run([sys.executable, *(["-O"] if optimized else []), "-c", code, str(SCRIPT), str(root)],
                            capture_output=True, check=False, timeout=10)
    assert result.returncode == 0, result.stderr.decode()


@pytest.mark.parametrize("status", ["not_started", "partial", "blocked"])
def test_non_release_statuses_can_progress(catalog, status):
    _, data = catalog
    data["criteria"][0]["status"] = status
    data["criteria"][0]["blocker"] = "fixture blocker"
    parsed, _ = MODULE.inventory(write(catalog))
    assert parsed["criteria"][0]["status"] == status


def test_verified_label_without_evidence_and_gate_review_is_rejected(catalog):
    catalog[1]["criteria"][0].update(status="verified", gaps=[])
    with pytest.raises(ValueError):
        MODULE.inventory(write(catalog))


def verified(catalog):
    root, data = catalog
    proof = root / "proof.txt"
    proof.write_text("fixture evidence only; no real release\n", encoding="utf-8")
    gate = root / "gate.json"
    gate.write_text(json.dumps({"schema": "ai-search-gate-review.v1", "criterion": "A1", "source_sha": "b" * 40,
        "outcome": "passed", "review_kind": "independent_release_gate", "reviewer": "fixture-reviewer"}), encoding="utf-8")
    data["criteria"][0].update(status="verified", gaps=[], verification={"source_sha": "b" * 40,
        "evidence": [{"path": "proof.txt", "sha256": hashlib.sha256(proof.read_bytes()).hexdigest()}],
        "release_gates": [{"path": "gate.json", "sha256": hashlib.sha256(gate.read_bytes()).hexdigest()}]})
    return write(catalog)


def test_verified_with_bound_evidence_is_representable_but_never_release_approval(catalog, monkeypatch):
    root = verified(catalog)
    data, _ = MODULE.inventory(root)
    assert data["criteria"][0]["status"] == "verified"
    monkeypatch.setattr(MODULE, "__file__", str(root / "scripts/ai-search-acceptance.py"))
    monkeypatch.setattr(MODULE.subprocess, "check_output", lambda *args, **kwargs: "b" * 40)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    assert MODULE.main() == 0
    report = json.loads((root / "output/ai-search-s1/matrix.json").read_text(encoding="utf-8"))
    assert report["product_acceptance"] is False and all(r["status"] == "not_run" for r in report["results"])


@pytest.mark.parametrize("fault", ["tampered_evidence", "wrong_source", "failed_gate", "missing_gate", "open_gaps"])
def test_verification_cannot_bypass_evidence_and_gate_binding(catalog, fault):
    root = verified(catalog)
    row = catalog[1]["criteria"][0]
    if fault == "tampered_evidence":
        (root / "proof.txt").write_text("changed", encoding="utf-8")
    elif fault == "missing_gate":
        row["verification"]["release_gates"] = []
    elif fault == "open_gaps":
        row["gaps"] = ["still open"]
    else:
        gate = json.loads((root / "gate.json").read_text(encoding="utf-8"))
        gate["source_sha" if fault == "wrong_source" else "outcome"] = "c" * 40 if fault == "wrong_source" else "failed"
        (root / "gate.json").write_text(json.dumps(gate), encoding="utf-8")
        row["verification"]["release_gates"][0]["sha256"] = hashlib.sha256((root / "gate.json").read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        MODULE.inventory(write(catalog))
