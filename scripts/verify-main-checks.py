"""Fail closed unless the latest push checks passed on the exact merged SHA."""
import json
import re
import sys

REQUIRED = {
    "full-audit.yml": "Full audit",
    "security-audit.yml": "Security dependency and static audit",
    "capacity-smoke.yml": "Capacity smoke safeguards",
    "ai-search-facts.yml": "AI Search combined facts quota sessions",
    "ai-search-frontend.yml": "AI Search private frontend",
}


def verify(pages, sha):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("exact main SHA required")
    if not isinstance(pages, list) or not pages or any(not isinstance(p, dict) for p in pages):
        raise ValueError("paginated workflow response required")
    runs = []
    for page in pages:
        value = page.get("workflow_runs")
        if not isinstance(value, list) or any(not isinstance(run, dict) for run in value):
            raise ValueError("invalid workflow runs")
        runs.extend(value)
    for filename, name in REQUIRED.items():
        selected = [run for run in runs if run.get("head_sha") == sha and run.get("event") == "push"
                    and run.get("head_branch") == "main" and run.get("path") == f".github/workflows/{filename}"
                    and run.get("name") == name]
        if not selected:
            raise ValueError(f"missing exact-main push check: {name}")
        latest = max(selected, key=lambda run: (int(run["run_number"]), int(run["run_attempt"]), int(run["id"])))
        if latest.get("status") != "completed" or latest.get("conclusion") != "success":
            raise ValueError(f"latest exact-main check did not pass: {name}")
        print(f"{name}: completed/success on {sha}")


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError("usage: verify-main-checks.py <exact-main-sha>")
        verify(json.load(sys.stdin), sys.argv[1])
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        print(f"Unsafe to deploy: {error}", file=sys.stderr)
        return 65
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
