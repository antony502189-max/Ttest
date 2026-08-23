from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "deploy" / "production-acceptance.sh").read_text(encoding="utf-8")


def test_acceptance_runner_is_autonomous_and_low_priority() -> None:
    assert "systemd-run" in SCRIPT
    assert "--property=Nice=10" in SCRIPT
    assert "--property=CPUWeight=1" in SCRIPT
    assert "--property=IOWeight=1" in SCRIPT
    assert "SKIPPED_RESOURCE_PRESSURE" in SCRIPT
    assert "flock -n 9" in SCRIPT
    assert "timeout --foreground" in SCRIPT


def test_acceptance_runner_reuses_production_monitor_and_keeps_import_evidence() -> None:
    assert "production-monitor-check.sh" in SCRIPT
    assert "external_worker_state" in SCRIPT
    assert "external_import_runs" in SCRIPT
    assert "discovery_complete" in SCRIPT
    assert "discovered_urls" in SCRIPT
    assert "fetched_details" in SCRIPT
    assert "accepted_rooms" in SCRIPT
    assert "IMPORT_SNAPSHOT_RETURN_CODE" in SCRIPT


def test_acceptance_runner_is_observational_not_self_healing() -> None:
    lowered = SCRIPT.lower()
    assert "docker compose down" not in lowered
    assert "docker restart" not in lowered
    assert "systemctl restart" not in lowered
    assert "rollback-release.sh" not in lowered
    assert "backup-production.sh" not in lowered
    assert "restore-verify.sh" not in lowered


def test_acceptance_runner_exposes_operational_commands() -> None:
    for command in ("start", "burn-in", "status", "follow", "stop", "report"):
        assert command in SCRIPT
    assert "ELAPSED=" in SCRIPT
    assert "REMAINING=" in SCRIPT
    assert "FINAL_STATUS" in SCRIPT
