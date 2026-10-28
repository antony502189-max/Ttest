"""Actual HTTP+cookies+ownership+quota+PostGIS cards, with an offline parser."""
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text, update
from test_ai_verified_cards import setup

from app.api.v1.ai_search import AISearchRuntime
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_search_quota import AIUsageDay
from app.models.ai_search_session import AISearchSession
from app.schemas.ai_search_intent import IntentPatch
from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
from app.services.ai_http_policy import AIHTTPPolicy
from app.services.ai_search_attempts import AIAttemptRejected
from app.services.ai_search_execution import TextSearchExecution

pytestmark = pytest.mark.integration
HEADERS = {"Origin": "https://testserver", "X-AI-Request": "1"}


class Gate:
    reject = False
    async def check(self, _key):
        if self.reject:
            raise AIAttemptRejected("ABUSE_GATE_UNAVAILABLE")


class Parser:
    calls = 0
    async def parse(self, message, current):
        self.calls += 1
        return IntentPatch.model_validate_json(json.dumps({"schema_version": "ai-search.v1",
            "session_id": str(current.session_id), "expected_version": current.version,
            "set": {"pets": {"strength": "hard", "value": [{"species": "dog", "size": "small", "count": 1}]}}}))


@pytest_asyncio.fixture
async def active(monkeypatch):
    query, _, _, _, _ = await setup("long")
    parser, gate = Parser(), Gate()
    value = AISearchRuntime(query.sessions, query, TextSearchExecution(query.sessions, parser, Gate(), query),
        GuestTokens(key=b"synthetic-http-guest-key-not-secret32", policy=GuestPolicy(ttl_seconds=600)),
        gate, frozenset({"https://testserver"}), 131_072, AIHTTPPolicy(10, 5, (), "https://testserver"))
    monkeypatch.setattr(app.state, "ai_search_runtime", value, raising=False)
    return value, parser, gate


def message(session_id, version):
    return {"idempotency_key": str(uuid4()), "session_id": session_id, "expected_version": version,
            "text": "PRIVATE_SYNTHETIC_INPUT", "search": {"limit": 1}}


async def test_guest_cookie_three_messages_replay_reset_paging_and_owner_isolation(active):
    _, parser, _ = active
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers=HEADERS) as first, AsyncClient(
        transport=ASGITransport(app), base_url="https://testserver", headers=HEADERS) as other:
        created = await first.post("/api/v1/ai-search/sessions")
        assert created.status_code == 200, created.text
        cookie = created.headers["set-cookie"].lower()
        assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
        sid = created.json()["intent"]["session_id"]
        untouched = await first.get("/api/v1/ai-search/quota")
        assert untouched.status_code == 200 and untouched.json()["remaining"] == 3
        initial = message(sid, 0)
        result = await first.post("/api/v1/ai-search/query", json=initial)
        assert result.status_code == 200, result.text
        answer = result.json()
        assert answer["operation"]["used"] == 1 and answer["operation"]["limit"] == 3
        assert answer["cards"]["cards"]["total"] == 3 and answer["operation"]["status"] == "succeeded"
        for version in (1, 2):
            response = await first.post("/api/v1/ai-search/query", json=message(sid, version))
            assert response.status_code == 200 and response.json()["operation"]["status"] == "succeeded", response.text
        assert (await first.post("/api/v1/ai-search/query", json=message(sid, 3))).status_code == 429
        assert parser.calls == 3
        replay = await first.post("/api/v1/ai-search/query", json=initial)
        assert replay.status_code == 200 and replay.json()["replay"] and parser.calls == 3
        receipt = answer["operation"]["receipt"]["result_ref"]
        old_page = await first.post(f"/api/v1/ai-search/results/{receipt}/cards", json={"search": {
            "limit": 1, "cursor": answer["cards"]["cards"]["nextCursor"]}})
        assert old_page.status_code == 200 and old_page.json()["cards"]["total"] == 3, old_page.text
        metadata = await first.get(f"/api/v1/ai-search/results/{receipt}")
        assert metadata.status_code == 200 and metadata.json()["intent"]["version"] == 1
        bounds = {"north": 28.5, "south": 27.5, "east": -16.6, "west": -16.9, "zoom": 14}
        result_map = await first.post(f"/api/v1/ai-search/results/{receipt}/map", json={"search": bounds})
        assert result_map.status_code == 200 and len(result_map.json()["map"]["items"]) == 3, result_map.text
        assert result_map.json()["intent_hash"] == answer["cards"]["intent_hash"]
        current_map = await first.post(f"/api/v1/ai-search/sessions/{sid}/map", json={"expected_version": 3, "search": bounds})
        assert current_map.status_code == 200 and len(current_map.json()["map"]["items"]) == 3
        quota = await first.get("/api/v1/ai-search/quota")
        assert quota.json()["used"] == 3 and quota.json()["reserved"] == 0
        reset = await first.post(f"/api/v1/ai-search/sessions/{sid}/reset", json={"expected_version": 3})
        assert reset.status_code == 200 and reset.json()["intent"]["session_id"] != sid
        new_sid = reset.json()["intent"]["session_id"]
        assert (await first.post("/api/v1/ai-search/query", json=message(new_sid, 0))).status_code == 429
        assert (await first.get(f"/api/v1/ai-search/sessions/{sid}")).status_code == 409
        await other.post("/api/v1/ai-search/sessions")
        assert (await other.get(f"/api/v1/ai-search/sessions/{new_sid}")).status_code == 404
        assert (await other.post(f"/api/v1/ai-search/results/{receipt}/cards", json={})).status_code == 404
        async with SessionLocal() as session:
            assert not await session.scalar(text("SELECT bool_or(criteria::text LIKE '%PRIVATE_SYNTHETIC_INPUT%') FROM ai_search_sessions"))
            assert not await session.scalar(text("SELECT bool_or(intent::text LIKE '%PRIVATE_SYNTHETIC_INPUT%') FROM ai_search_results"))


async def test_origin_cookie_gate_and_client_authority_fields_fail_closed(active):
    runtime, parser, gate = active
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers=HEADERS) as client:
        assert (await client.post("/api/v1/ai-search/sessions", headers={"Origin": "https://attacker.invalid"})).status_code == 403
        assert (await client.post("/api/v1/ai-search/sessions", headers={"X-AI-Request": "0"})).status_code == 403
        created = await client.post("/api/v1/ai-search/sessions")
        sid = created.json()["intent"]["session_id"]
        for cookie in ("forged", runtime.guests.issue(now=1)[0]):
            result = await client.get(f"/api/v1/ai-search/sessions/{sid}", headers={"Cookie": "ai_search_guest=" + cookie})
            assert result.status_code == 401 and "Max-Age=0" in result.headers["set-cookie"]
        # Invalid-cookie responses now clear the jar. Renew explicitly before
        # testing unrelated body/schema authority with a valid identity.
        sid = (await client.post("/api/v1/ai-search/sessions")).json()["intent"]["session_id"]
        oversized = await client.post("/api/v1/ai-search/query", content=b"x" * 131_073,
                                      headers={"Content-Type": "application/json"})
        assert oversized.status_code == 413 and parser.calls == 0
        async def chunks():
            yield b"x" * 70_000
            yield b"x" * 70_000
        chunked = await client.post("/api/v1/ai-search/query", content=chunks(), headers={"Content-Type": "application/json"})
        assert chunked.status_code == 413 and parser.calls == 0
        semantic_view = message(sid, 0) | {"search": {"petsAllowed": False}}
        assert (await client.post("/api/v1/ai-search/query", json=semantic_view)).status_code == 422
        forged = message(sid, 0) | {"subject_id": str(uuid4()), "quota_limit": 99999}
        result = await client.post("/api/v1/ai-search/query", json=forged)
        assert result.status_code == 422 and "PRIVATE_SYNTHETIC_INPUT" not in result.text
        assert (await client.post("/api/v1/ai-search/sessions", headers={"Authorization": "Bearer invalid"})).status_code == 401
        gate.reject = True
        result = await client.post("/api/v1/ai-search/query", json=message(sid, 0))
        assert result.status_code == 503 and result.json()["detail"] == "ABUSE_GATE_UNAVAILABLE"
        assert parser.calls == 0


async def test_registered_subject_has_auth_quota_and_never_auto_transfers_guest(active, register_user):
    _, parser, _ = active
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers=HEADERS) as client:
        guest = await client.post("/api/v1/ai-search/sessions")
        guest_sid = guest.json()["intent"]["session_id"]
        token, user = await register_user(client, email="ai-http-auth@example.org")
        headers = {"Authorization": "Bearer " + token}
        assert (await client.get(f"/api/v1/ai-search/sessions/{guest_sid}", headers=headers)).status_code == 404
        created = await client.post("/api/v1/ai-search/sessions", headers=headers)
        assert created.status_code == 200 and created.json()["intent"]["criteria"] == {}, created.text
        sid = created.json()["intent"]["session_id"]
        result = await client.post("/api/v1/ai-search/query", json=message(sid, 0), headers=headers)
        assert result.status_code == 200 and result.json()["operation"]["limit"] == 200, result.text
        async with SessionLocal() as session, session.begin():
            await session.execute(text("UPDATE users SET blocked=true WHERE id=:id"), {"id": UUID(user["id"])})
        assert (await client.post("/api/v1/ai-search/sessions", headers=headers)).status_code == 401
        blocked_quota = await client.get("/api/v1/ai-search/quota", headers=headers)
        assert blocked_quota.status_code == 401 and blocked_quota.headers["cache-control"] == "no-store"
        assert parser.calls == 1


MAP_BOUNDS = {"north": 28.5, "south": 27.5, "east": -16.6, "west": -16.9, "zoom": 14}


def private_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json() == {"detail": code}
    assert response.headers["cache-control"] == "no-store"


async def test_new_map_metadata_routes_reject_foreign_missing_expired_and_stale_versions(active, register_user):
    _, parser, _ = active
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers=HEADERS) as owner, AsyncClient(
        transport=ASGITransport(app), base_url="https://testserver", headers=HEADERS) as other:
        sid = (await owner.post("/api/v1/ai-search/sessions")).json()["intent"]["session_id"]
        answer = (await owner.post("/api/v1/ai-search/query", json=message(sid, 0))).json()
        ref = answer["operation"]["receipt"]["result_ref"]
        routes = [("GET", f"/api/v1/ai-search/results/{ref}", None, "RESULT_NOT_FOUND"),
                  ("POST", f"/api/v1/ai-search/results/{ref}/map", {"search": MAP_BOUNDS}, "RESULT_NOT_FOUND"),
                  ("POST", f"/api/v1/ai-search/sessions/{sid}/map",
                   {"expected_version": 1, "search": MAP_BOUNDS}, "SESSION_NOT_FOUND")]
        await other.post("/api/v1/ai-search/sessions")
        for method, path, payload, code in routes:
            private_error(await other.request(method, path, json=payload), 404, code)
            private_error(await owner.request(method, path.replace(ref, str(uuid4())).replace(sid, str(uuid4())),
                                              json=payload), 404, code)
        # An authenticated identity cannot inherit its own browser's guest data.
        token, _ = await register_user(other, email="ai-map-isolation@example.org")
        for method, path, payload, code in routes:
            private_error(await owner.request(method, path, json=payload, headers={"Authorization": "Bearer " + token}), 404, code)
        private_error(await owner.post(f"/api/v1/ai-search/sessions/{sid}/map",
            json={"expected_version": 0, "search": MAP_BOUNDS}), 409, "SESSION_VERSION_CONFLICT")
        for method, path, payload, _ in routes[1:]:
            private_error(await owner.request(method, path, json=payload, headers={"Origin": "https://attacker.invalid"}),
                          403, "AI_ORIGIN_OR_CSRF_REJECTED")
        async with SessionLocal() as session, session.begin():
            await session.execute(update(AISearchSession).where(AISearchSession.id == UUID(sid)).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        for method, path, payload, _ in routes:
            code = "SESSION_EXPIRED" if "/sessions/" in path else "RESULT_EXPIRED_REQUERY_REQUIRED"
            private_error(await owner.request(method, path, json=payload), 409, code)
        assert parser.calls == 1


async def test_map_body_rejects_injected_semantics_and_invalid_viewports_at_http_boundary(active):
    _, parser, _ = active
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers=HEADERS) as client:
        sid = (await client.post("/api/v1/ai-search/sessions")).json()["intent"]["session_id"]
        paths = [(f"/api/v1/ai-search/results/{uuid4()}/map", {}),
                 (f"/api/v1/ai-search/sessions/{sid}/map", {"expected_version": 0})]
        invalid = [{"petsAllowed": True}, {"maxPrice": 500}, {"subject_id": str(uuid4())},
                   {"north": 91}, {"south": -91}, {"east": 181}, {"west": -181},
                   {"zoom": 1}, {"zoom": 22}, {"north": 27.5}, {"south": 29},
                   {"east": -16.9}, {"west": 0}, {"zoom": None}, {"north": "NaN"}]
        for path, base in paths:
            for change in invalid:
                private_error(await client.post(path, json=base | {"search": MAP_BOUNDS | change}), 422, "AI_REQUEST_INVALID")
            private_error(await client.post(path, json=base | {"search": MAP_BOUNDS, "subject_id": str(uuid4())}),
                          422, "AI_REQUEST_INVALID")
        for version in (True, "0", -1, 2_147_483_648, None):
            private_error(await client.post(paths[1][0], json={"expected_version": version, "search": MAP_BOUNDS}),
                          422, "AI_REQUEST_INVALID")
        assert parser.calls == 0


async def test_quota_http_requires_identity_and_repeated_reads_never_create_rows_or_renew_session(active):
    runtime, parser, _ = active
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers=HEADERS) as client:
        private_error(await client.get("/api/v1/ai-search/quota"), 401, "AI_GUEST_IDENTITY_REQUIRED")
        for token in ("forged", runtime.guests.issue(now=1)[0]):
            response = await client.get("/api/v1/ai-search/quota", headers={"Cookie": "ai_search_guest=" + token})
            private_error(response, 401, "AI_GUEST_IDENTITY_INVALID_OR_EXPIRED")
            assert "Max-Age=0" in response.headers["set-cookie"]
        sid = UUID((await client.post("/api/v1/ai-search/sessions")).json()["intent"]["session_id"])
        async with SessionLocal() as session:
            before = (await session.execute(select(AISearchSession.expires_at, AISearchSession.updated_at).where(
                AISearchSession.id == sid))).one()
            assert await session.scalar(select(func.count()).select_from(AIUsageDay)) == 0
        for _ in range(3):
            response = await client.get("/api/v1/ai-search/quota")
            assert response.status_code == 200 and response.json()["remaining"] == 3
            assert response.headers["cache-control"] == "no-store" and "set-cookie" not in response.headers
        async with SessionLocal() as session:
            assert (await session.execute(select(AISearchSession.expires_at, AISearchSession.updated_at).where(
                AISearchSession.id == sid))).one() == before
            assert await session.scalar(select(func.count()).select_from(AIUsageDay)) == 0
        assert parser.calls == 0


async def test_expired_replay_receipt_survives_real_verified_card_access_denial(active, monkeypatch):
    runtime, parser, _gate = active
    original = runtime.sessions.finalize_patch
    async def lost_ack(*args, **kwargs):
        await original(*args, **kwargs)
        raise OSError("synthetic acknowledgement loss")
    monkeypatch.setattr(runtime.sessions, "finalize_patch", lost_ack)
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers=HEADERS) as client:
        sid = (await client.post("/api/v1/ai-search/sessions")).json()["intent"]["session_id"]
        payload = message(sid, 0)
        assert (await client.post("/api/v1/ai-search/query", json=payload)).status_code == 503
        async with SessionLocal.begin() as conn:
            await conn.execute(update(AISearchSession).where(AISearchSession.id == UUID(sid)).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        for _ in range(2):
            response = await client.post("/api/v1/ai-search/query", json=payload)
            assert response.status_code == 200, response.text
            answer = response.json()
            assert answer["operation"]["status"] == "succeeded"
            assert answer["operation"]["receipt"]["count"] == 3
            assert answer["cards"] is None and answer["cards_error"] == "RESULT_EXPIRED_REQUERY_REQUIRED"
        ref = answer["operation"]["receipt"]["result_ref"]
        private_error(await client.post(f"/api/v1/ai-search/results/{ref}/cards", json={}),
                      409, "RESULT_EXPIRED_REQUERY_REQUIRED")
        assert parser.calls == 1
        quota = (await client.get("/api/v1/ai-search/quota")).json()
        assert quota["used"] == 1 and quota["reserved"] == 0


async def test_browser_recovers_real_expired_terminal_receipt(active, monkeypatch):
    # Run with a local Vite frontend: AI_UI_TEST_URL=http://127.0.0.1:4176.
    # Browser API requests go through ASGI and real PostGIS/ledger, without
    # synthetic query/session responses or any external provider traffic.
    import os
    from urllib.parse import urlsplit
    frontend = os.getenv("AI_UI_TEST_URL")
    if not frontend:
        pytest.skip("set AI_UI_TEST_URL to an isolated local frontend")
    assert urlsplit(frontend).hostname == "127.0.0.1"
    from playwright.async_api import async_playwright, expect
    runtime, parser, _gate = active
    real_finalize = runtime.sessions.finalize_patch
    async def expire_after_commit(*args, **kwargs):
        completed = await real_finalize(*args, **kwargs)
        async with SessionLocal.begin() as conn:
            await conn.execute(update(AISearchSession).where(AISearchSession.id == args[1].session_id).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        raise OSError("synthetic lost acknowledgement")
    monkeypatch.setattr(runtime.sessions, "finalize_patch", expire_after_commit)
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers=HEADERS) as client:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                page = await browser.new_page()
                requests = []
                async def forward(route):
                    request = route.request
                    url = urlsplit(request.url)
                    if url.hostname != "127.0.0.1":
                        return await route.abort()
                    if url.path.startswith("/api/v1/ai-search/"):
                        if url.path.endswith("/query"):
                            requests.append(request.post_data_json)
                        response = await client.request(request.method, url.path, content=request.post_data,
                            headers={"Content-Type": "application/json"})
                        return await route.fulfill(status=response.status_code, body=response.content,
                                                   content_type="application/json")
                    if url.path.startswith("/api/"):
                        return await route.fulfill(status=404, json={"detail": "Not found"})
                    await route.continue_()
                await page.route("**/*", forward)
                await page.add_init_script("localStorage.setItem('112233:language:v1','es'); localStorage.setItem('112233:mobile-onboarding:v1','done:refreshable')")
                await page.goto(frontend + "/#/")
                await page.get_by_role("button", name="Escribir mi búsqueda").click()
                await page.locator("#ai-search-text").fill("Una habitación con mi perro")
                await page.get_by_role("button", name="Buscar habitaciones", exact=True).click()
                retry = page.get_by_role("button", name="Comprobar el mismo intento")
                await expect(retry).to_be_enabled()
                await retry.click()
                await expect(page.get_by_role("button", name="Iniciar nueva conversación")).to_be_enabled()
                await expect(retry).to_have_count(0)
                await expect(page.locator("#ai-search-text")).to_have_value("Una habitación con mi perro")
                assert len(requests) == 2 and requests[0] == requests[1]
                assert parser.calls == 1
                assert (await client.get("/api/v1/ai-search/quota")).json()["used"] == 1
                await page.get_by_role("button", name="Iniciar nueva conversación").click()
                await expect(page.get_by_role("button", name="Buscar habitaciones", exact=True)).to_be_enabled()
            finally:
                await browser.close()
