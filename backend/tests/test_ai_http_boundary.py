from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.ai_search import AISearchRuntime
from app.main import app, exclude_private_ai_telemetry
from app.services.ai_guest_tokens import GuestPolicy, GuestTokens, InvalidGuestToken
from app.services.ai_http_policy import AIHTTPPolicy


def test_signed_guest_identity_is_server_minted_bounded_and_policy_bound():
    tokens = GuestTokens(key=b"synthetic-guest-key-not-secret-32", policy=GuestPolicy(ttl_seconds=60))
    token, subject = tokens.issue(now=100)
    assert tokens.read(token, now=159) == subject
    for bad in (token + "x", "client-chosen-uuid", "a.b.c", "x" * 1025):
        with pytest.raises(InvalidGuestToken):
            tokens.read(bad, now=101)
    for instant in (99, 160):
        with pytest.raises(InvalidGuestToken):
            tokens.read(token, now=instant)
    with pytest.raises(InvalidGuestToken):
        GuestTokens(key=tokens.key, policy=GuestPolicy(ttl_seconds=61)).read(token, now=101)
    assert "127.0.0.1" not in tokens.ip_key("127.0.0.1", purpose="ai-http")


def test_http_api_is_disabled_without_database_provider_or_runtime():
    with TestClient(app) as client:
        assert client.get("/api/v1/ai-search/capabilities").json() == {"text": False, "map": False, "voice": False, "saved_searches": False}
        result = client.post("/api/v1/ai-search/sessions")
        assert result.status_code == 503 and result.json() == {"detail": "AI_SEARCH_DISABLED"}
        assert result.headers["cache-control"] == "no-store"


def test_ai_telemetry_drops_whole_event_and_transaction_but_preserves_other_routes():
    for event in ({"tags": {"ai_private": True}, "extra": {"text": "PRIVATE"}},
                  {"request": {"url": "https://example.invalid/api/v1/ai-search/query", "data": "PRIVATE"}},
                  {"type": "transaction", "request": {"url": "https://example.invalid/api/v1/ai-search/sessions"}},
                  {"request": {"url": "https://[malformed/api/v1/ai-search/query", "data": "PRIVATE"}}):
        assert exclude_private_ai_telemetry(event, {}) is None
    other = {"request": {"url": "https://example.invalid/api/v1/listings"}}
    assert exclude_private_ai_telemetry(other, {}) is other


def test_private_validation_never_exports_body_keys_or_values(monkeypatch, caplog):
    sessions = SimpleNamespace()
    guests = GuestTokens(key=b"synthetic-guest-key-not-secret-32", policy=GuestPolicy(ttl_seconds=60))
    active = AISearchRuntime(sessions, SimpleNamespace(sessions=sessions), SimpleNamespace(sessions=sessions),
                             guests, SimpleNamespace(check=AsyncMock()), frozenset({"https://testserver"}), 4096, AIHTTPPolicy(10, 5, ()))
    monkeypatch.setattr(app.state, "ai_search_runtime", active, raising=False)
    token, _ = guests.issue()
    headers = {"Origin": "https://testserver", "X-AI-Request": "1", "Cookie": "ai_search_guest=" + token}
    with TestClient(app, base_url="https://testserver") as client:
        for payload in ({"PRIVATE_BODY_KEY": "PRIVATE_BODY_VALUE"}, {"text": "PRIVATE_BODY_VALUE"}):
            response = client.post("/api/v1/ai-search/query", json=payload, headers=headers)
            assert response.status_code == 422
            assert response.json() == {"detail": "AI_REQUEST_INVALID"}
            assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE_BODY" not in caplog.text
    assert not any(record.message == "request_validation_failed" for record in caplog.records)


def test_session_creation_accepts_only_explicit_typed_mode_and_legacy_empty_body(monkeypatch):
    from app.schemas.ai_search_intent import SessionCreate
    sessions = SimpleNamespace(create=AsyncMock(return_value={"ok": True}))
    guests = GuestTokens(key=b"synthetic-guest-key-not-secret-32", policy=GuestPolicy(ttl_seconds=60))
    active = AISearchRuntime(sessions, SimpleNamespace(sessions=sessions), SimpleNamespace(sessions=sessions),
                             guests, SimpleNamespace(check=AsyncMock()), frozenset({"https://testserver"}), 4096, AIHTTPPolicy(10, 5, ()))
    monkeypatch.setattr(app.state, "ai_search_runtime", active, raising=False)
    token, owner = guests.issue()
    headers = {"Origin": "https://testserver", "X-AI-Request": "1", "Cookie": "ai_search_guest=" + token}
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post("/api/v1/ai-search/sessions", headers=headers)
        assert response.status_code == 200
        sessions.create.assert_awaited_with(owner, None, max_active=5)
        for mode in ("long", "holiday"):
            assert client.post("/api/v1/ai-search/sessions", json={"rental_mode": mode}, headers=headers).status_code == 200
            sessions.create.assert_awaited_with(owner, SessionCreate(rental_mode=mode), max_active=5)
        calls = sessions.create.await_count
        for body in ({"rental_mode": "vivienda"}, {"rental_mode": False}, {"criteria": {}}, {"intent_hash": "x"}, {"occupants": 2}):
            response = client.post("/api/v1/ai-search/sessions", json=body, headers=headers)
            assert response.status_code == 422 and response.json() == {"detail": "AI_REQUEST_INVALID"}
        assert sessions.create.await_count == calls
