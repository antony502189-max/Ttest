"""Actual HTTP+cookies+ownership+quota+PostGIS cards, with an offline parser."""
import json
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from test_ai_verified_cards import setup

from app.api.v1.ai_search import AISearchRuntime
from app.db.session import SessionLocal
from app.main import app
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
        gate, frozenset({"https://testserver"}), 131_072, AIHTTPPolicy(10, 5, ()))
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
            assert result.status_code == 401 and "set-cookie" not in result.headers
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
        assert parser.calls == 1
