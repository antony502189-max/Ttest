import re
from pathlib import Path


def test_visual_regression_inputs_are_pinned_by_source_commit() -> None:
    root = Path(__file__).resolve().parents[2]
    baseline_ref = (root / ".github" / "visual-baseline-ref").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"[0-9a-f]{40}", baseline_ref)

    installer = (root / "scripts" / "install-visual-baselines.sh").read_text(encoding="utf-8")
    assert ".github/visual-baseline-ref" in installer
    assert "git fetch --no-tags --depth=1" in installer
    assert "git ls-tree -r --name-only" in installer
    assert "tests/visual-snapshots/chromium/*.png" in installer
    assert "visual-baselines" not in installer

    for workflow_name in ("full-audit.yml", "mobile-validation.yml"):
        workflow = (root / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8")
        assert "bash scripts/install-visual-baselines.sh" in workflow
        assert "ref: visual-baselines" not in workflow
        assert "path: .visual-baselines" not in workflow

    local_audit = (root / "scripts" / "final-audit-local.sh").read_text(encoding="utf-8")
    assert "bash scripts/install-visual-baselines.sh" in local_audit
