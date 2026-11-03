"""S1 acceptance inventory and bounded offline checks; never a release gate."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

STATUSES = frozenset({"not_started", "partial", "blocked", "verified"})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strings(value, *, empty=False):
    return isinstance(value, list) and (empty or bool(value)) and all(
        isinstance(item, str) and bool(item.strip()) for item in value)


def checked_file(root, name):
    require(isinstance(name, str) and bool(name), "inventory path must be a nonempty string")
    path = (root / name).resolve()
    require(not Path(name).is_absolute() and path.is_relative_to(root) and path.is_file(),
            "inventory path must be an existing file inside the checkout")
    return path


def checked_evidence(root, row):
    require(isinstance(row, dict), "evidence record required")
    digest = row.get("sha256")
    require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "evidence SHA-256 required")
    path = checked_file(root, row.get("path"))
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "evidence digest mismatch")
    return path


def verify_criterion(root, row):
    verification = row.get("verification")
    require(isinstance(verification, dict), "verified criterion requires evidence and independent gate review")
    source = verification.get("source_sha")
    require(isinstance(source, str) and re.fullmatch(r"[0-9a-f]{40}", source), "verification source SHA required")
    for kind in ("evidence", "release_gates"):
        records = verification.get(kind)
        require(isinstance(records, list) and 1 <= len(records) <= 100, "bounded verification records required")
        for record in records:
            path = checked_evidence(root, record)
            if kind == "release_gates":
                gate = json.loads(path.read_text(encoding="utf-8"))
                require(isinstance(gate, dict) and gate.get("schema") == "ai-search-gate-review.v1"
                        and gate.get("criterion") == row["id"] and gate.get("source_sha") == source
                        and gate.get("outcome") == "passed" and gate.get("review_kind") == "independent_release_gate"
                        and isinstance(gate.get("reviewer"), str) and bool(gate["reviewer"].strip()),
                        "independent gate evidence must match criterion and source")


def inventory(root):
    root = Path(root).resolve()
    manifest_name = "docs/ai-search-developer/acceptance-matrix.v1.json"
    manifest = checked_file(root, manifest_name)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    require(isinstance(data, dict) and data.get("schema") == "ai-search-acceptance.v1", "invalid inventory schema")
    require(isinstance(data.get("base_sha"), str) and re.fullmatch(r"[0-9a-f]{40}", data["base_sha"]),
            "inventory base SHA required")
    checked_file(root, data.get("plan"))
    criteria, suite_rows = data.get("criteria"), data.get("suites")
    require(isinstance(criteria, list) and all(isinstance(row, dict) for row in criteria), "criterion records required")
    require([row.get("id") for row in criteria] == [f"A{i}" for i in range(1, 13)], "exact ordered A1-A12 required")
    require(isinstance(suite_rows, list) and bool(suite_rows) and all(isinstance(row, dict) for row in suite_rows),
            "suite records required")
    require(all(isinstance(row.get("id"), str) and row["id"] for row in suite_rows), "suite IDs required")
    suites = {suite["id"]: suite for suite in suite_rows}
    require(len(suites) == len(suite_rows), "duplicate suite IDs")
    for row in criteria:
        require(isinstance(row.get("stage"), str) and bool(row["stage"]), "criterion stage required")
        require(strings(row.get("suites")) and set(row["suites"]) <= suites.keys(), "unknown/empty criterion suites")
        require(isinstance(row.get("status"), str) and row["status"] in STATUSES, "invalid criterion status")
        require(strings(row.get("gaps"), empty=row["status"] == "verified"), "criterion gaps must be explicit")
        if row["status"] == "blocked":
            require(isinstance(row.get("blocker"), str) and bool(row["blocker"].strip()), "blocked criterion needs a reason")
        if row["status"] == "verified":
            require(not row["gaps"], "verified criterion cannot retain open gaps")
            verify_criterion(root, row)
    hashes = {}
    for suite in suite_rows:
        require(isinstance(suite.get("kind"), str) and suite["kind"] in {
            "unit", "mock-browser", "disposable-service", "gated"}, "invalid suite kind")
        require(strings(suite.get("paths")) and isinstance(suite.get("limit"), str) and suite["limit"].strip(),
                "suite paths and limits required")
        if suite["kind"] == "mock-browser":
            checked_file(root, suite.get("config"))
        for name in suite["paths"]:
            path = checked_file(root, name)
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    hashes[manifest_name] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    hashes["scripts/ai-search-acceptance.py"] = hashlib.sha256(
        checked_file(root, "scripts/ai-search-acceptance.py").read_bytes()).hexdigest()
    return data, hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", choices=("unit", "mock-browser"))
    parser.add_argument("--criterion", action="append", choices=[f"A{i}" for i in range(1, 13)])
    parser.add_argument("--output", default="output/ai-search-s1/matrix.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    if not output.is_relative_to(root / "output"):
        parser.error("output must remain inside the repository output directory")
    data, hashes = inventory(root)
    selected = [row for row in data["criteria"] if not args.criterion or row["id"] in args.criterion]
    suite_ids = {key for row in selected for key in row["suites"]}
    report = {"schema": "ai-search-acceptance-run.v1", "observed_at": datetime.now(UTC).isoformat(),
              "source": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
              "worktree_status": subprocess.check_output(["git", "status", "--short"], cwd=root, text=True),
              "python": sys.version, "input_sha256": hashes, "mode": args.run or "inventory",
              "product_acceptance": False, "results": [], "criteria": selected}
    failed = False
    for suite in data["suites"]:
        if suite["id"] not in suite_ids:
            continue
        row = {"suite": suite["id"], "kind": suite["kind"], "limit": suite["limit"], "status": "not_run"}
        report["results"].append(row)
        if suite["kind"] != args.run:
            continue
        # Only reviewed synthetic test entrypoints. No arbitrary shell command,
        # live model runner, lab control, migrations or capacity launch path.
        if args.run == "unit":
            command = [sys.executable, "-m", "pytest", "-q", "-m", "not integration", *suite["paths"]]
        else:
            command = ["node", "node_modules/@playwright/test/cli.js", "test", "--config", suite["config"]]
        env = dict(os.environ, PYTHONPATH=str(root / "backend"), APP_ENV="test")
        started = time.monotonic()
        log = output
        log = log.parent / (log.stem + "-" + suite["id"] + ".log")
        log.parent.mkdir(parents=True, exist_ok=True)
        row["argv"] = command
        with log.open("w", encoding="utf-8") as stream:
            try:
                result = subprocess.run(command, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=600, check=False)
                row.update(status="passed" if result.returncode == 0 else "failed", exit_code=result.returncode)
            except (OSError, subprocess.TimeoutExpired) as error:
                # Avoid echoing dependency exception payloads or environment.
                row.update(status="failed", error=type(error).__name__)
        row.update(seconds=round(time.monotonic() - started, 3), log=str(log.relative_to(root)))
        failed |= row["status"] != "passed"
        print(row["suite"], row["status"], row["seconds"], flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"A1-A12 inventory valid; {len(hashes)} referenced inputs. Product acceptance remains OPEN.")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
