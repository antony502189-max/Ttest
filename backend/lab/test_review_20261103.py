"""PR404 F1-F8 regressions. Disposable files, MockTransport, no real account."""
import hashlib
import json
import logging
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.services.ai_closed_deepseek import MAX_MICRO_USD, RESERVE_MICRO_USD
from app.services.ai_deepseek_intent import ProviderFailure
from lab.closed_ui import ExistingSmokeBudget, _UIBudgetTransport, smoke_cases
from lab.closed_ui_access import ClosedSmokeAccess, load_proxy_secret
from lab.closed_ui_authorization import canonical, verify, verify_operational_review
from lab.closed_ui_spec import CASE_IDS, CORPUS_SHA256, SPEC
from lab.closed_ui_test_support import SOURCE, admission_fixture, signed_fixture
from lab.intent_eval import state
from lab.runtime_contract import ATTESTATION, LabRuntime, RuntimePairing
from lab.test_closed_ui import journal, parser_at


async def test_fetched_public_attestation_is_not_closed_smoke_authorization():
    entered = []
    async def query(request):
        entered.append(True)
        return JSONResponse({"entered": True})
    app = Starlette(routes=[Route("/api/v1/ai-search/query", query, methods=["POST"])])
    runtime = LabRuntime.create("closed-live-synthetic", SOURCE, "mock")
    app.state.ai_lab_runtime = runtime
    app.add_middleware(RuntimePairing)
    app.add_middleware(ClosedSmokeAccess, secret=b"a" * 64)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://localhost") as client:
        metadata = (await client.get(ATTESTATION)).json()
        headers = {"X-AI-Lab-Mode": metadata["parser"], "X-AI-Lab-Source": metadata["source"],
                   "X-AI-Lab-Instance": metadata["instance"]}
        assert (await client.post("/api/v1/ai-search/query", headers=headers)).status_code == 403
        assert not entered
        assert (await client.post("/api/v1/ai-search/query", headers=headers | {"X-AI-Lab-Access": "wrong"})).status_code == 403
        assert (await client.post("/api/v1/ai-search/query", headers=headers | {"X-AI-Lab-Access": "a" * 64})).status_code == 200
    assert entered == [True]
    assert "a" * 64 not in json.dumps(metadata)


@pytest.mark.parametrize("path", ["/api/v1/ai-search", "/api/v1/ai-search/", "/api/v1/ai-search/query", "/api/v1/ai-search//query"])
async def test_http_namespace_and_websockets_never_bypass_pairing(path):
    entered = []
    async def downstream(scope, receive, send):
        entered.append(scope)
    middleware = RuntimePairing(downstream)
    app = Starlette()
    app.state.ai_lab_runtime = LabRuntime.create("finite", SOURCE, "none")
    messages = []
    async def send(message):
        messages.append(message)
    async def receive():
        return {"type": "http.request", "body": b""}
    for kind in ("http", "websocket"):
        await middleware({"type": kind, "path": path, "method": "POST", "headers": [], "app": app}, receive, send)
    assert not entered
    assert messages[0]["status"] == 409
    assert messages[-1] == {"type": "websocket.close", "code": 1008}


def test_proxy_include_is_strict_and_closed_nginx_requires_mtls(tmp_path):
    path = tmp_path / "proxy.conf"
    for value in ('proxy_set_header X-AI-Lab-Access "weak";', 'arbitrary nginx;'):
        path.write_text(value)
        with pytest.raises(RuntimeError):
            load_proxy_secret(path)
    path.write_text('proxy_set_header X-AI-Lab-Access "' + 'a' * 64 + '";\n')
    assert load_proxy_secret(path) == b"a" * 64
    root = Path(__file__).resolve().parents[2]
    config = (root / "deploy/ai-text-lab/closed-ui.nginx.conf").read_text()
    assert "ssl_verify_client on;" in config
    assert "include /closed-ui-access/proxy.conf;" in config
    # proxy_pass has no URI suffix: the original /api/v1/ai-search path survives.
    assert "proxy_pass http://backend:8000;" in config
    assert "closed-ui" not in (root / "deploy/ai-text-lab/compose.yml").read_text()


def _reserve_in_process(args):
    path, admission = args
    try:
        return ExistingSmokeBudget(path, corpus_sha256=CORPUS_SHA256, admission=admission).reserve("ru-balcony")
    except ProviderFailure as error:
        return str(error)


def test_journal_fence_across_separate_processes_and_restart(tmp_path):
    path = journal(tmp_path)
    proof = admission_fixture(path)
    with ProcessPoolExecutor(max_workers=3, mp_context=multiprocessing.get_context("spawn")) as pool:
        outcomes = list(pool.map(_reserve_in_process, [(path, proof)] * 6))
    assert sum(type(value) is int for value in outcomes) == 1
    assert outcomes.count("UI_SMOKE_CASE_ALREADY_ATTEMPTED") == 5
    restarted = ExistingSmokeBudget(path, corpus_sha256=CORPUS_SHA256, admission=proof)
    assert restarted.summary()["attempts"] == 52
    with pytest.raises(ProviderFailure, match="CASE_ALREADY_ATTEMPTED"):
        restarted.reserve("ru-balcony")


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership/mode certification requires Linux")
def test_group_writable_journal_or_directory_refused(tmp_path):
    path = journal(tmp_path)
    for item in (path, tmp_path):
        previous = item.stat().st_mode & 0o777
        try:
            item.chmod(previous | 0o020)
            with pytest.raises(ProviderFailure, match="UNSAFE_PERMISSIONS"):
                admission_fixture(path)
        finally:
            item.chmod(previous)


def test_same_spec_binds_budget_corpus_and_selected_cases():
    from lab.closed_ui_authorization import CASE_IDS as admitted_cases
    assert admitted_cases == CASE_IDS == tuple(c["id"] for c in smoke_cases()[0])
    assert SPEC.reserve_micro_usd == RESERVE_MICRO_USD
    assert SPEC.max_micro_usd == MAX_MICRO_USD
    assert SPEC.attempt_fence == 54


def review_bytes(**changes):
    now = datetime.now(UTC)
    data = {"schema": "ai-closed-ui-operational-review.v1", "source": SOURCE,
            "account_reference": "DISPOSABLE-account-not-real", "billing_scope": "dedicated synthetic fixture",
            "reviewer": "DISPOSABLE-reviewer", "verified_at": (now - timedelta(seconds=1)).isoformat(),
            "expires_at": (now + timedelta(minutes=30)).isoformat(), "external_cap_micro_usd": SPEC.max_micro_usd,
            "provider_limit_verified": True, "credentials_scope_verified": True, "egress_reviewed": True,
            "client_access_reviewed": True, "journal_permissions_reviewed": True}
    return canonical(data | changes)


@pytest.mark.parametrize("fault", [None, "hash", "billing", "egress", "access", "expired", "timezone", "cap", "extra"])
def test_signed_account_review_artifact_is_required_not_just_hex_format(tmp_path, fault):
    changes = {"provider_limit_verified": False} if fault == "billing" else {}
    if fault == "egress": changes = {"egress_reviewed": False}
    if fault == "access": changes = {"client_access_reviewed": False}
    if fault == "expired": changes = {"expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}
    if fault == "timezone": changes = {"verified_at": "2026-11-03T00:00:00"}
    if fault == "cap": changes = {"external_cap_micro_usd": 1}
    if fault == "extra": changes = {"secret": "not accepted"}
    document = review_bytes(**changes)
    proof = admission_fixture(journal(tmp_path), external_cap_evidence_sha256=hashlib.sha256(document).hexdigest(),
                              expires_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat())
    if fault:
        with pytest.raises(ProviderFailure, match="OPERATIONAL_REVIEW_REQUIRED"):
            verify_operational_review(proof, document + b" " if fault == "hash" else document)
    else:
        verify_operational_review(proof, document)


@pytest.mark.parametrize("stamp", ["not-a-date", "2026-11-03T00:00:00", "2026-11-03T00:00:00+99:00"])
def test_invalid_authorization_timezones_fail_closed(tmp_path, stamp):
    document, public, pin = signed_fixture(journal(tmp_path), issued_at=stamp)
    with pytest.raises(ProviderFailure):
        verify(document, public, trusted_key_sha256=pin, source=SOURCE)


async def test_success_diagnostics_are_info_and_never_log_private_values(tmp_path, caplog):
    parser = parser_at(journal(tmp_path))
    async def response(request):
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps({"status": "patch", "patch": {
                "set": smoke_cases()[0][0]["expected"], "remove": []}})}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})
    parser.transport = _UIBudgetTransport(httpx.MockTransport(response), parser.budget)
    caplog.set_level(logging.INFO, logger="lab.closed_ui")
    await parser.parse(smoke_cases()[0][0]["text"], state(smoke_cases()[0][0]))
    records = [r for r in caplog.records if r.message.startswith("closed_ui_provider_http_status")]
    assert len(records) == 1 and records[0].levelno == logging.INFO
    assert smoke_cases()[0][0]["text"] not in caplog.text
