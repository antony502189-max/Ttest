"""Real Chromium same-origin guest cookies and cross-site rejection, without a database."""
import asyncio
import os
import socket
import threading
import time
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.v1.ai_search import AISearchRuntime, router
from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
from app.services.ai_http_policy import AIHTTPPolicy

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("AI_HTTP_BROWSER_TEST") != "1",
    reason="explicit loopback Chromium opt-in required")]


def test_browser_guest_cookie_roundtrip_preflight_and_external_site_rejection():
    from playwright.sync_api import sync_playwright
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    api_origin = f"http://127.0.0.1:{port}"
    external_origin = f"http://localhost:{port}"
    fixture = FastAPI()
    fixture.include_router(router, prefix="/api/v1")
    fixture.add_middleware(CORSMiddleware, allow_origins=[api_origin, external_origin], allow_credentials=True,
        allow_methods=["GET", "POST"], allow_headers=["X-AI-Request", "Content-Type"])
    @fixture.get("/browser-fixture")
    def document():
        return HTMLResponse("<!doctype html><title>Local AI contract</title>")
    class Sessions:
        async def create(self, owner, seed=None, *, max_active):
            return {"session_id": str(uuid4()), "owner": str(owner.id)}
        async def get(self, owner, session_id):
            return {"session_id": str(session_id), "owner": str(owner.id)}
    class Gate:
        async def check(self, key):
            pass
    sessions = Sessions()
    fixture.state.ai_search_runtime = AISearchRuntime(sessions, SimpleNamespace(sessions=sessions),
        SimpleNamespace(sessions=sessions), GuestTokens(key=b"synthetic-guest-key-not-secret-32",
        policy=GuestPolicy(ttl_seconds=600)), Gate(), frozenset({api_origin, external_origin}), 4096,
        AIHTTPPolicy(2, 2, ()))
    server = uvicorn.Server(uvicorn.Config(fixture, log_level="critical", access_log=False, proxy_headers=False))
    thread = threading.Thread(target=lambda: asyncio.run(server.serve(sockets=[listener])), daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.02)
        assert server.started
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.getenv("AI_HTTP_CHROMIUM_EXECUTABLE"))
            try:
                context = browser.new_context()
                context.route("**/*", lambda route: route.continue_() if urlsplit(route.request.url).hostname
                    in {"127.0.0.1", "localhost"} else route.abort())
                page = context.new_page()
                page.goto(api_origin + "/browser-fixture")
                created = page.evaluate("""async () => {
                    const r = await fetch('/api/v1/ai-search/sessions', {method:'POST', credentials:'include',
                        headers:{'X-AI-Request':'1'}});
                    return {status:r.status, body:await r.json()};
                }""")
                assert created["status"] == 200
                cookie = next(value for value in context.cookies() if value["name"] == "ai_search_guest")
                assert cookie["secure"] and cookie["httpOnly"] and cookie["sameSite"] == "Strict"
                result = page.evaluate("""async sid => {
                    const r = await fetch('/api/v1/ai-search/sessions/'+sid, {credentials:'include'});
                    return {status:r.status, body:await r.json()};
                }""", created["body"]["session_id"])
                assert result["status"] == 200 and result["body"]["owner"] == created["body"]["owner"]
                assert page.evaluate("document.cookie") == ""
                # A real other-site document performs OPTIONS and POST. CORS
                # permits the explicit AI header; the guest boundary rejects
                # the operation without minting a cross-site cookie.
                page.goto(external_origin + "/browser-fixture")
                observed = []
                page.on("response", lambda response: observed.append((response.request.method, response.status)))
                denied = page.evaluate("""async origin => {
                    const r = await fetch(origin+'/api/v1/ai-search/sessions', {method:'POST', credentials:'include',
                        headers:{'X-AI-Request':'1', 'Content-Type':'application/json'}, body:'{}'});
                    return {status:r.status, body:await r.json()};
                }""", api_origin)
                assert denied == {"status": 403, "body": {"detail": "AI_GUEST_SAME_ORIGIN_REQUIRED"}}
                assert ("POST", 403) in observed
                assert len([value for value in context.cookies() if value["name"] == "ai_search_guest"]) == 1
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive()
