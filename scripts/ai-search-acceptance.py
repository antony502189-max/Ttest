"""S1 acceptance inventory and bounded offline checks; never a release gate."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def inventory(root):
    manifest = root / "docs/ai-search-developer/acceptance-matrix.v1.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["schema"] == "ai-search-acceptance.v1"
    assert [row["id"] for row in data["criteria"]] == [f"A{i}" for i in range(1, 13)]
    suites = {suite["id"]: suite for suite in data["suites"]}
    assert len(suites) == len(data["suites"])
    for row in data["criteria"]:
        assert row["stage"] and row["gaps"] and row["suites"]
        assert row["status"] == "partial"
        assert set(row["suites"]) <= suites.keys()
    hashes = {}
    for suite in suites.values():
        assert suite["kind"] in {"unit", "mock-browser", "disposable-service", "gated"}
        assert suite["paths"] and suite["limit"]
        for name in suite["paths"]:
            path = (root / name).resolve()
            assert path.is_relative_to(root) and path.is_file(), name
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    hashes[str(manifest.relative_to(root)).replace("\\", "/")] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    hashes["scripts/ai-search-acceptance.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
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
