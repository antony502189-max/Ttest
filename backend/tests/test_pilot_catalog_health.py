"""Publication, operator failure and metrics contracts without any live host."""

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from pilot.catalog_health import CatalogHealth
from pilot.guarded_cards import GuardedCards
from pilot.surface import minimal_app


def test_generation_fencing_failure_age_and_corrupt_state_are_closed(tmp_path):
    health = CatalogHealth(tmp_path / "health.json", "c" * 64)
    with pytest.raises(ValueError):
        health.ticket()
    old = health.begin()
    new = health.begin()
    with pytest.raises(ValueError):
        health.publish(old, snapshot_at="synthetic", active=1, removed=0)
    health.publish(new, snapshot_at=datetime.now(UTC).isoformat(), active=1, removed=2)
    assert health.ticket() == new
    health.fail(old)
    assert health.ticket() == new
    health.fail(new)
    assert health._read()["consecutive_failures"] == 1
    with pytest.raises(ValueError):
        health.ticket()
    token = health.begin()
    health.publish(token, snapshot_at="synthetic", active=3, removed=0)
    value = health._read()
    value["last_success"] = (datetime.now(UTC) - timedelta(seconds=4501)).isoformat()
    health._write(value)
    with pytest.raises(ValueError):
        health.ticket()
    assert "ttest_pilot_catalog_ready 0" in health.metrics()
    health.path.write_text("not JSON")
    with pytest.raises(ValueError):
        health.ticket()


@pytest.mark.parametrize("method", ["_query_intent", "_map_intent"])
async def test_card_and_map_reads_reject_generation_changed_during_query(tmp_path, monkeypatch, method):
    from app.repositories.ai_verified_cards import SourceCoverageUnavailable, VerifiedCardSearch

    health = CatalogHealth(tmp_path / "health.json", "c" * 64)
    token = health.begin()
    health.publish(token, snapshot_at="synthetic", active=1, removed=0)
    guarded = object.__new__(GuardedCards)
    guarded.health = health

    async def query(self, *args, **kwargs):
        next_token = health.begin()
        health.publish(next_token, snapshot_at="synthetic", active=1, removed=0)
        return object()

    monkeypatch.setattr(VerifiedCardSearch, method, query)
    with pytest.raises(SourceCoverageUnavailable):
        await getattr(guarded, method)()


async def test_http_catalog_body_is_withheld_when_generation_changes(tmp_path):
    from fastapi import FastAPI

    from pilot.guarded_cards import install_catalog_guard

    health = CatalogHealth(tmp_path / "health.json", "c" * 64)
    app = FastAPI()
    calls = 0

    @app.post("/api/v1/ai-search/query")
    async def query():
        nonlocal calls
        calls += 1
        health.begin()
        return {"cards": "PRIVATE_UNPUBLISHED_CARD"}

    install_catalog_guard(app, health)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://private.test") as client:
        assert (await client.post("/api/v1/ai-search/query")).status_code == 503 and calls == 0
        token = health.begin()
        health.publish(token, snapshot_at="synthetic", active=1, removed=0)
        response = await client.post("/api/v1/ai-search/query")
        assert response.status_code == 503 and calls == 1 and "PRIVATE" not in response.text


@pytest.mark.parametrize("stage", ["export", "apply"])
def test_host_failure_closes_catalog_exports_redacted_alert_and_rerun_recovers(tmp_path, monkeypatch, capsys, stage):
    script = Path(__file__).parents[2] / "deploy/ai-site-pilot/refresh_catalog.py"
    spec = importlib.util.spec_from_file_location("host_refresh", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    directory = tmp_path / "catalog-refresh"
    directory.mkdir()
    (directory / "export_public.py").write_text("synthetic-export")
    (directory / "refresh.py").write_text("synthetic-updater")
    health = CatalogHealth(tmp_path / "state/health.json", "c" * 64)
    monkeypatch.setattr(module, "configured_health", lambda: health)
    fail = True

    def run(argv, payload=None):
        assert not any("provider" in str(item) for item in argv)
        if "synthetic-export" in argv:
            assert health._read()["phase"] == "refreshing"
            if fail and stage == "export":
                raise RuntimeError("PRIVATE_CANARY")
            return "READ ONLY FIXTURE SQL"
        if module.PRIMARY in argv:
            return json.dumps({"schema": "pilot-cohort.v2", "records": []})
        if "synthetic-updater" in argv:
            if fail and stage == "apply":
                raise RuntimeError("PRIVATE_CANARY")
            health.publish(argv[-1], snapshot_at=datetime.now(UTC).isoformat(), active=2, removed=1)
            return '{"refreshed":2,"removed":1,"provider_calls":0}'
        return 'ttest_ai_voice_execution_total{status="failed",replay="no",failure="ASR_FAILURE"} 1\n'

    monkeypatch.setattr(module, "run", run)
    with pytest.raises(SystemExit):
        module.main([])
    assert health._read()["consecutive_failures"] == 1
    assert "PRIVATE_CANARY" not in capsys.readouterr().out
    assert "ttest_pilot_catalog_ready 0" in (directory / "metrics/health.prom").read_text()
    fail = False
    module.main([])
    assert health.ticket() and health._read()["consecutive_failures"] == 0
    assert "ttest_pilot_catalog_ready 1" in (directory / "metrics/health.prom").read_text()
    module.main(["--failure"])
    with pytest.raises(ValueError):
        health.ticket()
    assert "PILOT_CATALOG_REFRESH_FAILED_CATALOG_BLOCKED" in capsys.readouterr().out
    module.main([])
    assert health.ticket()


async def test_metrics_endpoint_is_loopback_only_and_never_added_to_proxy_allowlist():
    app = minimal_app()
    for host, expected in [("127.0.0.1", 200), ("172.30.41.2", 404), ("203.0.113.5", 404)]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=(host, 123)), base_url="http://private.test"
        ) as client:
            response = await client.get("/private-metrics")
            assert response.status_code == expected
            assert (await client.get('/private-metrics',headers={'X-Forwarded-For':'127.0.0.1','X-Real-IP':'127.0.0.1'})).status_code==expected
            assert (await client.post("/private-metrics")).status_code == 404
    directory = Path(__file__).parents[2] / "deploy/ai-site-pilot"
    assert "/private-metrics" not in (directory / "nginx.conf").read_text()
    assert (
        "OnFailure=ttest-pilot-catalog-refresh-alert.service"
        in (directory / "ttest-pilot-catalog-refresh.service").read_text()
    )
    assert "--failure" in (directory / "ttest-pilot-catalog-refresh-alert.service").read_text()
    assert "OnUnitActiveSec=1min" in (directory / "ttest-pilot-metrics.timer").read_text()
