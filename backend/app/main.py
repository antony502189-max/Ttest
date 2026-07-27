from collections import defaultdict, deque
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from .db.session import engine

app = FastAPI(title="112233.es API", version="1.0.0", openapi_url="/api/openapi.json", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

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
_rate_attempts: dict[str, deque[float]] = defaultdict(deque)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
}


def consume_rate_limit(key: str, limit: int, window_seconds: int, now: float | None = None) -> int | None:
    """Returns retry seconds when a request exceeds its fixed window, otherwise None."""
    current = monotonic() if now is None else now
    attempts = _rate_attempts[key]
    while attempts and attempts[0] <= current - window_seconds:
        attempts.popleft()
    if len(attempts) >= limit:
        return max(1, int(window_seconds - (current - attempts[0])))
    attempts.append(current)
    return None


@app.middleware("http")
async def request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    rate = RATE_LIMITS.get((request.method, request.url.path))
    if rate:
        client = request.client.host if request.client else "unknown"
        retry_after = consume_rate_limit(f"{client}:{request.method}:{request.url.path}", *rate)
        if retry_after is not None:
            return JSONResponse(
                status_code=429,
                content={"code": "rate_limited", "message": "Too many attempts", "fieldErrors": {}},
                headers={"Retry-After": str(retry_after), "X-Request-ID": request_id, **SECURITY_HEADERS},
            )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers.update(SECURITY_HEADERS)
    return response


@app.exception_handler(Exception)
async def internal_error(_: Request, exc: Exception):
    return JSONResponse(
        status_code=500, content={"code": "internal_error", "message": "Internal server error", "fieldErrors": {}}
    )


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503, "Database is not ready")
    return {"status": "ok"}


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
