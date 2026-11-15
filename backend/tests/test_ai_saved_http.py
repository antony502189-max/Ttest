from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_ai_saved_handoff import committed

from app.api.dependencies import current_user
from app.api.v1.ai_saved_searches import router as saved_router
from app.api.v1.ai_search import AISearchRuntime
from app.api.v1.ai_search import router as search_router
from app.repositories.ai_saved_searches import SavedAISnapshot
from app.repositories.ai_search_sessions import SessionError
from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
from app.services.ai_http_policy import AIHTTPPolicy
from app.services.ai_saved_handoff import SavedHandoffError, SavedHandoffSigner
from app.services.ai_saved_runtime import SavedRuntime


def search_app():
    snapshot = committed()
    sessions = SimpleNamespace(result=AsyncMock(return_value=snapshot))
    guests = GuestTokens(key=b"g" * 32, policy=GuestPolicy(ttl_seconds=60))
    active = AISearchRuntime(sessions, SimpleNamespace(sessions=sessions, cursors=SimpleNamespace(key=b"c" * 32)),
        SimpleNamespace(sessions=sessions), guests, SimpleNamespace(check=AsyncMock()),
        frozenset({"https://testserver"}), 32768, AIHTTPPolicy(10, 5, (), "https://testserver"),
        saved_handoff=SavedHandoffSigner(b"s" * 32))
    app = FastAPI()
    app.include_router(search_router, prefix="/api/v1")
    app.state.ai_search_runtime = active
    token, owner = guests.issue()
    return app, active, snapshot, owner, {"Origin": "https://testserver", "X-AI-Request": "1", "Cookie": "ai_search_guest=" + token}


def test_owned_result_handoff_does_not_run_model_or_transfer_guest_identity():
    app, active, snapshot, owner, headers = search_app()
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(f"/api/v1/ai-search/results/{snapshot.result_ref}/save-token", headers=headers)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert active.saved_handoff.verify(response.json()["token"]).intent.criteria == snapshot.intent.criteria
        active.sessions.result.assert_awaited_once_with(owner, snapshot.result_ref)
        active.sessions.result.side_effect = SessionError("RESULT_NOT_FOUND")
        assert client.post(f"/api/v1/ai-search/results/{uuid4()}/save-token", headers=headers).status_code == 404
        assert client.post(f"/api/v1/ai-search/results/{snapshot.result_ref}/save-token", headers={"Origin": "https://foreign.invalid"}).status_code == 403


def test_independent_key_and_explicit_off_switch():
    app, active, snapshot, _, headers = search_app()
    for key in (b"g" * 32, b"c" * 32):
        with pytest.raises(ValueError, match="independent"):
            replace(active, saved_handoff=SavedHandoffSigner(key))
    app.state.ai_search_runtime = replace(active, saved_handoff=None)
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/api/v1/ai-search/capabilities").json()["save_handoff"] is False
        assert client.post(f"/api/v1/ai-search/results/{snapshot.result_ref}/save-token", headers=headers).status_code == 503
    active.sessions.result.assert_not_awaited()


def test_registered_save_drops_private_validation_and_handoff_errors(caplog):
    app = FastAPI()
    app.include_router(saved_router, prefix="/api/v1")
    user = SimpleNamespace(id=uuid4())
    app.dependency_overrides[current_user] = lambda: user
    snapshot = committed()
    signer = SavedHandoffSigner(b"s" * 32)
    intent = signer.verify(signer.issue(snapshot)).intent
    saved = SavedAISnapshot(id=uuid4(), name="", revision=1, enabled=True, intent=intent, intent_hash="a" * 64)
    repo = SimpleNamespace(save_handoff=AsyncMock(return_value=saved), set_enabled=AsyncMock(return_value=saved))
    app.state.ai_saved_runtime = SavedRuntime(repo, signer, SimpleNamespace())
    with TestClient(app) as client:
        assert client.get("/api/v1/saved-searches/ai/capabilities").json() == {"save": True}
        result = client.post("/api/v1/saved-searches/ai", json={"token": "synthetic-token"})
        assert result.status_code == 200 and "criteria" not in result.json() and "intent" not in result.json()
        assert result.headers["cache-control"] == "private, no-store"
        assert repo.save_handoff.await_args.kwargs == {"name": "", "notifications": True}
        for body in ({"token": "synthetic-token", "PRIVATE_FIELD": "PRIVATE_VALUE"}, {"token": "PRIVATE_VALUE" * 4000}):
            rejected = client.post("/api/v1/saved-searches/ai", json=body)
            assert rejected.status_code in {413, 422} and "PRIVATE" not in rejected.text
        repo.save_handoff.side_effect = SavedHandoffError("PRIVATE_VALUE")
        rejected = client.post("/api/v1/saved-searches/ai", json={"token": "PRIVATE_VALUE"})
        assert rejected.status_code == 409 and rejected.json() == {"detail": "AI_SAVE_REFRESH_RESULT"}
        assert client.patch(f"/api/v1/saved-searches/ai/{saved.id}", json={"revision": 1, "enabled": False}).status_code == 200
        assert client.patch(f"/api/v1/saved-searches/ai/{saved.id}", json={"revision": True, "enabled": "false"}).status_code == 422
    assert "PRIVATE_VALUE" not in caplog.text and "PRIVATE_FIELD" not in caplog.text
