"""Small synthetic toolchain regressions; Docker and all benchmark work are faked."""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).parents[2]
PS = shutil.which("pwsh") or shutil.which("powershell")


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.mark.parametrize("args", [
    ["measure", "--samples", "0"], ["measure", "--samples", "-1"],
    ["measure", "--samples", "201"], ["seed", "--total", "1000001"],
    ["seed", "--total", "0"], ["measure", "--total", "-1"],
    ["measure", "--candidate", "-1"], ["measure", "--total", "10", "--candidate", "11"],
    ["seed", "--baseline-only"], ["initialize", "--candidate", "0"],
    ["measure", "--candidate", "1"], ["initialize", "--sources", "3"],
])
async def test_numeric_cli_rejects_before_side_effects(args, monkeypatch):
    bench = module("benchmark-ai-map")
    infra = Mock(side_effect=AssertionError("infrastructure must not run"))
    monkeypatch.setattr(bench, "engine", infra)
    monkeypatch.setattr(bench, "validate_lab_environment", infra)
    monkeypatch.setattr("sys.argv", ["benchmark-ai-map.py", *args])
    with pytest.raises(SystemExit) as error:
        await bench.main()
    assert error.value.code == 2
    infra.assert_not_called()


@pytest.mark.parametrize("samples", [1, 50, 200])
def test_valid_cli(samples):
    args = module("benchmark-ai-map").parse_args(["measure", "--samples", str(samples)])
    assert args.samples == samples


def dataset(size=100000, sources=2):
    return {"listings": size, "source_records_per_listing": sources, "observations_per_listing": 20,
            "counts_including_template": {"external_listing_sources": (size + 1) * sources,
                                          "ai_listing_facts": (size + 1) * 20},
            "size_bytes": 1024, "settings": [], "version": "synthetic", "postgis": "synthetic"}


def write(root, name, value):
    (root / name).write_text(json.dumps(value), encoding="utf-8")


def complete(root, size=100000, sources=2):
    write(root, f"dataset-{size}.json", dataset(size, sources))
    cases = []
    for count in {300, min(10000, size), size}:
        for concurrency in (50, 100, 200):
            for zoom in (8, 13):
                cases.append({"total": size, "candidates": count, "concurrency": concurrency, "zoom": zoom,
                    "samples": 1, "requested_samples": 1, "failures": 0, "pass": True, "seconds": 1,
                    "p95_ms": 1, "p99_ms": 1, "results": [{"ms": 1, "ok": True, "pool_ms": 0}]})
    write(root, f"load-{size}.json", cases)
    write(root, f"cancellation-{size}.json", {"tasks": 20, "elapsed_ms": 1, "remaining_active": 0,
                                            "pool_reusable": True})


def report(root, monkeypatch):
    monkeypatch.setattr("sys.argv", ["summarize-ai-map-capacity.py", str(root)])
    module("summarize-ai-map-capacity").main()
    return (root / "REPORT_RU.md").read_text(encoding="utf-8"), json.loads((root / "summary.json").read_text())


@pytest.mark.parametrize("sources,expected", [(2, "200,000"), (10, "1,000,000")])
def test_report_uses_actual_source_profile(tmp_path, monkeypatch, sources, expected):
    complete(tmp_path, sources=sources)
    text, _ = report(tmp_path, monkeypatch)
    assert f"| 100,000 | {expected} | 2,000,000 |" in text
    assert f"{sources} записей источника" in text
    assert f"({sources} источников / 20 наблюдений)" in text


@pytest.mark.parametrize("damage", ["unsupported", "less_than_template", "inconsistent"])
def test_invalid_dataset_rejected(tmp_path, damage):
    value = dataset()
    if damage == "unsupported":
        value["source_records_per_listing"] = 3
    else:
        value["counts_including_template"]["external_listing_sources"] = 1 if damage == "less_than_template" else 200003
    write(tmp_path, "dataset-100000.json", value)
    with pytest.raises(ValueError, match="dataset"):
        module("summarize-ai-map-capacity").summarize(tmp_path)


@pytest.mark.parametrize("sizes", [[], [100000], [100000, 500000]])
def test_stop_status_is_derived_from_files(tmp_path, monkeypatch, sizes):
    for size in sizes:
        complete(tmp_path, size)
    write(tmp_path, "experiment-stop.json", {"reason": "synthetic stop", "completed_scales": sizes})
    text, result = report(tmp_path, monkeypatch)
    assert result["completed_scales"] == sizes
    assert ("INCOMPLETE" in text) == (len(sizes) < 3)
    assert "завершены 100 и 500 тысяч" not in text


@pytest.mark.parametrize("damage", ["no_load", "partial_load", "no_cancel", "bad_cancel", "empty_samples"])
def test_scale_is_not_completed_from_seed_or_cancel_marker_alone(tmp_path, damage):
    complete(tmp_path)
    path = tmp_path / "load-100000.json"
    if damage == "no_load":
        path.unlink()
    elif damage == "partial_load":
        write(tmp_path, path.name, json.loads(path.read_text())[:1])
    elif damage == "empty_samples":
        cases = json.loads(path.read_text())
        cases[0]["results"] = []
        write(tmp_path, path.name, cases)
    elif damage == "no_cancel":
        (tmp_path / "cancellation-100000.json").unlink()
    else:
        write(tmp_path, "cancellation-100000.json", {"remaining_active": 1, "pool_reusable": False})
    assert not module("summarize-ai-map-capacity").summarize(tmp_path)["scales"][0]["completed"]


def test_stop_marker_cannot_invent_completed_scales(tmp_path, monkeypatch):
    write(tmp_path, "experiment-stop.json", {"completed_scales": [100000, 500000]})
    text, result = report(tmp_path, monkeypatch)
    assert result["status"] == "INCONSISTENT" and result["warnings"]
    assert "INCONSISTENT" in text and not result["completed_scales"]


@pytest.mark.parametrize("kind", ["missing", "error", "malformed", "legacy", "complete", "gap", "trailing_gap"])
def test_summary_resource_quality(tmp_path, kind):
    records = []
    if kind in {"complete", "gap", "trailing_gap"}:
        records.append({"kind": "monitor-start", "at": "2026-10-29T00:00:00+00:00", "interval_seconds": 5})
    if kind != "missing":
        records.append({"at": "2026-10-29T00:00:00+00:00", "db": {"CPUPerc": "2%", "MemPerc": "3%"}})
    if kind == "error":
        records.append({"kind": "monitor-error", "at": "2026-10-29T00:00:01+00:00", "category": "docker-stats-exit"})
    if kind in {"complete", "gap", "trailing_gap"}:
        if kind == "gap":
            records.append({"at": "2026-10-29T00:01:00+00:00", "db": {"CPUPerc": "2%", "MemPerc": "3%"}})
        records.append({"kind": "monitor-stop", "status": "stopped", "at": records[-1]["at"]})
        if kind == "trailing_gap":
            records[-1]["at"] = "2026-10-29T00:01:00+00:00"
    if records:
        (tmp_path / "resources.jsonl").write_text("\n".join(json.dumps(r) for r in records) +
            ("\nnot json" if kind == "malformed" else ""))
    quality = module("summarize-ai-map-capacity").summarize(tmp_path)["monitoring"]
    assert quality["status"] == {"missing": "missing", "complete": "complete", "legacy": "unknown",
                                 "error": "degraded", "malformed": "degraded", "gap": "degraded",
                                 "trailing_gap": "degraded"}[kind]


@pytest.fixture
def ps_project(tmp_path):
    if not PS:
        pytest.skip("PowerShell runtime unavailable; run the fake-Docker suite on Windows/pwsh")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("run-ai-map-benchmark.ps1", "monitor-ai-map.ps1"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    (tmp_path / ".gitignore").write_text("output/\n")
    (tmp_path / "tracked.py").write_text("# immutable source\n")
    for args in (["init", "-q"], ["add", "."], ["-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                                                 "commit", "-qm", "fixture"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)
    return tmp_path


def powershell(root, command, mode="success"):
    wrapper = ROOT / "backend/tests/fixtures/ai-map-fake-docker.ps1"
    return subprocess.run([PS, "-NoProfile", "-File", str(wrapper), "-Root", str(root), "-Mode", mode,
                           "-CommandText", command], capture_output=True, text=True, timeout=30, check=False)


@pytest.mark.parametrize("dirty", ["clean", "concurrent_edit", "unstaged", "staged", "untracked", "git_error"])
def test_launcher_provenance_before_docker(ps_project, dirty):
    if dirty in {"unstaged", "staged"}:
        (ps_project / "tracked.py").write_text("# changed\n")
        if dirty == "staged":
            subprocess.run(["git", "-C", str(ps_project), "add", "."], check=True)
    elif dirty == "untracked":
        (ps_project / "untracked.py").write_text("# extra\n")
    result = powershell(ps_project, "& $root/scripts/run-ai-map-benchmark.ps1 -Phase initialize",
                        mode=dirty if dirty in {"git_error", "concurrent_edit"} else "success")
    calls = ps_project / "output/docker-calls.txt"
    if dirty in {"clean", "concurrent_edit"}:
        assert result.returncode == 0, result.stderr
        assert "run" in calls.read_text()
        provenance = json.loads((ps_project / "output/mounted-source.json").read_text(encoding="utf-8-sig"))
        assert provenance["snapshot"] != str(ps_project) and provenance["content"].strip() == "# immutable source"
        assert provenance["archive_hash"] and provenance["checkout_clean"] == "true"
    else:
        assert result.returncode != 0
        assert not calls.exists(), result.stdout + result.stderr


@pytest.mark.parametrize("flags", ["-Samples 0", "-Samples -1", "-Total 0", "-Candidate -1",
                                    "-Samples 201", "-Total 1000001", "-Total 10 -Candidate 11", "-Phase seed -BaselineOnly"])
def test_powershell_invalid_cli_before_docker(ps_project, flags):
    phase = "" if "-Phase" in flags else "-Phase measure"
    result = powershell(ps_project, f"& $root/scripts/run-ai-map-benchmark.ps1 {phase} {flags}")
    assert result.returncode != 0
    assert not (ps_project / "output/docker-calls.txt").exists()


@pytest.mark.parametrize("mode", ["error", "malformed", "empty", "missing_fields", "wrong_profile",
                                    "wrong_output_profile", "success", "recover", "stop"])
def test_monitor_fake_docker(ps_project, mode):
    output = ps_project / "output/monitor"
    output.mkdir(parents=True)
    if mode == "stop":
        (output / "monitor.stop").touch()
    if mode == "wrong_output_profile":
        write(output, "template.json", {"sources": 10})
    result = powershell(ps_project,
        "& $root/scripts/monitor-ai-map.ps1 -OutputDirectory $root/output/monitor -MaxConsecutiveFailures 2", mode)
    records = [json.loads(line) for line in (output / "resources.jsonl").read_text(encoding="utf-8-sig").splitlines()]
    if mode in {"success", "recover", "stop"}:
        assert result.returncode == 0, result.stderr
        if mode != "stop":
            assert any("db" in row for row in records)
        if mode == "recover":
            assert any(row["kind"] == "monitor-error" for row in records)
    else:
        assert result.returncode != 0
        errors = [row for row in records if row["kind"] == "monitor-error"]
        assert len(errors) == (1 if mode in {"wrong_profile", "wrong_output_profile"} else 2)
