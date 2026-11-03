"""Closed LIVE proxy authorization, separate from public release pairing.

The loopback mTLS nginx proxy injects a private random header. It must overwrite
client-supplied values, and the backend must have no host-published ports.
No secret is ever sent to the browser or returned by lab-runtime.
"""
import hmac
import re
from pathlib import Path

from starlette.responses import JSONResponse

from lab.runtime_contract import ATTESTATION, ai_path

HEADER = b"x-ai-lab-access"


def load_proxy_secret(path: Path):
    # Same read-only include is consumed by nginx and this factory. No generic
    # nginx directives, browser variables or arbitrary token formats accepted.
    raw = path.read_bytes()
    match = re.fullmatch(rb'proxy_set_header X-AI-Lab-Access "([0-9a-f]{64})";\s*', raw)
    if match is None:
        raise RuntimeError("CLOSED_UI_PROXY_ACCESS_REQUIRED")
    return match[1]


class ClosedSmokeAccess:
    def __init__(self, app, *, secret: bytes):
        if not re.fullmatch(rb"[0-9a-f]{64}", secret):
            raise RuntimeError("CLOSED_UI_PROXY_ACCESS_REQUIRED")
        self.app, self.secret = app, secret

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"} or not ai_path(scope.get("path", "")):
            return await self.app(scope, receive, send)
        # Public metadata is explicitly not authentication. Possession/replay of
        # every returned value must still not grant access to a closed smoke.
        if scope["type"] == "http" and scope["path"] == ATTESTATION and scope["method"] == "GET":
            return await self.app(scope, receive, send)
        values = [v for k, v in scope.get("headers", []) if k.lower() == HEADER]
        if len(values) != 1 or not hmac.compare_digest(values[0], self.secret):
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            return await JSONResponse({"detail": "CLOSED_UI_ACCESS_DENIED"}, 403,
                                      headers={"Cache-Control": "no-store"})(scope, receive, send)
        return await self.app(scope, receive, send)
