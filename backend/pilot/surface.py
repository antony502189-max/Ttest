"""Pilot-only ASGI surface, with no marketplace/auth/payment routers."""
import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
GET = (r"capabilities", r"quota", rf"sessions/{UUID}", rf"operations/{UUID}", rf"results/{UUID}")
POST = (r"identity", r"sessions", r"query", r"voice", rf"sessions/{UUID}/(?:reset|close|cards|map)", rf"results/{UUID}/(?:cards|map)")


def allowed(method, path):
    if method == "GET" and path == "/api/v1/private-demo/status":
        return True
    prefix = "/api/v1/ai-search/"
    if not path.startswith(prefix):
        return False
    return any(re.fullmatch(pattern, path[len(prefix):]) for pattern in (GET if method == "GET" else POST if method == "POST" else ()))


def minimal_app():
    from app.api.v1.ai_search import router
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(router, prefix="/api/v1")

    @app.get('/private-metrics',include_in_schema=False)
    async def private_metrics():
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        from starlette.responses import Response
        return Response(generate_latest(),headers={'Content-Type':CONTENT_TYPE_LATEST,'Cache-Control':'no-store'})

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.url.path=='/private-metrics':
            if request.method=='GET' and request.client and request.client.host in {'127.0.0.1','::1'}:
                return await call_next(request)
            return JSONResponse({'detail':'PILOT_ROUTE_DENIED'},404,headers={'Cache-Control':'no-store'})
        if not allowed(request.method, request.url.path) or "authorization" in request.headers:
            return JSONResponse({"detail": "PILOT_ROUTE_DENIED"}, status_code=404, headers={"Cache-Control": "no-store"})
        return await call_next(request)
    return app
