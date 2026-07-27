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

AUTH_RATE_LIMIT = 10
AUTH_RATE_WINDOW_SECONDS = 60
_auth_attempts: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def request_id(request: Request, call_next):
    if request.method == "POST" and request.url.path in {"/api/v1/auth/login", "/api/v1/auth/register"}:
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{request.url.path}"
        attempts = _auth_attempts[key]
        now = monotonic()
        while attempts and attempts[0] <= now - AUTH_RATE_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= AUTH_RATE_LIMIT:
            return JSONResponse(status_code=429, content={"code": "rate_limited", "message": "Too many attempts"})
        attempts.append(now)
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
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
