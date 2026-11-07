"""Application composition and fail-closed startup, without provider or DB IO."""
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.ai_search import router
from app.repositories.ai_fact_pipeline import FactPipeline
from app.repositories.ai_search_sessions import SessionPolicy
from app.schemas.ai_fact_pipeline import FactQueuePolicy
from app.schemas.ai_listing_facts import FactVocabulary
from app.schemas.ai_search_quota import LeasePolicy
from app.services import ai_text_runtime as composition
from app.services.ai_fact_quality import FactQualityPolicy
from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
from app.services.ai_http_policy import AIHTTPPolicy
from app.services.ai_provider_privacy import RealUserOutboundDenied
from app.services.rate_limit import RedisRateLimiter

REVISION = "0079_ai_operating_policy"


@pytest.fixture
def setup(monkeypatch):
    connection = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [REVISION]))))

    @asynccontextmanager
    async def factory():
        yield connection

    pipeline = FactPipeline(factory, FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1),
        FactVocabulary(amenity_codes=frozenset({"wifi"}), catalog_other_codes=frozenset(),
                       tenant_group_codes=frozenset(), municipality_zones=frozenset()),
        resolver_version="reviewed.v1", operating_policy=FactQualityPolicy(
            price_max_age_seconds=86400, policy_max_age_seconds=86400, evidence_retention_seconds=604800))
    limiter = RedisRateLimiter("redis://127.0.0.1:1/0")
    monkeypatch.setattr(limiter, "ping", AsyncMock(return_value=True))
    monkeypatch.setattr(limiter, "close", AsyncMock())
    # The current real-user boundary stays denied. No provider is created.
    parser = SimpleNamespace(parse=AsyncMock(side_effect=AssertionError("unexpected inference")),
                             gate=RealUserOutboundDenied(), total_budget_seconds=10)
    args = {"pipeline": pipeline, "parser": parser, "limiter": limiter,
        "lease_policy": LeasePolicy(reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30),
        "session_policy": SessionPolicy(inactivity_seconds=86400),
        "guests": GuestTokens(key=b"g" * 32, policy=GuestPolicy(ttl_seconds=604800)),
        "cursor_key": b"c" * 32, "http_policy": AIHTTPPolicy(20, 3, (), "https://testserver"),
        "origins": frozenset({"https://testserver"}), "max_body_bytes": 32768, "execution_seconds": 15}
    journal = object()
    monkeypatch.setattr(composition, "configured_journal", lambda: journal)
    replay = AsyncMock()
    monkeypatch.setattr(composition, "replay_erasure", replay)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return SimpleNamespace(app=app, args=args, parser=parser, limiter=limiter,
                           connection=connection, journal=journal, replay=replay)


def test_capabilities_only_after_dependencies_and_erasure_replay(setup):
    active = composition.assemble_text_runtime(**setup.args)
    assert active.sessions.require_auth_owner
    assert active.sessions.vocabulary.amenity_codes == frozenset({"wifi"})
    assert active.sessions.ledger.sessions is setup.args["pipeline"].sessions
    assert not hasattr(setup.app.state, "ai_search_runtime")
    composition.install_text_runtime(setup.app, active)
    # Installation alone must not advertise enabled AI.
    assert not hasattr(setup.app.state, "ai_search_runtime")
    with TestClient(setup.app, base_url="https://testserver") as client:
        setup.replay.assert_awaited_once_with(active.sessions.ledger.sessions, setup.journal)
        assert client.get("/api/v1/ai-search/capabilities").json() == {
            "text": True, "map": True, "voice": False, "saved_searches": False}
        # An operator kill switch immediately closes the existing API.
        setup.app.state.ai_search_runtime = None
        assert client.get("/api/v1/ai-search/capabilities").json()["text"] is False
        assert client.post("/api/v1/ai-search/sessions").status_code == 503
    setup.limiter.close.assert_awaited_once()
    setup.parser.parse.assert_not_awaited()


@pytest.mark.parametrize("failure", ["schema", "redis", "journal", "replay"])
def test_dependency_failure_never_publishes_runtime(setup, monkeypatch, failure):
    active = composition.assemble_text_runtime(**setup.args)
    if failure == "schema":
        setup.connection.execute.return_value = SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: ["0066_complimentary_ads"]))
    elif failure == "redis":
        setup.limiter.ping.return_value = False
    elif failure == "journal":
        monkeypatch.setattr(composition, "configured_journal", lambda: None)
    else:
        setup.replay.side_effect = ValueError("AI_ERASURE_JOURNAL_BINDING_INVALID")
    composition.install_text_runtime(setup.app, active)
    with pytest.raises(ValueError), TestClient(setup.app):
        pytest.fail("startup must fail before traffic")
    assert not hasattr(setup.app.state, "ai_search_runtime")
    setup.limiter.close.assert_awaited_once()
    setup.parser.parse.assert_not_awaited()
    if failure in {"schema", "redis", "journal"}:
        setup.replay.assert_not_awaited()


@pytest.mark.parametrize("change", ["freshness", "keys", "parser_deadline", "http_deadline"])
def test_invalid_operating_configuration_rejected_before_io(setup, change):
    args = setup.args.copy()
    if change == "freshness":
        args["pipeline"].operating_policy = None
    elif change == "keys":
        args["cursor_key"] = args["guests"].key
    elif change == "parser_deadline":
        args["parser"].total_budget_seconds = 25
    else:
        args["http_policy"] = replace(args["http_policy"], request_seconds=15)
    with pytest.raises(ValueError):
        composition.assemble_text_runtime(**args)
    setup.limiter.ping.assert_not_awaited()
    setup.parser.parse.assert_not_awaited()


def test_installation_cannot_replace_existing_runtime(setup):
    active = composition.assemble_text_runtime(**setup.args)
    composition.install_text_runtime(setup.app, active)
    with pytest.raises(ValueError, match="already installed"):
        composition.install_text_runtime(setup.app, active)
