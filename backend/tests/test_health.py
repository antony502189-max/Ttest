import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.main as main_module
from app.api.v1.auth import require_cookie_origin
from app.core.config import get_settings
from app.main import RATE_LIMITS, app
from app.services.rate_limit import MemoryRateLimiter


def test_live_and_openapi_are_available() -> None:
    client = TestClient(app)
    response = client.get("/health/live", headers={"X-Request-ID": "test-request"})
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == "test-request"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert client.get("/api/openapi.json").status_code == 200


def test_sensitive_endpoints_have_rate_limits() -> None:
    assert ("POST", "/api/v1/uploads") in RATE_LIMITS
    assert ("POST", "/api/v1/messages") in RATE_LIMITS
    assert ("POST", "/api/v1/reports") in RATE_LIMITS
    assert ("POST", "/api/v1/auth/forgot-password") in RATE_LIMITS


@pytest.mark.asyncio
async def test_rate_limiter_returns_retry_after() -> None:
    limiter = MemoryRateLimiter()
    first = await limiter.consume("test-rate-limit", limit=1, window_seconds=60)
    second = await limiter.consume("test-rate-limit", limit=1, window_seconds=60)
    assert first.allowed is True
    assert second.allowed is False
    assert 1 <= second.retry_after <= 60


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
