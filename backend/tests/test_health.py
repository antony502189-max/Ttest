import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.main as main_module
from app.api.v1.auth import require_cookie_origin
from app.core.config import get_settings
from app.main import RATE_LIMITS, api_schema_enabled, app, rate_limit_client
from app.services.rate_limit import MemoryRateLimiter


def test_live_and_openapi_are_available() -> None:
    client = TestClient(app)
    response = client.get("/health/live", headers={"X-Request-ID": "test-request"})
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == "test-request"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert client.get("/api/openapi.json").status_code == 200


def test_api_health_aliases_are_available() -> None:
    client = TestClient(app)
    assert client.get("/api/health/live").json() == {"status": "ok"}


def test_production_disables_interactive_api_schema(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "production")
    assert not api_schema_enabled()


def test_sensitive_endpoints_have_rate_limits() -> None:
    assert ("POST", "/api/v1/uploads") in RATE_LIMITS
    assert ("POST", "/api/v1/messages") in RATE_LIMITS
    assert ("POST", "/api/v1/reports") in RATE_LIMITS
    assert ("POST", "/api/v1/auth/forgot-password") in RATE_LIMITS
    assert ("POST", "/api/v1/auth/refresh") in RATE_LIMITS


def test_rate_limiter_returns_retry_after() -> None:
    limiter = MemoryRateLimiter()
    first = asyncio.run(limiter.consume("test-rate-limit", limit=1, window_seconds=60))
    second = asyncio.run(limiter.consume("test-rate-limit", limit=1, window_seconds=60))
    assert first.allowed
    assert not second.allowed
    assert second.retry_after >= 1


def test_rate_limit_client_uses_sanitized_proxy_address() -> None:
    request = Request({
        "type": "http",
        "client": ("172.16.0.3", 12345),
        "headers": [
            (b"x-real-ip", b"198.51.100.10"),
            (b"x-forwarded-for", b"198.51.100.10"),
        ],
    })
    assert rate_limit_client(request) == "198.51.100.10"


def test_unsanitized_forwarded_chain_does_not_trust_attacker_prefix() -> None:
    request = Request({
        "type": "http",
        "client": ("172.16.0.3", 12345),
        "headers": [(b"x-forwarded-for", b"198.51.100.10, 172.16.0.3")],
    })
    assert rate_limit_client(request) == "172.16.0.3"


def test_rate_limiter_returns_429_from_middleware(monkeypatch) -> None:
    route = ("GET", "/health/live")
    RATE_LIMITS[route] = (1, 60)
    monkeypatch.setattr(main_module, "rate_limiter", MemoryRateLimiter())
    try:
        client = TestClient(app)
        assert client.get("/health/live").status_code == 200
        limited = client.get("/health/live")
        assert limited.status_code == 429
        assert limited.json()["code"] == "rate_limited"
        assert limited.headers["retry-after"]
    finally:
        RATE_LIMITS.pop(route, None)


def test_cookie_mutations_require_allowlisted_origin_in_production(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "production")
    request = Request({"type": "http", "headers": [(b"origin", b"https://example.invalid")]})
    with pytest.raises(HTTPException) as error:
        require_cookie_origin(request)
    assert error.value.status_code == 403
