"""No network/key/real journal. Disposable simulated history only."""
import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import SecretStr

from app.schemas.ai_search_intent import Criteria, apply_patch
from app.services.ai_closed_deepseek import RESERVE_MICRO_USD, EvaluationBudget, _BudgetTransport
from app.services.ai_deepseek_intent import ProviderFailure
from lab.closed_ui import (
    APPROVAL,
    BASELINE_ATTEMPTS,
    CORPUS_SHA256,
    ClosedUIParser,
    ExistingSmokeBudget,
    _UIBudgetTransport,
    plan,
    smoke_cases,
)
from lab.intent_eval import state


def journal(tmp_path, count=BASELINE_ATTEMPTS):
    budget = EvaluationBudget(tmp_path / "DISPOSABLE-simulated-budget.sqlite3", corpus_sha256=CORPUS_SHA256)
    for _ in range(count):
        budget.reserve()
    return budget.path


def parser_at(path):
    return ClosedUIParser(key=SecretStr("synthetic-test-only"), journal=path, approval=APPROVAL,
                          approved_corpus_sha256=CORPUS_SHA256)


def test_prepare_is_offline_and_describes_unapproved_bounded_smoke():
    with patch("sqlite3.connect", side_effect=AssertionError), patch("httpx.AsyncHTTPTransport", side_effect=AssertionError):
        prepared = plan()
    assert prepared["status"] == "PREPARED_NOT_AUTHORIZED"
    assert prepared["max_new_http_attempts"] == 3
    assert prepared["max_new_reserved_micro_usd"] == 33180
    assert prepared["provider_calls_made"] == 0


def test_no_new_or_reset_journal_or_old_approval(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(FileNotFoundError):
        parser_at(missing)
    assert not missing.exists()
    path = journal(tmp_path, 0)
    with pytest.raises(ProviderFailure, match="UI_SMOKE_BASELINE_MISSING"):
        parser_at(path)
    with pytest.raises(ProviderFailure, match="LIVE_UI_SMOKE_APPROVAL_REQUIRED"):
        ClosedUIParser(key=SecretStr("synthetic-test-only"), journal=path,
                       approval="deepseek-synthetic-intent-v1", approved_corpus_sha256=CORPUS_SHA256)


def test_same_journal_atomic_fence_across_restarts_and_competing_workers(tmp_path):
    path = journal(tmp_path)
    def reserve(_):
        try:
            return ExistingSmokeBudget(path, corpus_sha256=CORPUS_SHA256).reserve()
        except ProviderFailure as error:
            assert str(error) == "PROVIDER_COST_BUDGET_EXHAUSTED"
            return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        tickets = list(pool.map(reserve, range(12)))
    assert len(set(tickets) - {None}) == 3
    summary = ExistingSmokeBudget(path, corpus_sha256=CORPUS_SHA256).summary()
    assert summary["attempts"] == 54 and summary["reserved_micro_usd"] == 54 * RESERVE_MICRO_USD
    with pytest.raises(ProviderFailure, match="JOURNAL_MISMATCH"):
        ExistingSmokeBudget(path, corpus_sha256="changed")


async def test_three_exact_ui_cases_use_shared_decode_minimal_payload_and_budget_before_io(tmp_path):
    parser = parser_at(journal(tmp_path))
    cases, _ = smoke_cases()
    seen = []
    def handle(request):
        case = cases[len(seen)]
        payload = json.loads(request.content)
        outbound = json.loads(payload["messages"][1]["content"])
        assert outbound == {"text": case["text"], "criteria": {}}
        assert "expected" not in payload["messages"][0]["content"]
        seen.append(parser.budget.summary()["attempts"])
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps({"status": "patch", "patch": {
                "set": case["expected"], "remove": []}})}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})
    parser.transport = _BudgetTransport(httpx.MockTransport(handle), parser.budget)
    for case in cases:
        current = state(case)
        result = await parser.parse(case["text"], current)
        assert result.session_id == current.session_id and result.expected_version == 0
        assert apply_patch(current, result).criteria == Criteria.model_validate_json(json.dumps(case["expected"]))
    assert seen == [52, 53, 54]
    with pytest.raises(ProviderFailure, match="PROVIDER_COST_BUDGET_EXHAUSTED"):
        await parser.parse(cases[0]["text"], state(cases[0]))
    assert len(seen) == 3


async def test_unapproved_text_state_and_changed_corpus_never_reach_io(tmp_path):
    parser = parser_at(journal(tmp_path))
    cases, digest = smoke_cases()
    parser.transport = _BudgetTransport(httpx.MockTransport(lambda r: pytest.fail("unexpected IO")), parser.budget)
    with pytest.raises(ProviderFailure, match="SYNTHETIC_OUTBOUND_CASE_NOT_APPROVED"):
        await parser.parse("private text or biography", state(cases[0]))
    changed = state(cases[0]).model_copy(update={"criteria": Criteria.model_validate_json(
        '{"balcony":{"strength":"hard","value":true}}')})
    with pytest.raises(ProviderFailure, match="SYNTHETIC_OUTBOUND_CASE_NOT_APPROVED"):
        await parser.parse(cases[0]["text"], changed)
    with (patch("lab.closed_ui.load_corpus", return_value=(cases, "changed")),
          pytest.raises(ProviderFailure, match="UI_SMOKE_CORPUS_MISMATCH")):
        smoke_cases()
    assert parser.budget.summary()["attempts"] == 51
    assert digest == CORPUS_SHA256


@pytest.mark.parametrize("fault", ["503", "disconnect", "cancel", "malformed"])
async def test_ambiguous_or_failed_io_never_refunds_or_automatically_retries(tmp_path, fault):
    parser = parser_at(journal(tmp_path))
    calls = []
    def handle(request):
        calls.append(request)
        if fault == "disconnect":
            raise httpx.ReadError("synthetic")
        if fault == "cancel":
            raise asyncio.CancelledError
        return httpx.Response(503) if fault == "503" else httpx.Response(200, json={"invalid": True})
    parser.transport = _BudgetTransport(httpx.MockTransport(handle), parser.budget)
    case = smoke_cases()[0][0]
    with pytest.raises(asyncio.CancelledError if fault == "cancel" else ProviderFailure):
        await parser.parse(case["text"], state(case))
    assert len(calls) == 1 and parser.budget.summary()["attempts"] == 52
    assert parser.total_budget_seconds == 10


def test_explicit_ui_factory_uses_shared_assembly_after_lab_guard(tmp_path):
    from lab.closed_ui import create_app
    with patch("lab.ai_text.require_lab") as guard, patch("lab.ai_text._assemble_app") as assemble:
        create_app(key=SecretStr("synthetic-test-only"), journal=journal(tmp_path), approval=APPROVAL,
                   approved_corpus_sha256=CORPUS_SHA256)
        guard.assert_called_once_with(closed_ui=True)
        parser = assemble.call_args.args[0]()
        assert isinstance(parser, ClosedUIParser)
    # No new public live env mode/credential accepted by the offline lab.


def test_live_ui_mode_needs_separate_composition_and_preserves_production_guards():
    from lab.ai_text import DATABASE, MARKER, ORIGIN, REDIS, require_lab
    env = {"APP_ENV": "test", "AI_SYNTHETIC_LAB": MARKER, "DATABASE_URL": DATABASE,
           "REDIS_URL": REDIS, "FRONTEND_APP_URL": ORIGIN, "FRONTEND_ORIGINS": ORIGIN,
           "EXTERNAL_IMPORT_ENABLED": "false", "EXTERNAL_REMOVAL_CHECK_ENABLED": "false",
           "AI_LAB_PARSER": "closed-live-synthetic"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError):
            require_lab()
        require_lab(closed_ui=True)
    for change in ({"DATABASE_URL": "production"}, {"AI_LAB_PARSER": "finite"},
                   {"AI_INTENT_EVAL_DEEPSEEK_KEY": "synthetic"}):
        with patch.dict(os.environ, env | change, clear=True), pytest.raises(RuntimeError):
            require_lab(closed_ui=True)


def test_parser_fits_actual_execution_deadline(tmp_path):
    from app.services.ai_search_execution import TextSearchExecution
    parser = parser_at(journal(tmp_path))
    sessions = SimpleNamespace(ledger=SimpleNamespace(policy=SimpleNamespace(running_seconds=60)))
    execution = TextSearchExecution(sessions, parser, None, None)
    assert parser.total_budget_seconds < execution.total_budget_seconds == 15


def test_entry_requires_new_approval_before_key_or_journal_access():
    from lab.closed_ui_entry import create_app
    with (patch("lab.closed_ui_entry.require_lab"), patch.dict(os.environ, {}, clear=True),
          patch("pathlib.Path.read_text", side_effect=AssertionError("key must remain unopened")),
          patch("sqlite3.connect", side_effect=AssertionError("journal must remain unopened")),
          pytest.raises(ProviderFailure, match="LIVE_UI_SMOKE_APPROVAL_REQUIRED")):
        create_app()


def test_entry_validates_existing_journal_before_key_access():
    from lab.closed_ui_entry import create_app
    with (patch("lab.closed_ui_entry.require_lab"), patch.dict(os.environ, {
            "AI_CLOSED_UI_APPROVAL": APPROVAL, "AI_CLOSED_UI_CORPUS_SHA256": CORPUS_SHA256}, clear=True),
          patch("lab.closed_ui_entry.ExistingSmokeBudget", side_effect=ProviderFailure("MISSING_HISTORY")),
          patch("pathlib.Path.read_text", side_effect=AssertionError("key must remain unopened")),
          pytest.raises(ProviderFailure, match="MISSING_HISTORY")):
        create_app()


def test_readable_but_unwritable_existing_journal_fails_before_provider_setup(tmp_path):
    path = journal(tmp_path)
    with (patch("lab.closed_ui.os.access", return_value=False),
          patch("httpx.AsyncHTTPTransport", side_effect=AssertionError("transport must remain uncreated")),
          pytest.raises(ProviderFailure, match="UI_SMOKE_JOURNAL_NOT_WRITABLE")):
        parser_at(path)


async def test_closed_diagnostics_capture_fixed_status_and_code_without_private_values(tmp_path, caplog):
    parser = parser_at(journal(tmp_path))
    private = "NEVER_LOG_PRIVATE_PROVIDER_BODY_OR_TOKEN"
    parser.transport = _UIBudgetTransport(httpx.MockTransport(lambda request: httpx.Response(
        401, text=private, headers={"X-Private": private})), parser.budget)
    case = smoke_cases()[0][0]
    with pytest.raises(ProviderFailure, match="PROVIDER_REQUEST_REJECTED"):
        await parser.parse(case["text"], state(case))
    assert "closed_ui_provider_http_status:401" in caplog.text
    assert "closed_ui_provider_failure:PROVIDER_REQUEST_REJECTED" in caplog.text
    assert private not in caplog.text and case["text"] not in caplog.text
    assert "synthetic-test-only" not in caplog.text


async def test_unknown_dependency_failure_details_do_not_enter_diagnostics(tmp_path, caplog):
    parser = parser_at(journal(tmp_path))
    private = "PRIVATE_UNKNOWN_FAILURE_DETAILS"
    parser.gate.prepare = patch_prepare = AsyncMock(side_effect=ProviderFailure(private))
    case = smoke_cases()[0][0]
    with pytest.raises(ProviderFailure):
        await parser.parse(case["text"], state(case))
    patch_prepare.assert_awaited_once()
    assert "closed_ui_provider_failure:PROVIDER_FAILURE" in caplog.text
    assert private not in caplog.text and parser.budget.summary()["attempts"] == 51
