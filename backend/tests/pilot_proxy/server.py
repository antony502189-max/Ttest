"""Offline HTTP fixture, not an activatable provider/SQL implementation."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.ai_http_policy import AIHTTPPolicy
from app.services.ai_operating_limits import OperatingHTTPGate
from app.services.ai_search_attempts import AIAttemptRejected
from app.services.rate_limit import RedisRateLimiter
from pilot.surface import allowed

app = FastAPI(docs_url=None, openapi_url=None, redoc_url=None)
policy = AIHTTPPolicy(20, 3, ("172.30.41.2/32",), "https://app.112233.es")
gate = OperatingHTTPGate(RedisRateLimiter("redis://redis:6379/0"))
operations = {}
unexpected = []


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def fixture(path: str, request: Request):
    if not allowed(request.method, "/"+path):
        unexpected.append(path)
        return JSONResponse({"reached_unexpected_handler": path}, 599)
    address = policy.address(request)
    if path.endswith("/identity"):
        try:
            await gate.check("ai-guest-issue:"+address)
        except AIAttemptRejected:
            return JSONResponse({"limited":True,"address":address},429)
        result = JSONResponse({"ready":True,"address":address})
        result.set_cookie("ai_search_guest","fixture",secure=True,httponly=True,samesite="strict",path="/api/v1/ai-search")
        return result
    if path.endswith("/query"):
        body = await request.json()
        key = body["idempotency_key"]
        operations.setdefault(key, {"status":"succeeded","result_ref":key,"count":0})
        return JSONResponse({"operation":operations[key],"mock_calls":len(operations)})
    return JSONResponse({"address":address,"authorization_absent":"authorization" not in request.headers,
        "forwarded_absent":not request.headers.get("x-forwarded-for"),"unexpected_handlers":unexpected,"mock_calls":len(operations)})
