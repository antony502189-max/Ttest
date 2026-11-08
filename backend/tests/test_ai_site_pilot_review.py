import importlib.util
import json
import multiprocessing
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi import Request

from app.repositories.ai_verified_cards import SourceCoverageUnavailable
from app.schemas.ai_search_intent import Criteria, SearchIntent
from app.services.ai_deepseek_intent import ProviderFailure
from app.services.ai_http_policy import AIHTTPPolicy
from pilot.budget import ATTEMPT, BINDING, PilotBudget
from pilot.entry import PilotParser, PilotTransport
from pilot.surface import minimal_app


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/listings", "/api/v1/payments", "/api/v1/admin", "/api/v1/uploads", "/api/docs", "/api/openapi.json", "/openapi.json", "/api/v1/ai-search/unknown"])
async def test_minimal_asgi_denies_other_routes_without_cookies(path):
    app = minimal_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://app.112233.es") as client:
        for method in ("GET", "POST", "PUT", "DELETE"):
            response = await client.request(method, path, json={"private": "must_not_reach_handler"})
            assert response.status_code == 404 and "set-cookie" not in response.headers
        assert (await client.get("/api/v1/ai-search/capabilities")).status_code == 200
        assert (await client.post("/api/v1/ai-search/capabilities")).status_code == 404


def test_only_exact_nginx_peer_supplies_sanitized_ip():
    policy = AIHTTPPolicy(20, 3, ("172.30.41.2/32",), "https://app.112233.es")
    def request(peer, claimed):
        return Request({"type": "http", "client": (peer, 1000), "headers": [(b"x-real-ip", claimed.encode())]})
    assert policy.address(request("172.30.41.2", "198.51.100.10")) == "198.51.100.10"
    assert policy.address(request("172.30.41.2", "198.51.100.11")) == "198.51.100.11"
    assert policy.address(request("172.30.41.3", "198.51.100.10")) == "172.30.41.3"


@pytest.mark.asyncio
async def test_expired_catalog_blocks_before_key_read_budget_or_transport(tmp_path, monkeypatch):
    from pilot import entry
    budget = PilotBudget(tmp_path / "provider.sqlite3", initialize=True)
    async def stale(): return {"catalog_ready": False}
    monkeypatch.setattr(entry, "approved", lambda: True)
    parser = PilotParser(budget, stale)
    current = SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1", session_id=uuid4(), version=0,
        criteria=Criteria.model_validate({"rental_mode": {"strength": "hard", "value": "long"}}))
    with pytest.raises(SourceCoverageUnavailable, match="PILOT_CATALOG_STALE"):
        await parser.parse("до 600 евро в месяц", current)
    assert budget.summary()["attempts"] == 0


def revoke_file(path):
    Path(path).rename(Path(path).with_suffix(".disabled"))


@pytest.mark.asyncio
async def test_external_process_revokes_after_preflight_before_reserve(tmp_path, monkeypatch):
    from pilot import entry
    monkeypatch.setattr(entry, "CONTROL", tmp_path)
    artifact = tmp_path / "approval.json"
    artifact.write_text(json.dumps({"binding": BINDING, "owner_approved": True, "max_calls": 50,
        "max_micro_usd": 1_000_000, "scope": "owner-team-nonpersonal-positive-rent-grammar.v1"}))
    budget = PilotBudget(tmp_path / "provider.sqlite3", initialize=True)
    budget.dispatch_guard = entry.require_approval
    assert entry.approved()
    process = multiprocessing.get_context("spawn").Process(target=revoke_file, args=(str(artifact),))
    process.start()
    process.join(10)
    if process.is_alive():
        process.kill()
        process.join()
    assert process.exitcode == 0
    called = []
    async def ready(): return {"catalog_ready": True}
    transport = PilotTransport(httpx.MockTransport(lambda request: called.append(request)), budget, ready)
    token = ATTEMPT.set("revoked-before-dispatch")
    try:
        with pytest.raises(ProviderFailure, match="APPROVAL_REQUIRED"):
            await transport.handle_async_request(httpx.Request("POST", "https://api.deepseek.com/chat/completions"))
        with pytest.raises(ProviderFailure, match="APPROVAL_REQUIRED"):
            budget.reserve()  # Independent last synchronous guard, in DB transaction.
    finally:
        ATTEMPT.reset(token)
    assert called == [] and budget.summary()["attempts"] == 0


@pytest.mark.parametrize("stop_fails", [False, True])
def test_revocation_always_stops_network_and_restarts_backend_preserving_journal(tmp_path, monkeypatch, stop_fails):
    source = Path(__file__).parents[2]/"deploy/ai-site-pilot/revoke.py"
    spec = importlib.util.spec_from_file_location("pilot_revoke_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path/"owner-purpose").write_text("ai-site-pilot-20261108; owned test")
    control = tmp_path/"deploy/ai-site-pilot/control"
    control.mkdir(parents=True)
    (control/"approval.json").write_text("owner approval retained")
    journal = tmp_path/"provider.sqlite3"
    journal.write_bytes(b"durable-reserved-counter-do-not-reset")
    calls = []
    def run(command, check):
        calls.append(command[-2:])
        if stop_fails and command[-2:] == ["stop","ttest-ai-site-pilot-20261108-egress-1"]:
            raise RuntimeError("fixture stop failure")
    monkeypatch.setattr(module,"Path",lambda _value:tmp_path)
    monkeypatch.setattr(module.subprocess,"run",run)
    monkeypatch.setattr(module.subprocess,"check_output",lambda *args,**kwargs:"ai-site-pilot-20261108\n")
    if stop_fails:
        with pytest.raises(RuntimeError,match="fixture stop failure"):module.revoke()
    else:module.revoke()
    assert calls == [["stop","ttest-ai-site-pilot-20261108-egress-1"],["restart","ttest-ai-site-pilot-20261108-backend-1"]]
    assert journal.read_bytes() == b"durable-reserved-counter-do-not-reset"
    assert not (control/"approval.json").exists() and len(list(control.glob("approval.revoked-*.json"))) == 1
