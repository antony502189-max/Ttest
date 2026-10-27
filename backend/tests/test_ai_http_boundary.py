import pytest
from fastapi.testclient import TestClient

from app.main import app, exclude_private_ai_telemetry
from app.services.ai_guest_tokens import GuestPolicy, GuestTokens, InvalidGuestToken


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
