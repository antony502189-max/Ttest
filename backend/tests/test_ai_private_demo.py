import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.repositories.ai_fact_snapshots import CapturedParserSnapshot
from app.schemas.ai_fact_bridge import BridgeReference, BridgeRejected
from app.schemas.ai_search_intent import Criteria, SearchIntent, apply_patch
from app.services.ai_closed_deepseek import EvaluationBudget
from app.services.ai_deepseek_intent import ProviderFailure
from app.services.ai_pisocompartido_price import prepare_price
from demo.budget import ATTEMPT
from demo.entry import BINDING, PHRASES, DemoBudget, DemoGate, DemoParser, DemoTransport


def snapshot(**updates):
    sid = uuid4()
    value = {"source_name": "PisoCompartido", "source_price_text": "450 €/mes", "rental_mode": "long",
        "price_currency": "EUR", "price_period": "month", "price_is_from": False, "price_amount": 450,
        "pets_allowed": True, "phone": "PRIVATE_CONTACT", "description": "PRIVATE_TEXT"}
    value.update(updates)
    return CapturedParserSnapshot(BridgeReference(source_record_id=sid, canonical_listing_id=uuid4(),
        source_identifier=f"PisoCompartido:{sid.hex}", snapshot_hash="a" * 64), "{}", json.dumps(value), value["source_price_text"])


def test_price_mapping_never_admits_contacts_or_default_booleans():
    ready = prepare_price(snapshot())
    assert {f.key for f in ready.facts} == {"price", "rental_mode"}
    data = json.dumps(ready.sanitized_fields)
    assert "PRIVATE" not in data and "phone" not in data and "pets" not in data
    assert ready.source.snapshot_hash == "a" * 64


@pytest.mark.parametrize("update", [{"price_amount": 451}, {"price_is_from": True},
    {"price_currency": "USD"}, {"price_period": "week"}, {"rental_mode": "holiday"},
    {"source_name": "Other"}, {"source_price_text": "desde 450 €/mes"},
    {"price_period": None}, {"source_price_text": "450 €/mes, 20€ gastos"}])
def test_unconfirmed_or_disagreeing_price_is_rejected(update):
    with pytest.raises(BridgeRejected):
        prepare_price(snapshot(**update))


def test_independent_demo_budget_reopen_cannot_reset_three_attempt_limit(tmp_path):
    path = tmp_path / "demo.sqlite3"
    budget = DemoBudget(path, corpus_sha256=BINDING, initialize=True)
    session = str(uuid4())
    for step in range(3):
        accepted_step(budget, session, step)
    with pytest.raises(ProviderFailure, match="BUDGET_EXHAUSTED"):
        DemoBudget(path, corpus_sha256=BINDING).reserve()
    assert budget.summary()["attempts"] == 3
    assert budget.summary()["reserved_micro_usd"] == 33180
    with pytest.raises(ProviderFailure, match="JOURNAL_MISMATCH"):
        DemoBudget(path, corpus_sha256="b" * 64)


def accepted_step(budget, session, step):
    token = ATTEMPT.set((session, step, step))
    try:
        ticket = budget.reserve()
        budget.record_usage(ticket, b'{"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}')
        budget.accept(ticket)
    finally:
        ATTEMPT.reset(token)


def test_global_sequence_binds_one_session_and_never_refunds_ambiguous_attempt(tmp_path):
    budget = DemoBudget(tmp_path / "demo.sqlite3", corpus_sha256=BINDING, initialize=True)
    first, other = str(uuid4()), str(uuid4())
    accepted_step(budget, first, 0)
    for attempt in ((other, 0, 0), (other, 1, 1), (first, 0, 0), (first, 2, 2)):
        token = ATTEMPT.set(attempt)
        try:
            with pytest.raises(ProviderFailure, match="SEQUENCE_REJECTED"):
                budget.reserve()
        finally:
            ATTEMPT.reset(token)
    token = ATTEMPT.set((first, 1, 1))
    try:
        ticket = budget.reserve()  # Crash/lost ACK: pending survives restart.
        with pytest.raises(ProviderFailure, match="ALREADY_RESERVED"):
            DemoBudget(budget.path, corpus_sha256=BINDING).reserve()
        budget.uncertain(ticket)
        with pytest.raises(ProviderFailure, match="SEQUENCE_REJECTED"):
            budget.reserve()
    finally:
        ATTEMPT.reset(token)
    assert budget.summary()["attempts"] == 2 and budget.status()["halted"]


def test_parallel_new_sessions_cannot_spend_first_step_twice(tmp_path):
    path = tmp_path / "demo.sqlite3"
    budget = DemoBudget(path, corpus_sha256=BINDING, initialize=True)
    def reserve(_):
        token = ATTEMPT.set((str(uuid4()), 0, 0))
        try:
            return DemoBudget(path, corpus_sha256=BINDING).reserve()
        except ProviderFailure:
            return None
        finally:
            ATTEMPT.reset(token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(x is not None for x in pool.map(reserve, range(2))) == 1
    assert budget.summary()["attempts"] == 1


def test_missing_or_replaced_journal_is_never_initialized_by_application(tmp_path):
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(ProviderFailure, match="JOURNAL_REQUIRED"):
        DemoBudget(path, corpus_sha256=BINDING)
    assert not path.exists()


def test_random_database_secret_and_dedicated_destination_required(monkeypatch):
    from demo.entry import APPROVAL, ORIGIN, require_demo
    env = {"APP_ENV":"test", "AI_PRIVATE_TEXT_DEMO_APPROVAL":APPROVAL, "REDIS_URL":"redis://redis:6379/0",
        "FRONTEND_APP_URL":ORIGIN, "FRONTEND_ORIGINS":ORIGIN, "EXTERNAL_IMPORT_ENABLED":"false",
        "EXTERNAL_REMOVAL_CHECK_ENABLED":"false", "AI_DEMO_DATABASE_PASSWORD":"a"*64,
        "DATABASE_URL":"postgresql+asyncpg://ai_demo:"+"a"*64+"@postgres:5432/ai_text_demo_20261108"}
    for k,v in env.items():monkeypatch.setenv(k,v)
    require_demo()
    for bad in (env["DATABASE_URL"].replace("@postgres", "@external.invalid"),
                env["DATABASE_URL"].replace("/ai_text_demo_20261108", "/production")):
        monkeypatch.setenv("DATABASE_URL",bad)
        with pytest.raises(ValueError, match="DATABASE_CONFIGURATION"):
            require_demo()
    assert "private-demo-only" not in (Path(__file__).parents[2] / "deploy/ai-text-demo/compose.yml").read_text()


async def test_exact_demo_phrases_and_states_only_before_provider_io():
    gate = DemoGate()
    current = SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1", session_id=uuid4(),
        version=0, criteria=Criteria.model_validate_json('{"rental_mode":{"strength":"hard","value":"long"}}'))
    value = await gate.prepare(PHRASES[0], current)
    assert set(value.model_dump()) == {"schema_version", "provider", "purpose", "text", "criteria"}
    for text in ("PRIVATE_EMAIL@example.invalid", PHRASES[1], PHRASES[0] + " "):
        with pytest.raises(ProviderFailure, match="INPUT_NOT_APPROVED"):
            await gate.prepare(text, current)
    budget = {"strength": "hard", "value": {"amount": "600.00", "currency": "EUR", "period": "monthly"}}
    refined = current.model_copy(update={"criteria": Criteria.model_validate_json(json.dumps({
        "rental_mode": {"strength": "hard", "value": "long"}, "budget": budget}))})
    await gate.prepare(PHRASES[1], refined)


async def test_exhausted_demo_never_reads_provider_key(monkeypatch):
    from types import SimpleNamespace

    from demo import entry
    monkeypatch.setattr(entry, "require_demo", lambda: None)
    monkeypatch.setattr(entry, "DemoBudget", lambda *a, **k: SimpleNamespace(summary=lambda: {"attempts": 3}))
    def forbidden(*args, **kwargs):
        raise AssertionError("provider key must remain unmounted")
    monkeypatch.setattr(entry.Path, "read_text", forbidden)
    parser = entry.DemoParser()
    assert parser.key.get_secret_value() == "budget-exhausted-no-live-key"
    await parser.transport.aclose()


def fake_parser(tmp_path, responder):
    from app.services.ai_deepseek_intent import DeepSeekPolicy
    parser = object.__new__(DemoParser)
    parser.budget = DemoBudget(tmp_path / "provider.sqlite3", corpus_sha256=BINDING, initialize=True)
    parser.key, parser.gate = SecretStr("offline-placeholder"), DemoGate()
    parser.policy = DeepSeekPolicy(model="deepseek-flash", timeout_seconds=8,
        total_budget_seconds=10, max_tokens=1024, max_attempts=1, retry_delay_seconds=0, max_response_bytes=65536)
    parser.transport = DemoTransport(httpx.MockTransport(responder), parser.budget)
    return parser


def intent():
    return SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1", session_id=uuid4(),
        version=0, criteria=Criteria.model_validate({"rental_mode":{"strength":"hard","value":"long"}}))


def response_for(step):
    patch = {"set":{"budget":{"strength":"hard","value":{"amount":str(600-step*200),
        "currency":"EUR","period":"monthly"}}},"remove":[]} if step < 2 else {"set":{},"remove":["budget"]}
    return {"choices":[{"finish_reason":"stop","message":{"role":"assistant",
        "content":json.dumps({"status":"patch","patch":patch})}}],
        "usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}


async def test_parser_three_semantic_steps_and_cross_session_are_metered_once(tmp_path):
    sent = []
    def responder(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=response_for(len(sent)-1))
    parser, current = fake_parser(tmp_path, responder), intent()
    for step, phrase in enumerate(PHRASES):
        if step:
            with pytest.raises(ProviderFailure, match="SEQUENCE_REJECTED"):
                await parser.parse(PHRASES[0], intent())
        patch = await parser.parse(phrase, current)
        current = apply_patch(current, patch)
    assert len(sent) == 3 and parser.budget.status()["exhausted"]
    assert current.version == 3 and current.criteria.budget is None
    assert str(current.session_id) not in json.dumps(sent)
    with pytest.raises(ProviderFailure, match="BUDGET_EXHAUSTED"):
        await parser.parse(PHRASES[0], intent())
    assert len(sent) == 3
    await parser.transport.aclose()


@pytest.mark.parametrize("failure", ["invalid_json","wrong_budget","lost_ack"])
async def test_ambiguous_or_wrong_provider_result_halts_without_another_dispatch(tmp_path, failure):
    sent = []
    def responder(request):
        sent.append(request.url)
        if failure == "lost_ack":
            raise httpx.ReadError("offline lost acknowledgement")
        if failure == "invalid_json":
            return httpx.Response(200, content=b"not-json")
        return httpx.Response(200, json=response_for(1))  # 400 on first step is valid syntax, wrong semantics.
    parser, current = fake_parser(tmp_path, responder), intent()
    with pytest.raises(ProviderFailure):
        await parser.parse(PHRASES[0], current)
    with pytest.raises(ProviderFailure, match="SEQUENCE_REJECTED"):
        await parser.parse(PHRASES[0], current)
    assert len(sent) == 1 and parser.budget.summary()["attempts"] == 1
    assert DemoBudget(parser.budget.path, corpus_sha256=BINDING).status()["halted"]
    await parser.transport.aclose()


def test_legacy_spent_journal_is_readable_without_migration_or_reset(tmp_path):
    import hashlib
    path = tmp_path / "legacy.sqlite3"
    old = EvaluationBudget(path, corpus_sha256=BINDING)
    for _ in range(3):
        old.reserve()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    legacy = DemoBudget(path, corpus_sha256=BINDING)
    assert legacy.status()["exhausted"]
    with pytest.raises(ProviderFailure, match="BUDGET_EXHAUSTED"):
        legacy.reserve()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
