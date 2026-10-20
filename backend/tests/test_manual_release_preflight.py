"""Execute the real release gate against paginated GitHub API fixtures."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(not shutil.which("jq") or not shutil.which("bash"), reason="release gate requires Bash and jq")
@pytest.mark.parametrize("scenario,allowed", [("complete", True), ("missing_payment", False),
                                               ("failed_payment", False), ("incomplete_files", False)])
def test_paginated_manual_release_gate(tmp_path, scenario, allowed):
    workflow = yaml.safe_load((ROOT / ".github/workflows/manual-production-deploy.yml").read_text())
    script = next(step["run"] for step in workflow["jobs"]["verify-release"]["steps"]
                  if step["name"] == "Verify CI evidence for the merged pull request")
    sha, head = "a" * 40, "b" * 40
    files = [{"filename": f"docs/note-{i}.md"} for i in range(100)]
    file_pages = [files, [{"filename": "backend/app/services/province_top.py"}]]
    checks = [{"name": name, "status": "completed", "conclusion": "success", "completed_at": "2026-10-20T10:00:00Z"}
              for name in ["snapshot", "security-static", "safeguards", "full-audit", "backend-production", "frontend-static", "validate"]]
    payments = [{"name": name, "status": "completed", "conclusion": "success", "completed_at": "2026-10-20T10:00:00Z"}
                for name in ["backend-payments", "frontend-payments"]]
    if scenario == "missing_payment":
        payments.pop()
    if scenario == "failed_payment":
        payments[-1]["conclusion"] = "failure"
    if scenario == "incomplete_files":
        file_pages.pop()
    data = {"pulls": [{"number": 360, "merge_commit_sha": sha, "merged_at": "2026-10-20T09:00:00Z",
                        "base": {"ref": "main"}, "head": {"sha": head}}],
            "files": file_pages, "checks": [{"check_runs": checks}, {"check_runs": payments}]}
    fixture = tmp_path / "responses.json"
    fixture.write_text(json.dumps(data))
    stub = tmp_path / "gh"
    stub.write_text(f"#!{sys.executable}\n" + """import json, os, sys
args = sys.argv[1:]
data = json.load(open(os.environ['RELEASE_FIXTURES']))
endpoint = next(arg for arg in args if arg.startswith('/repos/'))
if endpoint.endswith('/pulls'):
    print(json.dumps(data['pulls']))
elif '/files?' in endpoint or '/check-runs?' in endpoint:
    assert '--paginate' in args and '--slurp' in args
    print(json.dumps(data['files' if '/files?' in endpoint else 'checks']))
else:
    assert endpoint.endswith('/pulls/360')
    print(101)
""")
    stub.chmod(0o755)
    env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
           "GITHUB_REPOSITORY": "antony502189-max/Ttest", "GITHUB_SHA": sha,
           "RELEASE_FIXTURES": str(fixture)}
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, check=False)
    assert (result.returncode == 0) is allowed, result.stdout + result.stderr
