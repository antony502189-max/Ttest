#!/usr/bin/env python3
"""Fail CI when audited supply-chain pins are weakened."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
ACTION_USE = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def fail(message: str) -> None:
    raise SystemExit(message)


def check_workflows() -> None:
    workflows = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
    if not workflows:
        fail("no GitHub Actions workflows found")

    for path in workflows:
        content = path.read_text(encoding="utf-8")
        if "runs-on: ubuntu-latest" in content:
            fail(f"{path.relative_to(ROOT)} uses a floating runner image")
        for action in ACTION_USE.findall(content):
            # Local actions are part of the checked-out repository. All remote
            # actions must be immutable commit references, never mutable tags.
            if action.startswith("./"):
                continue
            if not FULL_SHA.fullmatch(action):
                fail(f"{path.relative_to(ROOT)} uses an unpinned action: {action}")
        if "actions/checkout@" in content and "persist-credentials: false" not in content:
            fail(f"{path.relative_to(ROOT)} checkout persists the workflow token")


def check_backend_constraints() -> None:
    constraints = ROOT / "backend" / "constraints.txt"
    dockerfile = ROOT / "backend" / "Dockerfile"
    production_workflow = WORKFLOW_DIR / "production-audit.yml"

    if not constraints.is_file() or not constraints.read_text(encoding="utf-8").strip():
        fail("backend/constraints.txt is missing or empty")
    lines = [line.strip() for line in constraints.read_text(encoding="utf-8").splitlines()]
    packages = [line for line in lines if line and not line.startswith("#")]
    if any("==" not in line or line.count("==") != 1 for line in packages):
        fail("every backend constraint must use one exact == version")
    names = [line.split("==", 1)[0].casefold() for line in packages]
    if len(names) != len(set(names)):
        fail("backend constraints contain duplicate package names")

    if "pip install --constraint constraints.txt ." not in dockerfile.read_text(encoding="utf-8"):
        fail("backend Dockerfile does not install through constraints.txt")
    workflow_text = production_workflow.read_text(encoding="utf-8")
    if "--constraint backend/constraints.txt" not in workflow_text or "python -m pip check" not in workflow_text:
        fail("Production audit does not enforce the backend dependency graph")


def main() -> None:
    check_workflows()
    check_backend_constraints()
    print("Supply-chain pins are valid")


if __name__ == "__main__":
    main()
