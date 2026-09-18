import asyncio
from uuid import UUID

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.main as main_module
from app.api.v1.auth import require_cookie_origin
from app.core.config import Settings, get_settings
from app.main import RATE_LIMITS, REQUESTS, api_schema_enabled, app, rate_limit_client
from app.services.rate_limit import MemoryRateLimiter


def test_live_and_openapi_are_available() -> None:
    client = TestClient(app)
    response = client.get("/health/live", headers={"X-Request-ID": "test-request"})
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == "test-request"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert client.get("/api/openapi.json").status_code == 200


def test_api_health_aliases_are_available_and_not_cacheable() -> None:
    client = TestClient(app)
    response = client.get("/api/health/live")
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"


def test_invalid_request_id_is_replaced_with_generated_uuid() -> None:
    client = TestClient(app)
    response = client.get("/health/live", headers={"X-Request-ID": "invalid request id"})
    assert response.status_code == 200
    UUID(response.headers["x-request-id"])


def test_unmatched_api_404_uses_bounded_metric_route_and_no_store() -> None:
    client = TestClient(app)
    before = REQUESTS.labels("GET", "<unmatched>", "404")._value.get()

    first = client.get("/api/definitely-missing-a")
    second = client.get("/api/definitely-missing-b")

    assert first.status_code == second.status_code == 404
    assert first.headers["cache-control"] == "no-store"
    assert first.headers["x-request-id"]
    assert first.headers["x-content-type-options"] == "nosniff"
    assert REQUESTS.labels("GET", "<unmatched>", "404")._value.get() == before + 2


def test_unhandled_api_error_uses_common_http_finalization() -> None:
    path = "/api/v1/test-unhandled-http-contour"

    async def fail():
        raise RuntimeError("forced test failure")

    app.add_api_route(path, fail, methods=["GET"], include_in_schema=False)
    before = REQUESTS.labels("GET", path, "500")._value.get()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(path, headers={"X-Request-ID": "unhandled-test"})
    finally:
        app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", None) != path]

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Internal server error",
        "fieldErrors": {},
    }
    assert response.headers["x-request-id"] == "unhandled-test"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert REQUESTS.labels("GET", path, "500")._value.get() == before + 1


def test_production_disables_interactive_api_schema(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "production")
    assert not api_schema_enabled()


def test_sentry_uses_explicit_release_without_pii(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    release = "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setattr(
        main_module,
        "settings",
        Settings(
            app_env="production",
            sentry_dsn="https://public@example.invalid/1",
            sentry_release=release,
            sentry_traces_sample_rate=0.05,
        ),
    )
    monkeypatch.setattr(main_module.sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    main_module.configure_sentry()

    assert calls == [
        {
            "dsn": "https://public@example.invalid/1",
            "environment": "production",
            "release": release,
            "traces_sample_rate": 0.05,
            "send_default_pii": False,
        }
    ]


def test_sensitive_endpoints_have_rate_limits() -> None:
    assert ("POST", "/api/v1/uploads") in RATE_LIMITS
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
    before = REQUESTS.labels("GET", "/health/live", "429")._value.get()
    try:
        client = TestClient(app)
        assert client.get("/health/live").status_code == 200
        limited = client.get("/health/live")
        assert limited.status_code == 429
        assert limited.json()["code"] == "rate_limited"
        assert limited.headers["retry-after"]
        assert limited.headers["cache-control"] == "no-store"
        assert REQUESTS.labels("GET", "/health/live", "429")._value.get() == before + 1
    finally:
        RATE_LIMITS.pop(route, None)


def test_readiness_maps_s3_dependency_failure_to_503(monkeypatch) -> None:
    class Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _statement):
            return None

    class Engine:
        def connect(self):
            return Connection()

    class Limiter:
        async def ready(self):
            return True

    class Storage:
        def healthcheck(self):
            raise ClientError(
                {"Error": {"Code": "503", "Message": "storage unavailable"}},
                "HeadBucket",
            )

    monkeypatch.setattr(main_module, "engine", Engine())
    monkeypatch.setattr(main_module, "rate_limiter", Limiter())
    monkeypatch.setattr(main_module, "get_storage", lambda: Storage())

    with pytest.raises(HTTPException) as error:
        asyncio.run(main_module.ready())

    assert error.value.status_code == 503
    assert error.value.detail == "A required dependency is not ready"


def test_cookie_mutations_require_allowlisted_origin_in_production(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "production")
    request = Request({"type": "http", "headers": [(b"origin", b"https://example.invalid")]})
    with pytest.raises(HTTPException) as error:
        require_cookie_origin(request)
    assert error.value.status_code == 403
