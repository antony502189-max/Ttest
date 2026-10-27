"""Review regressions for the private HTTP perimeter; no DB/provider calls."""
import asyncio
import logging
import time
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from app.api.v1.ai_search import AISearchRuntime
from app.main import app, metric_route_for, settings
from app.repositories.ai_search_quota import QuotaError
from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
from app.services.ai_http_policy import AIHTTPPolicy
from app.services.ai_search_attempts import AIAttemptRejected

HEADERS = {"Origin": "https://testserver", "X-AI-Request": "1"}


@pytest.fixture
def active(monkeypatch):
    sessions = SimpleNamespace(create=AsyncMock(return_value={"created": True}), get=AsyncMock(return_value={}))
    guests = GuestTokens(key=b"synthetic-guest-key-not-secret-32", policy=GuestPolicy(ttl_seconds=60))
    gate = SimpleNamespace(check=AsyncMock())
    value = AISearchRuntime(sessions, SimpleNamespace(sessions=sessions), SimpleNamespace(sessions=sessions),
                            guests, gate, frozenset({"https://testserver", settings.origins[0]}), 4096,
                            AIHTTPPolicy(1, 2, ("10.0.0.0/24",), "https://testserver"))
    monkeypatch.setattr(app.state, "ai_search_runtime", value, raising=False)
    return value


def test_proxy_identity_uses_explicit_trust_and_ignores_untrusted_forwarding(active):
    with TestClient(app, base_url="https://testserver", client=("10.0.0.2", 8000)) as client:
        for address in ("198.51.100.1", "198.51.100.2"):
            client.cookies.clear()
            assert client.post("/api/v1/ai-search/sessions", headers=HEADERS | {"X-Real-IP": address}).status_code == 200
        calls = [call.args[0] for call in active.http_gate.check.call_args_list]
        assert active.guests.ip_key("198.51.100.1", purpose="ai-http") in calls
        assert active.guests.ip_key("198.51.100.2", purpose="ai-http") in calls
        assert active.guests.ip_key("198.51.100.1", purpose="ai-guest-issue") in calls
        assert active.guests.ip_key("198.51.100.2", purpose="ai-guest-issue") in calls
    for forwarded in ("198.51.100.1", "198.51.100.2"):
        request = Request({"type": "http", "client": ("203.0.113.4", 8000), "headers": [
            (b"x-real-ip", forwarded.encode()), (b"x-forwarded-for", forwarded.encode())]})
        assert active.policy.address(request) == "203.0.113.4"
    assert any(call.args[0].startswith("ai-session-create:") for call in active.http_gate.check.call_args_list)
    assert all("guest:" not in call.args[0] for call in active.http_gate.check.call_args_list)


def test_cors_preflight_allows_ai_header_only_for_allowlisted_origin(active):
    with TestClient(app, base_url="https://testserver") as client:
        for origin, expected in ((settings.origins[0], 200), ("https://attacker.invalid", 400)):
            result = client.options("/api/v1/ai-search/sessions", headers={"Origin": origin,
                "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-ai-request,content-type"})
            assert result.status_code == expected
            if expected == 200:
                assert result.headers["access-control-allow-origin"] == origin
                assert "x-ai-request" in result.headers["access-control-allow-headers"].lower()
                # Preflight succeeds; the endpoint deliberately rejects a
                # cross-origin guest rather than issuing an unusable cookie.
                post = client.post("/api/v1/ai-search/sessions", headers={"Origin": origin, "X-AI-Request": "1"})
                assert post.status_code == 403 and post.json()["detail"] == "AI_GUEST_SAME_ORIGIN_REQUIRED"
            else:
                assert "access-control-allow-origin" not in result.headers
        assert client.post("/api/v1/ai-search/sessions", headers=HEADERS).status_code == 200


@pytest.mark.parametrize("path,method", [("/sessions/PRIVATE_SENTINEL", "get"),
    ("/results/PRIVATE_SENTINEL/cards", "post"), ("/PRIVATE_SENTINEL", "get")])
def test_unvalidated_private_paths_are_redacted_in_application_logs_and_metrics(active, caplog, path, method):
    token, _ = active.guests.issue()
    caplog.set_level(logging.INFO, logger="app.main")
    with TestClient(app, base_url="https://testserver") as client:
        response = getattr(client, method)("/api/v1/ai-search" + path,
            headers=HEADERS | {"Cookie": "ai_search_guest=" + token})
        assert response.status_code in {404, 422}
    records = [record for record in caplog.records if record.name == "app.main"]
    assert records
    assert all("PRIVATE_SENTINEL" not in str(record.__dict__) for record in records)
    request = Request({"type": "http", "path": "/api/v1/ai-search" + path, "headers": []})
    assert metric_route_for(request) == "/api/v1/ai-search/<private>"


@pytest.mark.parametrize("site", ["cross-site", "same-site"])
def test_guest_cookie_flow_rejects_external_documents_before_mint(active, site):
    with TestClient(app, base_url="https://testserver") as client:
        result = client.post("/api/v1/ai-search/sessions", headers=HEADERS | {"Sec-Fetch-Site": site})
        assert result.status_code == 403
        assert "set-cookie" not in result.headers
        active.sessions.create.assert_not_awaited()


def test_deadline_bounds_gate_and_session_read_without_inventing_release(active, monkeypatch):
    async def blocked(*args, **kwargs):
        await asyncio.Event().wait()
    value = replace(active, policy=AIHTTPPolicy(.02, 2, (), "https://testserver"))
    monkeypatch.setattr(app.state, "ai_search_runtime", value)
    with TestClient(app, base_url="https://testserver") as client:
        value.http_gate.check.side_effect = blocked
        result = client.post("/api/v1/ai-search/sessions", headers=HEADERS)
        assert result.status_code == 504
        assert result.json()["detail"] == "AI_REQUEST_TIMEOUT_RETRY_SAME_OPERATION"
        value.http_gate.check.side_effect = None
        token, _ = value.guests.issue()
        value.sessions.get.side_effect = blocked
        result = client.get(f"/api/v1/ai-search/sessions/{uuid4()}", headers={"Cookie": "ai_search_guest=" + token})
        assert result.status_code == 504 and result.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("error,code,delay", [(AIAttemptRejected("ATTEMPT_LIMIT", 17), "ATTEMPT_LIMIT", "17"),
    (QuotaError("QUOTA_EXHAUSTED", 864), "QUOTA_EXHAUSTED", "864")])
def test_retry_after_and_configuration_capabilities_are_explicit(active, error, code, delay):
    active.http_gate.check.side_effect = error
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post("/api/v1/ai-search/sessions", headers=HEADERS)
        assert response.status_code == 429 and response.json()["detail"] == code
        assert response.headers["retry-after"] == delay
        # Advertisement is not health; a broken injected gate doesn't change
        # configuration or trigger provider/DB health probes.
        assert client.get("/api/v1/ai-search/capabilities").json()["text"] is True


@pytest.mark.parametrize("seconds,maximum,proxies", [(0, 2, ()), (float("nan"), 2, ()),
    (1, 0, ()), (1, 2, ("0.0.0.0/0",)), (1, 2, ("::/0",))])
def test_policy_requires_explicit_budgets_and_bounded_proxy_trust(seconds, maximum, proxies):
    with pytest.raises(ValueError):
        AIHTTPPolicy(seconds, maximum, proxies, "https://testserver")


def test_server_access_logger_drops_raw_private_url_but_keeps_ordinary_requests(caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.access")
    access = logging.getLogger("uvicorn.access")
    for path in ("/api/v1/ai-search/sessions/PRIVATE_SENTINEL?text=PRIVATE_SENTINEL", "/api/v1/listings"):
        access.info('%s - "%s %s HTTP/%s" %d', "127.0.0.1:1", "GET", path, "1.1", 404)
    assert "PRIVATE_SENTINEL" not in caplog.text
    assert "/api/v1/listings" in caplog.text


@pytest.mark.asyncio
async def test_deadline_covers_slow_stream_before_body_validation(active, monkeypatch):
    monkeypatch.setattr(app.state, "ai_search_runtime", replace(active, policy=AIHTTPPolicy(.02, 2, (), "https://testserver")))
    async def slow_body():
        yield b"{"
        await asyncio.Event().wait()
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver") as client:
        response = await client.post("/api/v1/ai-search/query", content=slow_body(), headers=HEADERS)
        assert response.status_code == 504
    active.sessions.create.assert_not_awaited()


def test_late_synchronous_result_is_rejected_and_not_claimed_within_deadline(active, monkeypatch):
    monkeypatch.setattr(app.state, "ai_search_runtime", replace(active, policy=AIHTTPPolicy(.02, 2, (), "https://testserver")))
    def late(*args):
        time.sleep(.04)
        return {"late": True}
    active.sessions.get.side_effect = late
    token, _ = active.guests.issue()
    with TestClient(app, base_url="https://testserver") as client:
        response = client.get(f"/api/v1/ai-search/sessions/{uuid4()}", headers={"Cookie": "ai_search_guest=" + token})
        assert response.status_code == 504
        assert "late" not in response.text


def test_https_guest_origin_survives_tls_termination_with_internal_http_scope(active):
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post("/api/v1/ai-search/sessions", headers=HEADERS)
        assert response.status_code == 200
        assert "secure" in response.headers["set-cookie"].lower()
        token, _ = active.guests.issue()
        response = client.get(f"/api/v1/ai-search/sessions/{uuid4()}", headers={
            "Cookie": "ai_search_guest=" + token, "Sec-Fetch-Site": "same-origin"})
        assert response.status_code == 200
    with TestClient(app, base_url="https://foreign-host.invalid") as client:
        response = client.post("/api/v1/ai-search/sessions", headers=HEADERS)
        assert response.status_code == 403


@pytest.mark.parametrize("origin", ["http://public.invalid", "https://testserver/private", "https://testserver?secret=x"])
def test_guest_origin_policy_rejects_unsafe_or_non_origin_values(origin):
    with pytest.raises(ValueError):
        AIHTTPPolicy(1, 2, (), origin)
