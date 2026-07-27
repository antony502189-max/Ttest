from fastapi.testclient import TestClient

from app.main import RATE_LIMITS, _rate_attempts, app, consume_rate_limit


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


def test_rate_limiter_returns_retry_after() -> None:
    key = "test-rate-limit"
    _rate_attempts.pop(key, None)
    assert consume_rate_limit(key, limit=1, window_seconds=60, now=100.0) is None
    assert consume_rate_limit(key, limit=1, window_seconds=60, now=101.0) == 59
    _rate_attempts.pop(key, None)


def test_rate_limiter_returns_429_from_middleware() -> None:
    route = ("GET", "/health/live")
    RATE_LIMITS[route] = (1, 60)
    try:
        client = TestClient(app)
        assert client.get("/health/live").status_code == 200
        limited = client.get("/health/live")
        assert limited.status_code == 429
        assert limited.json()["code"] == "rate_limited"
        assert limited.headers["retry-after"]
    finally:
        RATE_LIMITS.pop(route, None)
        _rate_attempts.clear()
