import base64
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.ai_search import AISearchRuntime
from app.main import app
from app.services import ai_registered_runtime as composition
from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
from app.services.ai_http_policy import AIHTTPPolicy


@pytest.fixture
def configured(monkeypatch, tmp_path):
    def file(variable, name, data):
        path = tmp_path / name
        path.write_bytes(data)
        monkeypatch.setenv(variable, str(path))
        return path
    keys = file("AI_REGISTERED_KEYS_FILE", "keys.json", json.dumps({"schema": "ai-registered-keys.v1",
        "ip": base64.b64encode(b"i" * 32).decode(), "cursor": base64.b64encode(b"c" * 32).decode()}).encode())
    cohort = file("AI_SAVED_COHORT_FILE", "cohort.json", json.dumps({"schema": "ai-saved-cohort.v1", "source_ids": [str(uuid4())]}).encode())
    file("AI_SAVED_HANDOFF_KEY_FILE", "handoff.key", base64.b64encode(b"h" * 32))
    file("AI_REGISTERED_ASR_PYTHON", "python", b"synthetic asset, never executed")
    model = tmp_path / "model"
    model.mkdir()
    (model / "model.bin").write_bytes(b"synthetic asset, never loaded")
    monkeypatch.setattr(composition, "MODEL_FILES", {"model.bin": hashlib.sha256(b"synthetic asset, never loaded").hexdigest()})
    monkeypatch.setenv("AI_REGISTERED_ASR_MODEL", str(model))
    monkeypatch.setenv("AI_REGISTERED_SEARCH_MODE", "local-housing-accounts.v1")
    monkeypatch.setenv("AI_SAVED_SEARCH_MODE", "signed-housing-inapp.v1")
    monkeypatch.setattr(composition, "get_settings", lambda: SimpleNamespace(redis_url="redis://127.0.0.1:1/0", frontend_app_url="https://testserver"))
    return keys, cohort


def test_disabled_native_runtime_does_not_read_files_or_initialize_any_authority(monkeypatch):
    monkeypatch.delenv("AI_REGISTERED_SEARCH_MODE", raising=False)
    monkeypatch.setattr(composition, "_file", lambda *_: pytest.fail("disabled runtime read secrets"))
    assert composition.configured_registered_runtime(object()) is None


@pytest.mark.parametrize("memory,swap,cpu,valid", [("1610612736", "0", "200000 100000", True),
    ("max", "0", "200000 100000", False), ("1610612736", "1610612736", "200000 100000", False),
    ("1610612736", "0", "max 100000", False), ("1610612736", "0", "300000 100000", False),
    ("1610612736", "0", "200000 0", False)])
def test_native_voice_requires_bounded_full_composition_and_no_swap(tmp_path, memory, swap, cpu, valid):
    for name, value in [("memory.max", memory), ("memory.swap.max", swap), ("cpu.max", cpu)]:
        (tmp_path / name).write_text(value)
    if valid: composition.verify_registered_resources(tmp_path)
    else:
        with pytest.raises(ValueError, match="RESOURCE_LIMITS"):
            composition.verify_registered_resources(tmp_path)


def test_native_runtime_uses_primary_cohort_owned_sessions_and_one_voice_authority(configured):
    factory = object()
    runtime, asr = composition.configured_registered_runtime(factory)
    assert runtime.auth_only and runtime.sessions.require_auth_owner
    assert runtime.sessions.ledger.sessions is factory
    assert runtime.cards.source_ids and len(runtime.cards.source_ids) == 1
    assert runtime.cards.pipeline.resolver_version == "housing-main.v1"
    assert runtime.voice.sessions is runtime.sessions and runtime.voice.query is runtime.cards
    assert runtime.voice.asr is asr and runtime.voice.parser is runtime.execution.parser
    assert runtime.saved_handoff is not None and asr.prewarm
    assert runtime.voice.policy.total_budget_seconds == 24


@pytest.mark.parametrize("failure", ["mode", "saved_mode", "keys_schema", "same_keys", "handoff_reuse", "empty_cohort", "duplicate_cohort", "cohort_schema", "missing_asset", "modified_model", "extra_model_file"])
def test_native_configuration_fails_closed_without_key_defaults_or_scope_expansion(configured, monkeypatch, failure):
    keys, cohort = configured
    if failure == "mode": monkeypatch.setenv("AI_REGISTERED_SEARCH_MODE", "automatic")
    elif failure == "saved_mode": monkeypatch.delenv("AI_SAVED_SEARCH_MODE")
    elif failure == "missing_asset": monkeypatch.setenv("AI_REGISTERED_ASR_PYTHON", "/missing/native-asset")
    elif failure == "modified_model": (cohort.parent / "model/model.bin").write_bytes(b"different model")
    elif failure == "extra_model_file": (cohort.parent / "model/unreviewed.bin").write_bytes(b"extra model")
    elif failure in {"keys_schema", "same_keys", "handoff_reuse"}:
        value = json.loads(keys.read_bytes())
        if failure == "keys_schema": value["unexpected"] = True
        elif failure == "same_keys": value["cursor"] = value["ip"]
        else: value["cursor"] = base64.b64encode(b"h" * 32).decode()
        keys.write_text(json.dumps(value))
    else:
        value = json.loads(cohort.read_bytes())
        if failure == "empty_cohort": value["source_ids"] = []
        elif failure == "duplicate_cohort": value["source_ids"] *= 2
        else: value["schema"] = "automatic-all-sources"
        cohort.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        composition.configured_registered_runtime(object())


@pytest.mark.parametrize("cookie", [None, "old-or-invalid-guest-token"])
def test_native_anonymous_requests_never_read_or_issue_guest_identity(monkeypatch, cookie):
    sessions = SimpleNamespace()
    guests = GuestTokens(key=b"g" * 32, policy=GuestPolicy(ttl_seconds=60))
    monkeypatch.setattr(guests, "issue", lambda: pytest.fail("native minted guest"))
    monkeypatch.setattr(guests, "read", lambda *_: pytest.fail("native read guest cookie"))
    active = AISearchRuntime(sessions, SimpleNamespace(sessions=sessions), SimpleNamespace(sessions=sessions), guests,
        SimpleNamespace(check=AsyncMock()), frozenset({"https://testserver"}), 4096,
        AIHTTPPolicy(10, 3, (), "https://testserver"), auth_only=True)
    monkeypatch.setattr(app.state, "ai_search_runtime", active, raising=False)
    headers = {"Origin": "https://testserver", "X-AI-Request": "1"}
    if cookie: headers["Cookie"] = "ai_search_guest=" + cookie
    with TestClient(app, base_url="https://testserver") as client:
        for method, path in [("POST", "/identity"), ("POST", "/sessions"), ("GET", "/quota")]:
            response = client.request(method, "/api/v1/ai-search" + path, headers=headers)
            assert response.status_code == 401 and response.json()["detail"] == "AI_REGISTERED_USER_REQUIRED"
            assert "set-cookie" not in response.headers
