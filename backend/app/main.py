from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from ipaddress import ip_address
from time import perf_counter
from uuid import uuid4

import sentry_sdk  # type: ignore[import-not-found]
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .api.public_pages import router as public_pages_router
from .api.v1.admin import router as admin_router
from .api.v1.auth import router as auth_router
from .api.v1.favorites import router as favorites_router
from .api.v1.listings import router as listings_router
from .api.v1.notifications import router as notifications_router
from .api.v1.reports import router as reports_router
from .api.v1.saved_searches import router as saved_searches_router
from .api.v1.search_history import router as search_history_router
from .api.v1.uploads import router as uploads_router
from .api.v1.users import router as users_router
from .core.config import get_settings
from .core.observability import REQUEST_DURATION, REQUESTS, UNHANDLED_ERRORS, configure_logging, metrics_payload
from .db.session import SessionLocal, engine
from .services.listing_lifecycle import expire_due_listings
from .services.rate_limit import ResilientRateLimiter
from .storage import get_storage

settings = get_settings()
configure_logging()


def configure_sentry() -> None:
    """Initialize Sentry without widening captured production data."""
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            release=settings.sentry_release or None,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=False,
        )


configure_sentry()
logger = logging.getLogger(__name__)
rate_limiter = ResilientRateLimiter()
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
LISTING_LIFECYCLE_INTERVAL_SECONDS = 60


def api_schema_enabled() -> bool:
    """Keep interactive API metadata out of the public production surface."""
    return not settings.is_production


RATE_LIMITS: dict[tuple[str, str], tuple[int, int]] = {
    ("POST", "/api/v1/auth/login"): (10, 60),
    ("POST", "/api/v1/auth/register"): (10, 60),
    ("POST", "/api/v1/auth/google"): (10, 60),
    ("POST", "/api/v1/auth/refresh"): (10, 60),
    ("POST", "/api/v1/auth/forgot-password"): (5, 60),
    ("POST", "/api/v1/auth/reset-password"): (10, 60),
    ("POST", "/api/v1/auth/email-verification/request"): (5, 3600),
    ("POST", "/api/v1/auth/email-verification/confirm"): (10, 60),
    ("POST", "/api/v1/reports"): (10, 60),
    ("POST", "/api/v1/uploads"): (20, 60),
    ("POST", "/api/v1/listings"): (20, 60),
    ("POST", "/api/v1/account/import-guest-state"): (5, 60),
    ("DELETE", "/api/v1/discarded-listings"): (60, 60),
}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=()",
    "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def rate_limit_rule(method: str, path: str) -> tuple[str, int, int] | None:
    """Return a stable bucket name and its budget for one request.

    Dynamic UUID path components must never become part of the Redis key;
    otherwise callers can rotate identifiers to create unlimited buckets.
    """
    direct = RATE_LIMITS.get((method, path))
    if direct:
        return path, *direct
    if method in {"PUT", "DELETE"} and path.startswith("/api/v1/favorites/"):
        return "/api/v1/favorites/{listing_id}", 60, 60
    if method in {"PUT", "DELETE"} and path.startswith("/api/v1/discarded-listings/"):
        return "/api/v1/discarded-listings/{listing_id}", 60, 60
    return None


def rate_rule(method: str, path: str) -> tuple[int, int] | None:
    rule = rate_limit_rule(method, path)
    return (rule[1], rule[2]) if rule else None


def _normalized_ip(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return ip_address(candidate).compressed
    except ValueError:
        return None


def rate_limit_client(request: Request) -> str:
    # The public backend is reachable only through Traefik and the frontend
    # nginx proxy. nginx sanitizes X-Real-IP/X-Forwarded-For to one validated
    # client hop before forwarding the request here.
    real_ip = _normalized_ip(request.headers.get("x-real-ip", ""))
    if real_ip:
        return real_ip
    forwarded = [part for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
    for part in reversed(forwarded):
        candidate = _normalized_ip(part)
        if candidate:
            return candidate
    if request.client:
        direct = _normalized_ip(request.client.host)
        if direct:
            return direct
    return "unknown"


def request_id_for(request: Request) -> str:
    candidate = request.headers.get("X-Request-ID", "")
    return candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else str(uuid4())


async def listing_lifecycle_loop() -> None:
    """Keep persisted internal listing state aligned with expiry visibility."""
    while True:
        try:
            async with SessionLocal() as session:
                expired = await expire_due_listings(session)
            if expired:
                logger.info("listing_lifecycle_expired", extra={"count": expired})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("listing_lifecycle_iteration_failed")
        await asyncio.sleep(LISTING_LIFECYCLE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime()
    logger.info("application_started", extra={"app_env": settings.app_env})
    lifecycle_task = asyncio.create_task(listing_lifecycle_loop())
    try:
        yield
    finally:
        lifecycle_task.cancel()
        try:
            await lifecycle_task
        except asyncio.CancelledError:
            pass
        await rate_limiter.close()
        await engine.dispose()
        logger.info("application_stopped")


app = FastAPI(
    title="112233.es API",
    version="1.1.0",
    openapi_url="/api/openapi.json" if api_schema_enabled() else None,
    docs_url="/api/docs" if api_schema_enabled() else None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request_id_for(request)
    request.state.request_id = request_id
    started = perf_counter()
    rate = rate_limit_rule(request.method, request.url.path)
    if rate:
        bucket, limit, window_seconds = rate
        client = rate_limit_client(request)
        result = await rate_limiter.consume(
            f"ttest:rate:{client}:{request.method}:{bucket}",
            limit,
            window_seconds,
        )
        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content={"code": "rate_limited", "message": "Too many attempts", "fieldErrors": {}},
                headers={
                    "Retry-After": str(result.retry_after),
                    "X-Request-ID": request_id,
                    "Cache-Control": "no-store",
                    **SECURITY_HEADERS,
                },
            )

    response = await call_next(request)
    if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    duration = perf_counter() - started
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    REQUESTS.labels(request.method, route_path, str(response.status_code)).inc()
    REQUEST_DURATION.labels(request.method, route_path).observe(duration)
    response.headers["X-Request-ID"] = request_id
    response.headers.update(SECURITY_HEADERS)
    logger.info(
        "http_request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration * 1000, 2),
        },
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    """Keep machine-readable API errors at the top level without changing legacy errors."""
    content = exc.detail if isinstance(exc.detail, dict) and "code" in exc.detail else {"detail": exc.detail}
    request_id = getattr(request.state, "request_id", None) or request_id_for(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers={**(exc.headers or {}), "X-Request-ID": request_id, **SECURITY_HEADERS},
    )


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or request_id_for(request)
    UNHANDLED_ERRORS.labels(type(exc).__name__).inc()
    logger.exception(
        "unhandled_request_error",
        extra={"request_id": request_id, "method": request.method, "path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "message": "Internal server error", "fieldErrors": {}},
        headers={"X-Request-ID": request_id, **SECURITY_HEADERS},
    )


@app.get("/api/health/live", include_in_schema=False)
@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/api/health/ready", include_in_schema=False)
@app.get("/health/ready")
async def ready():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        if not await rate_limiter.ready():
            raise RuntimeError("Redis is not ready")
        await asyncio.to_thread(get_storage().healthcheck)
    except (SQLAlchemyError, OSError, RuntimeError) as exc:
        raise HTTPException(503, "A required dependency is not ready") from exc
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    if not settings.metrics_enabled:
        raise HTTPException(404, "Not found")
    payload, content_type = metrics_payload()
    return Response(content=payload, media_type=content_type)


app.include_router(public_pages_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(favorites_router, prefix="/api/v1")
app.include_router(listings_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(saved_searches_router, prefix="/api/v1")
app.include_router(search_history_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")
