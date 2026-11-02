"""Read-only acceptance of raw capacity evidence; never activates AI."""
import argparse
import importlib.util
import re
import sys
from pathlib import Path


def accept(root: Path, expected_sha: str):
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ValueError("exact measured source SHA required")
    path = Path(__file__).with_name("summarize-ai-map-capacity.py")
    spec = importlib.util.spec_from_file_location("capacity_summary", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Recompute from raw attempts/plans/manifests/resources, not summary.json.
    result = module.summarize(root)
    provenance = result.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("code_revision") != expected_sha:
        raise ValueError("capacity evidence does not match the measured source SHA")
    if result.get("protocol_complete") is not True or result.get("slo_passed") is not True:
        raise ValueError("current protocol and all capacity SLOs must pass")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        accept(args.root, args.expected_sha)
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"AI capacity acceptance BLOCKED: {error}", file=sys.stderr)
        return 1
    print(f"AI map capacity evidence accepted for {args.expected_sha}; public activation remains separately gated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
