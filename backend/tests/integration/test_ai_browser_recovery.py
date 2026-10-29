"""Actual Chromium HTTP cookies/Origin/CSRF, frontend and real PostGIS.

No ASGI forwarding or rewritten Cookie/Origin/Set-Cookie. Offline parser only.
"""
import asyncio
import os
import socket
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import test_ai_http
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, update

from app.api.v1.ai_search import router
from app.db.session import SessionLocal
from app.models.ai_search_session import AISearchSession

# Register the shared offline-parser/PostGIS runtime fixture in this module.
active = test_ai_http.active

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.getenv("AI_UI_DIST_PATH"),
    reason="explicit built local frontend required")]


@pytest.mark.parametrize("phase", ["create", "reset", "query", "guest-query"])
async def test_real_http_browser_recovers_without_stranded_session(active, monkeypatch, phase):
    from playwright.async_api import async_playwright, expect
    runtime, parser, _gate = active
    directory = Path(os.environ["AI_UI_DIST_PATH"]).resolve()
    assert (directory / "index.html").is_file()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    fixture = FastAPI()
    fixture.include_router(router, prefix="/api/v1")
    fixture.state.ai_search_runtime = replace(runtime, origins=frozenset({origin}),
        policy=replace(runtime.policy, guest_origin=origin, max_active_sessions=1))
    fixture.mount("/", StaticFiles(directory=directory, html=True))
    target = "finalize_patch" if phase == "query" else phase
    if phase != "guest-query":
        original = getattr(runtime.sessions, target)
        first = True
        async def lost_ack(*args, **kwargs):
            nonlocal first
            answer = await original(*args, **kwargs)
            if first:
                first = False
                if phase == "query":
                    async with SessionLocal.begin() as conn:
                        await conn.execute(update(AISearchSession).where(AISearchSession.id == args[1].session_id)
                            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
                raise OSError("synthetic acknowledgement loss after commit")
            return answer
        monkeypatch.setattr(runtime.sessions, target, lost_ack)
    server = uvicorn.Server(uvicorn.Config(fixture, log_level="critical", access_log=False, proxy_headers=False))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(.02)
        assert server.started
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                context = await browser.new_context()
                page = await context.new_page()
                requests = []
                page.on("request", lambda request: requests.append(request) if "/api/v1/ai-search/" in request.url else None)
                await page.add_init_script("localStorage.setItem('112233:language:v1','es'); localStorage.setItem('112233:mobile-onboarding:v1','done:refreshable')")
                await page.goto(origin + "/#/")
                await page.get_by_role("button", name="Escribir mi búsqueda").click()
                await page.locator("#ai-rental-mode").select_option("none")
                await page.locator("#ai-search-text").fill("Una habitación con mi perro")
                if phase == "guest-query":
                    # Bootstrap ownership, then corrupt it immediately before query.
                    await page.evaluate("fetch('/api/v1/ai-search/identity',{method:'POST',headers:{'X-AI-Request':'1'}})")
                search = page.get_by_role("button", name="Buscar habitaciones", exact=True)
                await search.click()
                if phase == "create":
                    await expect(page.get_by_text("No se pudo iniciar una nueva conversación.", exact=False)).to_be_visible()
                    await search.click()
                if phase == "query":
                    retry = page.get_by_role("button", name="Comprobar el mismo intento")
                    await expect(retry).to_be_enabled()
                    await retry.click()
                    await expect(retry).to_have_count(0)
                    await expect(page.get_by_role("button", name="Iniciar nueva conversación")).to_be_enabled()
                    assert parser.calls == 1
                else:
                    await expect(page.get_by_role("region", name="Resultados confirmados")).to_be_visible()
                cookies = await context.cookies()
                cookie = next(item for item in cookies if item["name"] == "ai_search_guest")
                assert cookie["path"] == "/api/v1/ai-search" and cookie["secure"] and cookie["httpOnly"]
                assert cookie["sameSite"] == "Strict" and await page.evaluate("document.cookie") == ""
                owner = runtime.guests.read(cookie["value"])
                if phase == "reset":
                    await page.locator("#ai-search-text").fill("Con balcón")
                    reset = page.get_by_role("button", name="Iniciar nueva conversación")
                    await reset.click()
                    await expect(page.get_by_text("No se pudo iniciar una nueva conversación.", exact=False)).to_be_visible()
                    await reset.click()
                    await expect(page.get_by_text("Nueva conversación lista.", exact=False)).to_be_visible()
                    await expect(page.locator("#ai-search-text")).to_have_value("Con balcón")
                if phase == "guest-query":
                    await context.add_cookies([{**cookie, "value": "forged"}])
                    await page.locator("#ai-search-text").fill("Mi borrador privado")
                    await page.get_by_role("button", name="Actualizar búsqueda", exact=True).click()
                    await expect(page.get_by_role("button", name="Iniciar nueva conversación")).to_be_enabled()
                    await expect(page.locator("#ai-search-text")).to_be_enabled()
                    await expect(page.locator("#ai-search-text")).to_have_value("Mi borrador privado")
                    assert not [item for item in await context.cookies() if item["name"] == "ai_search_guest"]
                    await page.get_by_role("button", name="Iniciar nueva conversación").click()
                    await expect(page.get_by_text("Nueva conversación lista.", exact=False)).to_be_visible()
                    renewed = next(item for item in await context.cookies() if item["name"] == "ai_search_guest")
                    assert renewed["value"] != cookie["value"]
                    assert runtime.guests.read(renewed["value"]).id != owner.id
                posts = [req for req in requests if req.method == "POST"]
                for request in posts:
                    headers = await request.all_headers()
                    assert headers["origin"] == origin and headers["x-ai-request"] == "1"
                    if not request.url.endswith("/identity"):
                        assert "ai_search_guest=" in headers.get("cookie", "")
                if phase in {"create", "reset", "query"}:
                    suffix = "/sessions" if phase == "create" else "/reset" if phase == "reset" else "/query"
                    attempts = [req.post_data_json for req in posts if req.url.endswith(suffix)]
                    assert len(attempts) == 2 and attempts[0] == attempts[1]
                async with SessionLocal() as conn:
                    count = await conn.scalar(select(func.count()).select_from(AISearchSession).where(
                        AISearchSession.subject_id == owner.id, AISearchSession.closed_at.is_(None),
                        AISearchSession.expires_at > datetime.now(UTC)))
                    assert count == (0 if phase == "query" else 1)
            finally:
                await browser.close()
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=5)
        listener.close()
