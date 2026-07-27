from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .api.v1.admin import router as admin_router
from .api.v1.auth import router as auth_router
from .api.v1.favorites import router as favorites_router
from .api.v1.listings import router as listings_router
from .api.v1.messages import router as messages_router
from .api.v1.reports import router as reports_router
from .api.v1.saved_searches import router as saved_searches_router
from .api.v1.search_history import router as search_history_router
from .api.v1.uploads import router as uploads_router
from .api.v1.users import router as users_router
from .core.config import get_settings
from .core.observability import (
    REQUEST_DURATION,
    REQUESTS,
    UNHANDLED_ERRORS,
    configure_logging,
    metrics_payload,
)
from .db.session import engine
from .services.rate_limit import ResilientRateLimiter

configure_logging()
logger = logging.getLogger(__name__)
rate_limiter = ResilientRateLimiter()

RATE_LIMITS: dict[tuple[str, str], tuple[int, int]] = {
    ("POST", "/api/v1/auth/login"): (10, 60),
    ("POST", "/api/v1/auth/register"): (10, 60),
    ("POST", "/api/v1/auth/google"): (10, 60),
    ("POST", "/api/v1/auth/forgot-password"): (5, 60),
    ("POST", "/api/v1/auth/reset-password"): (10, 60),
    ("POST", "/api/v1/auth/request-email-verification"): (5, 60),
    ("POST", "/api/v1/auth/verify-email"): (10, 60),
    ("POST", "/api/v1/messages"): (30, 60),
    ("POST", "/api/v1/reports"): (10, 60),
    ("POST", "/api/v1/uploads"): (20, 60),
    ("POST", "/api/v1/listings"): (20, 60),
}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    # Public media is consumed by the GitHub Pages frontend on another origin.
    "Cross-Origin-Resource-Policy": "cross-origin",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings().validate_runtime()
    logger.info("application_started", extra={"app_env": get_settings().app_env})
    try:
        yield
    finally:
        await rate_limiter.close()
        await engine.dispose()
        logger.info("application_stopped")


app = FastAPI(
    title="112233.es API",
    version="1.1.0",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    started = perf_counter()
    rate = RATE_LIMITS.get((request.method, request.url.path))
    if rate:
        client = request.client.host if request.client else "unknown"
        result = await rate_limiter.consume(f"ttest:rate:{client}:{request.method}:{request.url.path}", *rate)
        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content={"code": "rate_limited", "message": "Too many attempts", "fieldErrors": {}},
                headers={"Retry-After": str(result.retry_after), "X-Request-ID": request_id, **SECURITY_HEADERS},
            )

    response = await call_next(request)
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


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID", "unknown")
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


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database is not ready") from exc
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    if not get_settings().metrics_enabled:
        raise HTTPException(404, "Not found")
    payload, content_type = metrics_payload()
    return Response(content=payload, media_type=content_type)


app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(favorites_router, prefix="/api/v1")
app.include_router(listings_router, prefix="/api/v1")
app.include_router(messages_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(saved_searches_router, prefix="/api/v1")
app.include_router(search_history_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")
