"""Lab-only backend attestation and per-request frontend/instance pairing.

Not an authentication mechanism. Prevents accidental mixed releases before any
session, quota reservation or model IO; normal app.main never installs it.
"""
import re
from dataclasses import dataclass
from uuid import uuid4

from starlette.responses import JSONResponse

PREFIX = "/api/v1/ai-search/"
ATTESTATION = PREFIX + "lab-runtime"
MODES = frozenset({"finite", "decision-transport-fixture", "closed-live-synthetic"})


@dataclass(frozen=True)
class LabRuntime:
    parser: str
    source: str
    transport: str
    instance: str

    @classmethod
    def create(cls, parser, source, transport):
        if parser not in MODES or not re.fullmatch(r"[0-9a-f]{40}", source or ""):
            raise RuntimeError("LAB_RUNTIME_SOURCE_OR_MODE_INVALID")
        if transport not in {"none", "mock", "https"} or (parser != "closed-live-synthetic" and transport == "https"):
            raise RuntimeError("LAB_RUNTIME_TRANSPORT_INVALID")
        return cls(parser, source, transport, str(uuid4()))

    def public(self):
        return {"schema": "ai-lab-runtime.v1", "parser": self.parser, "source": self.source,
                "instance": self.instance, "provider_transport": self.transport}

    def headers(self):
        return {"X-AI-Lab-Mode": self.parser, "X-AI-Lab-Source": self.source, "X-AI-Lab-Instance": self.instance}


class RuntimePairing:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith(PREFIX):
            return await self.app(scope, receive, send)
        runtime = getattr(scope["app"].state, "ai_lab_runtime", None)
        if runtime is None:
            return await JSONResponse({"detail": "LAB_RUNTIME_UNAVAILABLE"}, 503,
                                      headers={"Cache-Control": "no-store"})(scope, receive, send)
        if scope["path"] == ATTESTATION and scope["method"] == "GET":
            return await JSONResponse(runtime.public(), headers={"Cache-Control": "no-store"})(scope, receive, send)
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        matched = all(headers.get(key.lower()) == value for key, value in runtime.headers().items())
        if not matched:
            if scope["path"] == PREFIX + "capabilities" and scope["method"] == "GET":
                return await JSONResponse(dict.fromkeys(("text", "map", "voice", "saved_searches"), False),
                                          headers={"Cache-Control": "no-store"})(scope, receive, send)
            return await JSONResponse({"detail": "LAB_RUNTIME_MISMATCH"}, 409,
                                      headers={"Cache-Control": "no-store"})(scope, receive, send)
        return await self.app(scope, receive, send)
