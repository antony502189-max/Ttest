"""Small synthetic toolchain regressions; Docker and all benchmark work are faked."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

ROOT = Path(__file__).parents[2]
PS = shutil.which("pwsh") or shutil.which("powershell")


def test_evidence_intervals_survive_wall_clock_steps(monkeypatch):
    bench = module("benchmark-ai-map")
    anchor = datetime(2026, 10, 30, tzinfo=UTC)
    monkeypatch.setattr(bench, "_CLOCK_UTC", anchor)
    monkeypatch.setattr(bench, "_CLOCK_MONOTONIC", 100.0)
    monkeypatch.setattr(bench, "time", Mock(perf_counter=Mock(side_effect=[100.0, 101.0, 102.0])))
    wall_clock = Mock()
    wall_clock.now.side_effect = [anchor, anchor-timedelta(seconds=4), anchor+timedelta(minutes=10)]
    monkeypatch.setattr(bench, "datetime", wall_clock)
    observed = [datetime.fromisoformat(bench.now()) for _ in range(3)]
    assert observed == [anchor, anchor+timedelta(seconds=1), anchor+timedelta(seconds=2)]
    wall_clock.now.assert_not_called()


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
    ["seed", "--sources", "10"], ["measure", "--sources", "2"],
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
            "counts_including_template": {table:(size+1)*n for table,n in {
                "listings":1,"listing_room_details":1,"external_listing_sources":sources,"ai_fact_catalogs":1,
                "ai_listing_fact_batches":sources,"ai_fact_sources":sources,"ai_listing_facts":20,
                "ai_listing_search_features":1,"ai_query_proofs":1}.items()},"seed_generation":1,
            "size_bytes": 1024,"distinct_providers":min(10,size+sources), "settings": [], "version": "synthetic", "postgis": "synthetic"}


def write(root, name, value):
    (root / name).write_text(json.dumps(value), encoding="utf-8")


def complete(root, size=100000, sources=2):
    provenance = {"experiment_id":"a"*32, "seed_id":"a"*32, "code_revision":"b"*40,
        "runner_image_id":"sha256:"+"c"*64, "archive_sha256":"d"*64,
        "db_container_id":"e"*64, "db_image_id":"sha256:"+"f"*64, "sources":sources, "observations":20,"protocol_version":"r01-capacity.v2"}
    write(root, "experiment.json", provenance)
    init_id, seed_id, run_id = "1"*32, f"{size+2:032x}", f"{size+1:032x}"
    for phase, identifier in (("initialize", init_id), ("seed", seed_id), ("measure", run_id)):
        manifest_size = 100000 if phase == "initialize" else size
        write(root, f"runner-{phase}-{manifest_size}-{identifier}.json", {"provenance":provenance,
            "run_id":identifier, "status":"complete", "phase":phase,"total":size,
            "started_at":"2026-10-28T00:00:00+00:00", "ended_at":"2026-10-30T00:00:00+00:00"})
    write(root, "template.json", {"sources":sources, "observations":20,"provenance":provenance,"run_id":init_id})
    write(root, f"dataset-{size}.json", {**dataset(size, sources),"provenance":provenance,"run_id":seed_id})
    write(root, f"proof-verification-{size}.json", {"actual_production_digest_equal":True,"provenance":provenance,
        "run_id":seed_id,"seed_generation":1,
        "ordinals":sorted(n for n in {2,size//7,size//3,size//2+1,size*2//3,size-1,size} if 1 <= n <= size)})
    cases = []
    for count in {300, min(10000, size), size}:
        for concurrency in (50, 100, 200):
            for zoom in (8, 13):
                cases.append({"total": size, "candidates": count, "concurrency": concurrency, "zoom": zoom,
                    "samples": 200, "requested_samples": 200,"stopped_after_failed_wave":False, "mode":"load", "failures": 0, "pass": True, "seconds": 4,
                    "provenance":provenance,"run_id":run_id,"started_at":"2026-10-29T00:00:00+00:00",
                    "ended_at":"2026-10-29T00:00:04+00:00",
                    "p50_ms":1,"p95_ms": 1, "p99_ms": 1, "results": [{"ms": 1, "ok": True, "pool_ms": 0,"query_ms":1,"count":count,"items":min(count,300),
                        "started_at":f"2026-10-29T00:00:0{i//concurrency}+00:00",
                        "ended_at":f"2026-10-29T00:00:0{i//concurrency}.001+00:00"} for i in range(200)]})
    write(root, f"load-{size}.json", cases)
    write(root, f"cancellation-{size}.json", {"tasks": 20, "elapsed_ms": 1, "remaining_active": 0,
        "pool_reusable": True,"provenance":provenance,"run_id":run_id,
        "started_at":"2026-10-29T00:00:04+00:00","ended_at":"2026-10-29T00:00:04.001+00:00",
        "cancel_requested":20,"cancel_accepted":20,"cancelled":20,"active_before_cancel":20,
        "completed_before_cancel":0,"failed":0})
    write(root,f"dataset-stability-{size}-{run_id}.json",{"provenance":provenance,"run_id":run_id,"total":size,
        "stable":True,"write_frozen":True,"lock_mode":"SHARE","seed_generation_before":1,"seed_generation_after":1,
        "tables":["public."+table for table in [*dataset(size,sources)["counts_including_template"],"r01_entities","r01_meta"]],
        "started_at":"2026-10-28T23:59:59+00:00","ended_at":"2026-10-29T00:00:06+00:00"})
    baseline = []
    for count in {0,299,300,301,302,10000,size}:
        for zoom in (8,12,13,21):
            statements = [{"ordinal":0,"category":"transaction-control","sql":"SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY","parameters":[]}]
            for index in range(1,3 if zoom >= 13 and count > 300 else 2):
                sql = f"SELECT {index} /* synthetic test capture */"
                sha = hashlib.sha256(sql.encode()).hexdigest()
                filename = f"plan-{size}-{count}-z{zoom}-{index}.json"
                statements.append({"ordinal":index,"category":"map-query","sql":sql,"sql_sha256":sha,
                    "parameters":[],"plan_file":filename,"plan_status":"actual"})
                write(root,filename,{"total":size,"candidates":count,"zoom":zoom,"statement_index":index,
                    "provenance":provenance,"run_id":run_id,"sql_sha256":sha,"parameters":[],"status":"actual",
                    "plan":[{"Plan":{"Node Type":"Result","Actual Loops":1},"Execution Time":1}]})
            baseline.append({"total":size,"candidates":count,"zoom":zoom,"provenance":provenance,"run_id":run_id,
                "started_at":"2026-10-29T00:00:00+00:00","ended_at":"2026-10-29T00:00:00.001+00:00",
                "first_touch":{"ok":True,"ms":1,"pool_ms":0,"query_ms":1,"count":count,"items":min(count,300),
                    "started_at":"2026-10-29T00:00:00+00:00","ended_at":"2026-10-29T00:00:00.001+00:00"},
                "capture_count":len(statements),"query_count":len(statements)-1,"plan_count":len(statements)-1,"statements":statements})
    write(root,f"baseline-{size}.json",baseline)
    resource_path = root / "resources.jsonl"
    rows = [json.loads(line) for line in resource_path.read_text().splitlines()] if resource_path.exists() else []
    rows = [r for r in rows if r.get("run_id") != run_id]
    identity = {"provenance":provenance,"run_id":run_id,"monitor_id":"monitor-"+run_id,"profile":"fanout" if sources == 10 else "baseline","db_container_id":"e"*64}
    rows += [{**identity,"kind":"monitor-start","at":"2026-10-29T00:00:00+00:00","interval_seconds":5},
        *[{**identity,"kind":"sample","at":f"2026-10-29T00:00:0{s}+00:00","db":{"CPUPerc":"2%","MemPerc":"3%"}} for s in (0,5)],
        {**identity,"kind":"monitor-stop","status":"stopped","at":"2026-10-29T00:00:06+00:00"}]
    resource_path.write_text("\n".join(json.dumps(r) for r in rows),encoding="utf-8")


def report(root, monkeypatch):
    monkeypatch.setattr("sys.argv", ["summarize-ai-map-capacity.py", str(root)])
    module("summarize-ai-map-capacity").main()
    return (root / "REPORT_RU.md").read_text(encoding="utf-8"), json.loads((root / "summary.json").read_text())


@pytest.mark.parametrize("damage", [None, "missing_config", "wrong_config", "missing_plan_setting", "unknown_contract", "extra_query"])
def test_single_pass_contract_attests_jit_dispatch_and_explain_settings(tmp_path, damage):
    complete(tmp_path)
    records = json.loads((tmp_path / "baseline-100000.json").read_text())
    for record in records:
        old = [row for row in record["statements"] if row["category"] == "map-query"]
        plan = json.loads((tmp_path / old[0]["plan_file"]).read_text())
        for row in old:
            (tmp_path / row["plan_file"]).unlink()
        filename = f"plan-100000-{record['candidates']}-z{record['zoom']}-2.json"
        plan.update(statement_index=2, query_settings={"jit":"off"})
        write(tmp_path, filename, plan)
        config = {"category":"query-config", "ordinal":1, "sql":"SET LOCAL jit = off",
                  "sql_sha256":hashlib.sha256(b"SET LOCAL jit = off").hexdigest(), "parameters":[]}
        record.update(query_contract="single-pass-jit.v1", query_settings={"jit":"off"},
                      capture_count=3, query_count=1, plan_count=1,
                      statements=[record["statements"][0], config, {**old[0], "ordinal":2,"plan_file":filename}])
    if damage == "missing_config":
        records[0]["statements"].pop(1)
    elif damage == "wrong_config":
        records[0]["statements"][1]["sql"] = "SET jit = off"
    elif damage == "missing_plan_setting":
        filename = records[0]["statements"][2]["plan_file"]
        plan = json.loads((tmp_path / filename).read_text())
        del plan["query_settings"]
        write(tmp_path, filename, plan)
    elif damage == "unknown_contract":
        records[0]["query_contract"] = "unattested.v2"
    elif damage == "extra_query":
        records[0]["statements"].append({**records[0]["statements"][2], "ordinal":3})
        records[0].update(capture_count=4, query_count=2, plan_count=2)
    write(tmp_path, "baseline-100000.json", records)
    result = module("summarize-ai-map-capacity").summarize(tmp_path)
    assert result["completed_scales"] == ([100000] if damage is None else [])


@pytest.mark.parametrize("sources,expected", [(2, "200,000"), (10, "1,000,000")])
def test_report_uses_actual_source_profile(tmp_path, monkeypatch, sources, expected):
    complete(tmp_path, sources=sources)
    text, _ = report(tmp_path, monkeypatch)
    assert f"| 100,000 | {expected} | 2,000,000 |" in text
    assert f"{sources} записей источника" in text
    assert f"({sources} источников / 20 наблюдений)" in text
    assert "На 100 тысячах — 200 попыток" not in text


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
    assert quality["status"] == {"missing": "missing", "complete": "unknown", "legacy": "unknown",
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
    write(output, "experiment.json", {"experiment_id":"a"*32, "db_container_id":"e"*64,
        "db_image_id":"sha256:"+"a"*64,"sources":2})
    result = powershell(ps_project,
        "& $root/scripts/monitor-ai-map.ps1 -OutputDirectory $root/output/monitor -RunId " + "b"*32 + " -MaxConsecutiveFailures 2", mode)
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


@pytest.mark.parametrize("samples", [1, 49, 99, 199])
def test_probe_cannot_complete_protocol(tmp_path, samples):
    complete(tmp_path)
    cases = json.loads((tmp_path / "load-100000.json").read_text())
    for case in cases:
        case.update(samples=samples, requested_samples=samples)
        case["results"] = case["results"][:samples]
    write(tmp_path, "load-100000.json", cases)
    assert not module("summarize-ai-map-capacity").summarize(tmp_path)["completed_scales"]


def test_all_protocol_scales_and_confirmed_failed_wave(tmp_path):
    for size in (100000, 500000, 1000000):
        complete(tmp_path, size)
    cases = json.loads((tmp_path / "load-500000.json").read_text())
    for case in cases:
        case["results"] = [{**r, "ok":False, "error":"SyntheticError","detail":"forced failure","sqlstate":"57014"} for r in case["results"][:case["concurrency"]]]
        case.update(samples=len(case["results"]), failures=len(case["results"]),
            stopped_after_failed_wave=len(case["results"]) < 200, **{"pass":False})
    write(tmp_path, "load-500000.json", cases)
    result = module("summarize-ai-map-capacity").summarize(tmp_path)
    assert result["status"] == "COMPLETE"
    assert result["completed_scales"] == [100000,500000,1000000]
    assert all(not case["pass"] for case in result["scales"][1]["load"])


@pytest.mark.parametrize("field,value", [("p99_ms", 999), ("pass", False), ("failures", 1), ("p50_ms", 2)])
def test_derived_metrics_are_recomputed(tmp_path, field, value):
    complete(tmp_path)
    cases = json.loads((tmp_path / "load-100000.json").read_text())
    cases[0][field] = value
    write(tmp_path, "load-100000.json", cases)
    result = module("summarize-ai-map-capacity").summarize(tmp_path)
    assert result["status"] == "INCONSISTENT" and not result["completed_scales"]
    assert result["scales"][0]["load"][0][field] == {"p99_ms":1, "pass":True, "failures":0,"p50_ms":1}[field]


@pytest.mark.parametrize("part", ["dataset", "load", "cancellation", "template", "manifest", "experiment", "missing_manifest", "running_manifest", "proof-verification"])
def test_mixed_or_missing_phase_provenance_fails_closed(tmp_path, part):
    complete(tmp_path)
    if part in {"manifest", "missing_manifest", "running_manifest"}:
        path = next(tmp_path.glob("runner-measure-*.json"))
    else:
        path = tmp_path / (part + ("-100000" if part in {"dataset", "load", "cancellation", "proof-verification"} else "") + ".json")
    if part == "missing_manifest":
        path.unlink()
    else:
        value = json.loads(path.read_text())
        record = value[0] if isinstance(value, list) else value
        provenance = record if part == "experiment" else record["provenance"]
        if part == "running_manifest":
            record["status"] = "running"
        else:
            provenance["code_revision"] = "0"*40
        write(tmp_path, path.name, value)
    result = module("summarize-ai-map-capacity").summarize(tmp_path)
    assert result["status"] == "INCONSISTENT" and not result["completed_scales"]


def test_summary_cli_fails_with_a_reviewable_report_for_tampered_metrics(tmp_path, monkeypatch):
    complete(tmp_path)
    path = tmp_path / "load-100000.json"
    cases = json.loads(path.read_text())
    cases[0]["p99_ms"] = 9999
    write(tmp_path,path.name,cases)
    monkeypatch.setattr("sys.argv",["summarize-ai-map-capacity.py",str(tmp_path)])
    assert module("summarize-ai-map-capacity").main() == 1
    assert "INCONSISTENT" in (tmp_path / "REPORT_RU.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("field", ["cancelled", "cancel_accepted", "active_before_cancel"])
def test_finished_tasks_are_not_confirmed_cancellations(tmp_path, field):
    complete(tmp_path)
    path = tmp_path / "cancellation-100000.json"
    value = json.loads(path.read_text())
    value.update({field:0, "completed_before_cancel":20})
    write(tmp_path, path.name, value)
    assert not module("summarize-ai-map-capacity").summarize(tmp_path)["completed_scales"]


def test_sequential_attempts_do_not_prove_concurrency(tmp_path):
    complete(tmp_path)
    cases = json.loads((tmp_path / "load-100000.json").read_text())
    for attempt in cases[0]["results"]:
        attempt["ended_at"] = attempt["started_at"]
    write(tmp_path, "load-100000.json", cases)
    assert not module("summarize-ai-map-capacity").summarize(tmp_path)["completed_scales"]


@pytest.mark.parametrize("damage", [None,"stale_run","stale_experiment","outside","gap","no_stop","wrong_db","two_starts"])
def test_monitoring_covers_the_specific_load_run(tmp_path, damage):
    complete(tmp_path)
    case = json.loads((tmp_path / "load-100000.json").read_text())[0]
    identity = {"provenance":case["provenance"],"run_id":case["run_id"],"monitor_id":"m1",
        "profile":"baseline","db_container_id":"e"*64}
    rows = [{**identity,"kind":"monitor-start","at":"2026-10-29T00:00:00+00:00","interval_seconds":5},
        *[{**identity,"kind":"sample","at":f"2026-10-29T00:00:0{s}+00:00",
            "db":{"CPUPerc":"2%","MemPerc":"3%"}} for s in (0,5)],
        {**identity,"kind":"monitor-stop","status":"stopped","at":"2026-10-29T00:00:06+00:00"}]
    if damage == "stale_run":
        rows = [{**r,"run_id":"old"} for r in rows]
    elif damage == "stale_experiment":
        rows = [{**r,"provenance":{**r["provenance"],"code_revision":"0"*40}} for r in rows]
    elif damage == "outside":
        rows = [{**r,"at":r["at"].replace("2026-10-29","2026-10-28")} for r in rows]
    elif damage == "gap":
        rows[0]["at"] = "2026-10-28T23:00:00+00:00"
    elif damage == "no_stop":
        rows.pop()
    elif damage == "wrong_db":
        rows = [{**r,"db_container_id":"0"*64} for r in rows]
    elif damage == "two_starts":
        rows.insert(0, rows[0])
    (tmp_path / "resources.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    result = module("summarize-ai-map-capacity").summarize(tmp_path)
    assert (result["scales"][0]["monitoring"] == "complete") == (damage is None)
    assert (result["monitoring"]["status"] == "complete") == (damage is None)


@pytest.mark.parametrize("mode", ["wrong_network","wrong_network_id","wrong_alias","wrong_image","wrong_database"])
def test_launcher_rejects_db_identity_before_runner(ps_project, mode):
    result = powershell(ps_project,"& $root/scripts/run-ai-map-benchmark.ps1 -Phase initialize",mode)
    assert result.returncode != 0
    assert "run" not in (ps_project / "output/docker-calls.txt").read_text().splitlines()


@pytest.mark.parametrize("field", ["code_revision","runner_image_id","archive_sha256","db_container_id","sources"])
def test_experiment_is_immutable(tmp_path, monkeypatch, field):
    bench = module("benchmark-ai-map")
    monkeypatch.setattr(bench,"OUT",tmp_path)
    env = {"R01_EXPERIMENT_ID":"a"*32,"R01_RUN_ID":"1"*32,"R01_CODE_REVISION":"b"*40,
        "R01_IMAGE_ID":"sha256:"+"c"*64,"R01_SOURCE_ARCHIVE_SHA256":"d"*64,
        "R01_DB_ID":"e"*64,"R01_DB_IMAGE_ID":"sha256:"+"f"*64,
        "R01_SOURCE_MODE":"git-archive","R01_CHECKOUT_CLEAN":"true"}
    for key,value in env.items():
        monkeypatch.setenv(key,value)
    bench.bind_experiment(2,"initialize")
    value = json.loads((tmp_path / "experiment.json").read_text())
    value[field] = 10 if field == "sources" else "changed"
    write(tmp_path,"experiment.json",value)
    with pytest.raises(RuntimeError,match="provenance mismatch"):
        bench.bind_experiment(2,"measure")


@pytest.mark.parametrize("damage", ["entities","meta_sources","template","provenance", "providers", "trigger",
    "listings","listing_room_details","external_listing_sources","ai_fact_catalogs","ai_listing_fact_batches",
    "ai_fact_sources","ai_listing_facts","ai_listing_search_features","ai_query_proofs",
    "live_contract","live_coverage","live_trigger"])
async def test_measure_validates_dataset_before_timed_sql(tmp_path, monkeypatch, damage):
    bench = module("benchmark-ai-map")
    models = (bench.Listing, bench.ListingRoomDetails, bench.ExternalListingSource, bench.AiFactCatalog,
        bench.AiListingFactBatch, bench.AiFactSource, bench.AiListingFact, bench.AiListingSearchFeatures, bench.AiQueryProof)
    counts = {model.__tablename__:101*(20 if model is bench.AiListingFact else 2 if model in
        (bench.ExternalListingSource,bench.AiFactSource,bench.AiListingFactBatch) else 1) for model in models}
    assert damage in {"entities","meta_sources","template","provenance","providers","trigger",
                     "live_contract","live_coverage","live_trigger",*counts}
    provenance = {"sources":2}
    meta = {"synthetic_only":True,"sources":2,"provenance":provenance,"generation":1}
    template = {"listing":"synthetic","sources":2,"observations":20,"provenance":provenance}
    value = {**dataset(100),"counts_including_template":counts,"distinct_providers":10,"provenance":provenance,
             "live_inputs_contract":"wrong" if damage == "live_contract" else "live-inputs.v1","fast_proof_count":101,
             "validity_contract":"live-validity.fk.v1"}
    if damage == "meta_sources": meta["sources"] = 10
    if damage == "template": template["sources"] = 10
    if damage == "provenance": value["provenance"] = {}
    write(tmp_path,"template.json",template)
    write(tmp_path,"dataset-100.json",value)
    connection = AsyncMock()
    connection.__aenter__.return_value = connection
    connection.scalar.side_effect = [meta, 99 if damage == "entities" else 100,
        *[number-1 if name == damage else number for name,number in counts.items()],
        9 if damage == "providers" else 10,"D" if damage == "trigger" else "O",
        100 if damage == "live_coverage" else 101,None if damage == "live_trigger" else "ready"]
    db = Mock()
    db.connect.return_value = connection
    db.dispose = AsyncMock()
    monkeypatch.setattr(bench,"engine",Mock(return_value=db))
    monkeypatch.setattr(bench,"verify_database_identity",AsyncMock())
    timed = Mock(side_effect=AssertionError("timed queries must not start"))
    monkeypatch.setattr(bench,"async_sessionmaker",timed)
    monkeypatch.setattr(bench,"OUT",tmp_path)
    monkeypatch.setattr(bench,"PROVENANCE",provenance)
    with pytest.raises(RuntimeError,match="dataset|trigger"):
        await bench.measure(100,200)
    timed.assert_not_called()
    assert not list(tmp_path.glob("load-*.json"))


@pytest.mark.parametrize("damage", ["missing_baseline","partial_baseline","no_capture","wrong_count",
    "missing_plan","invalid_plan","double_failure","wrong_hash"])
def test_protocol_requires_baseline_and_every_captured_plan(tmp_path, damage):
    for size in (100000,500000,1000000):
        complete(tmp_path,size)
    path = tmp_path / "baseline-100000.json"
    records = json.loads(path.read_text())
    plan_path = tmp_path / records[0]["statements"][1]["plan_file"]
    if damage == "missing_baseline":
        path.unlink()
    elif damage == "partial_baseline":
        write(tmp_path,path.name,records[:-1])
    elif damage in {"no_capture","wrong_count"}:
        if damage == "no_capture":
            records[0].update(statements=[],capture_count=0,query_count=0,plan_count=0)
        else:
            records[0]["first_touch"]["count"] = 999
        write(tmp_path,path.name,records)
    elif damage == "missing_plan":
        plan_path.unlink()
    else:
        plan = json.loads(plan_path.read_text())
        if damage == "invalid_plan": plan["plan"] = []
        if damage == "double_failure": plan.update(status="failed",analyze_error="timeout",estimate_error="failed")
        if damage == "wrong_hash": plan["sql_sha256"] = "0"*64
        write(tmp_path,plan_path.name,plan)
    result = module("summarize-ai-map-capacity").summarize(tmp_path)
    scale = result["scales"][0]
    assert scale["seed_attested"] and scale["load_complete"] and scale["resource_attested"]
    assert not scale["protocol_complete"] and not result["protocol_complete"]
    assert result["status"] != "COMPLETE" and not result["slo_passed"]


def test_explicit_estimated_only_plan_can_complete_evidence(tmp_path):
    complete(tmp_path)
    path = tmp_path / "baseline-100000.json"
    rows = json.loads(path.read_text())
    trace = rows[0]["statements"][1]
    trace["plan_status"] = "estimated-only"
    plan_path = tmp_path / trace["plan_file"]
    plan = json.loads(plan_path.read_text())
    plan.update(status="estimated-only",analyze_error={"type":"TimeoutError","detail":"synthetic timeout"},plan=[{"Plan":{"Node Type":"Result"}}])
    write(tmp_path,plan_path.name,plan)
    write(tmp_path,path.name,rows)
    scale = module("summarize-ai-map-capacity").summarize(tmp_path)["scales"][0]
    assert scale["plans_attested"] and scale["protocol_complete"]


@pytest.mark.parametrize("damage", ["missing","run_id","gap","error","extra_lifecycle"])
def test_global_complete_requires_resource_attestation(tmp_path, damage):
    for size in (100000,500000,1000000):
        complete(tmp_path,size)
    path = tmp_path / "resources.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if damage == "missing":
        path.unlink()
    else:
        if damage == "run_id": rows = [{**r,"run_id":"stale"} for r in rows]
        if damage == "gap": rows[0]["at"] = "2026-10-28T23:00:00+00:00"
        if damage == "error": rows.append({**rows[0],"kind":"monitor-error"})
        if damage == "extra_lifecycle": rows.append({**rows[0],"monitor_id":"unpaired-monitor"})
        path.write_text("\n".join(json.dumps(r) for r in rows))
    result = module("summarize-ai-map-capacity").summarize(tmp_path)
    assert all(s["load_complete"] for s in result["scales"])
    assert not result["protocol_complete"] and result["status"] != "COMPLETE"


@pytest.mark.parametrize("damage", ["negative_seconds","nan_seconds","wrong_seconds","missing_query_ms","negative_pool_ms",
    "nan_query_ms","component_sum","clock_mismatch","missing_error"])
def test_raw_timing_and_failure_diagnosis_are_validated(tmp_path, monkeypatch, damage):
    complete(tmp_path)
    path = tmp_path / "load-100000.json"
    cases = json.loads(path.read_text())
    case, attempt = cases[0], cases[0]["results"][0]
    if damage == "negative_seconds": case["seconds"] = -1
    if damage == "nan_seconds": case["seconds"] = float("nan")
    if damage == "wrong_seconds": case["seconds"] = 100
    if damage == "missing_query_ms": attempt.pop("query_ms")
    if damage == "negative_pool_ms": attempt["pool_ms"] = -1
    if damage == "nan_query_ms": attempt["query_ms"] = float("nan")
    if damage == "component_sum": attempt["pool_ms"] = 100
    if damage == "clock_mismatch": attempt["ended_at"] = "2026-10-29T00:00:02+00:00"
    if damage == "missing_error":
        attempt["ok"] = False
        case.update(failures=1,**{"pass":False})
    write(tmp_path,path.name,cases)
    monkeypatch.setattr("sys.argv",["summarize-ai-map-capacity.py",str(tmp_path)])
    assert module("summarize-ai-map-capacity").main() == 1
    result = json.loads((tmp_path / "summary.json").read_text())
    assert result["status"] == "INCONSISTENT" and not result["scales"][0]["load_complete"]


@pytest.mark.parametrize("damage", ["manifest","proof","counts","generation","proof_ordinals","providers"])
def test_dataset_file_presence_is_separate_from_attested_seed(tmp_path, damage):
    complete(tmp_path)
    if damage == "manifest":
        next(tmp_path.glob("runner-seed-*.json")).unlink()
    elif damage == "proof":
        (tmp_path / "proof-verification-100000.json").unlink()
    elif damage == "proof_ordinals":
        path = tmp_path / "proof-verification-100000.json"
        value = json.loads(path.read_text())
        value["ordinals"] = [100000]
        write(tmp_path,path.name,value)
    else:
        path = tmp_path / "dataset-100000.json"
        value = json.loads(path.read_text())
        if damage == "counts": value["counts_including_template"].pop("ai_query_proofs")
        if damage == "generation": value["seed_generation"] = 2
        if damage == "providers": value["distinct_providers"] = 1
        write(tmp_path,path.name,value)
    scale = module("summarize-ai-map-capacity").summarize(tmp_path)["scales"][0]
    assert scale["dataset_file_present"] and not scale["seed_attested"] and not scale["dataset_complete"]


def test_experiment_output_lock_excludes_other_processes_and_releases(tmp_path, monkeypatch):
    bench = module("benchmark-ai-map")
    monkeypatch.setattr(bench,"OUT",tmp_path)
    code = ("import importlib.util,sys; from pathlib import Path; "
        "s=importlib.util.spec_from_file_location('bench',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "m.OUT=Path(sys.argv[2]); lock=m.phase_file_lock(); lock.__enter__(); lock.__exit__(None,None,None)")
    command = [sys.executable,"-c",code,str(ROOT / "scripts/benchmark-ai-map.py"),str(tmp_path)]
    env = {**os.environ,"PYTHONPATH":str(ROOT / "backend")}
    with bench.phase_file_lock():
        blocked = subprocess.run(command,env=env,capture_output=True,text=True,timeout=30,check=False)
        assert blocked.returncode != 0 and "another phase owns" in blocked.stderr
    released = subprocess.run(command,env=env,capture_output=True,text=True,timeout=30,check=False)
    assert released.returncode == 0,released.stderr


async def test_double_explain_failure_is_retained_as_an_artifact(tmp_path, monkeypatch):
    bench = module("benchmark-ai-map")
    db = Mock()
    db.connect.side_effect = RuntimeError("synthetic explain failure")
    result = await bench.explain_statement(db,"WITH fixture AS (SELECT 1) SELECT * FROM fixture",[])
    assert result["status"] == "failed" and result["analyze_error"] and result["estimate_error"]
    monkeypatch.setattr(bench,"OUT",tmp_path)
    bench.save("failed-plan.json",result)
    assert json.loads((tmp_path / "failed-plan.json").read_text())["status"] == "failed"
