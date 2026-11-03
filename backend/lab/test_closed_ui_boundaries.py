import asyncio
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
import yaml
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.schemas.ai_search_intent import Criteria
from app.services.ai_deepseek_intent import ProviderFailure
from lab.closed_ui import ExistingSmokeBudget, _UIBudgetTransport, smoke_cases
from lab.closed_ui_authorization import canonical, host_preflight, verify
from lab.closed_ui_test_support import SOURCE, admission_fixture, signed_fixture
from lab.decision_fixtures import FIXTURES
from lab.decision_parser import completion
from lab.intent_eval import state
from lab.runtime_contract import ATTESTATION, LabRuntime, RuntimePairing
from lab.test_closed_ui import journal, parser_at


def test_copied_or_replaced_journal_cannot_reuse_original_signed_admission(tmp_path):
    original = journal(tmp_path)
    proof = admission_fixture(original)
    copy = tmp_path / "DISPOSABLE-copy.sqlite3"
    shutil.copyfile(original, copy)
    for path in (copy,):
        with pytest.raises(ProviderFailure, match="JOURNAL_IDENTITY_MISMATCH"):
            ExistingSmokeBudget(path, corpus_sha256=proof.data["corpus_sha256"], admission=proof)
        with pytest.raises(ProviderFailure, match="JOURNAL_IDENTITY_MISMATCH"):
            host_preflight(proof, path, proof.data["backend_image"], proof.data["frontend_image"])
    original.unlink()
    shutil.copyfile(copy, original)
    # Filesystem may recycle inode after unlink; hold the old original via rename
    # in the separate replacement regression below for a deterministic identity.
    if original.stat().st_ino != proof.data["runtime_journal"]["inode"]:
        with pytest.raises(ProviderFailure, match="JOURNAL_IDENTITY_MISMATCH"):
            proof.check_journal(original)


def test_same_path_replacement_and_later_file_swap_fail_before_reserve(tmp_path):
    original = journal(tmp_path)
    proof = admission_fixture(original)
    budget = ExistingSmokeBudget(original, corpus_sha256=proof.data["corpus_sha256"], admission=proof)
    moved = tmp_path / "DISPOSABLE-retained-original.sqlite3"
    original.rename(moved)
    shutil.copyfile(moved, original)
    with pytest.raises(ProviderFailure, match="JOURNAL_IDENTITY_MISMATCH"):
        budget.reserve("ru-balcony")


@pytest.mark.parametrize("change", ["source", "signature", "pin", "expiry", "external_cap", "baseline_prior"])
def test_release_authorization_is_not_a_public_approval_string(tmp_path, change):
    path = journal(tmp_path)
    options = {}
    if change == "expiry":
        options = {"issued_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
                   "expires_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat()}
    if change == "external_cap":
        options = {"external_cap_evidence_sha256": ""}
    if change == "baseline_prior":
        options = {"baseline_attempts": 52, "baseline_reserved_micro_usd": 575120,
                   "max_new_attempts": 2, "max_new_reserved_micro_usd": 22120,
                   "case_ids": ["es-monthly", "en-negation"]}
    document, public, pin = signed_fixture(path, **options)
    if change == "signature":
        envelope = json.loads(document)
        envelope["payload"]["authorization_id"] = "e" * 32
        document = canonical(envelope)
    with pytest.raises(ProviderFailure):
        verify(document, public, trusted_key_sha256="0" * 64 if change == "pin" else pin,
               source="f" * 40 if change == "source" else SOURCE)


def test_host_rejects_wrong_images_and_journal_origin_even_with_valid_signature(tmp_path):
    path = journal(tmp_path)
    proof = admission_fixture(path)
    with pytest.raises(ProviderFailure, match="IMAGE_IDENTITY_MISMATCH"):
        host_preflight(proof, path, "sha256:" + "e" * 64, proof.data["frontend_image"])


@pytest.mark.parametrize("backend_mode", ["decision-transport-fixture", "closed-live-synthetic"])
@pytest.mark.parametrize("frontend_mode", ["decision-transport-fixture", "closed-live-synthetic"])
async def test_real_asgi_pairing_matrix_stops_mismatch_before_fake_paid_transport(tmp_path, backend_mode, frontend_mode):
    parser = parser_at(journal(tmp_path))
    calls = []
    def fake_paid(request):
        calls.append(request)
        return httpx.Response(503)
    parser.transport = _UIBudgetTransport(httpx.MockTransport(fake_paid), parser.budget)
    runtime = LabRuntime.create(backend_mode, SOURCE, "mock")
    async def query(request):
        case = smoke_cases()[0][0]
        try:
            await parser.parse(case["text"], state(case))
        except ProviderFailure:
            pass
        return JSONResponse({"query_entered": True})
    app = Starlette(routes=[Route("/api/v1/ai-search/query", query, methods=["POST"])])
    app.state.ai_lab_runtime = runtime
    app.add_middleware(RuntimePairing)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://localhost:9443") as client:
        actual = await client.get(ATTESTATION)
        assert actual.json() == runtime.public()
        assert actual.headers["cache-control"] == "no-store"
        headers = runtime.headers() | {"X-AI-Lab-Mode": frontend_mode}
        result = await client.post("/api/v1/ai-search/query", headers=headers)
    matched = backend_mode == frontend_mode
    assert result.status_code == (200 if matched else 409)
    assert len(calls) == int(matched)
    assert parser.budget.summary()["attempts"] == 51 + int(matched)


@pytest.mark.parametrize("field", ["X-AI-Lab-Source", "X-AI-Lab-Instance", "X-AI-Lab-Mode"])
async def test_stale_source_or_instance_and_unlabelled_frontend_are_rejected(field):
    app = Starlette()
    runtime = LabRuntime.create("closed-live-synthetic", SOURCE, "mock")
    app.state.ai_lab_runtime = runtime
    app.add_middleware(RuntimePairing)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://localhost:9443") as client:
        assert (await client.post("/api/v1/ai-search/sessions")).status_code == 409
        headers = runtime.headers() | {field: "stale"}
        assert (await client.post("/api/v1/ai-search/query", headers=headers)).status_code == 409
        assert not (await client.get("/api/v1/ai-search/capabilities", headers=headers)).json()["text"]


@pytest.mark.parametrize("variant", ["pii", "space", "state", "version"])
async def test_unapproved_outbound_rejected_before_any_reservation(tmp_path, variant):
    parser = parser_at(journal(tmp_path))
    parser.transport = _UIBudgetTransport(httpx.MockTransport(lambda req: pytest.fail("paid IO")), parser.budget)
    case = smoke_cases()[0][0]
    current, text = state(case), case["text"]
    if variant == "pii":
        text = "private biography health contact@example.invalid"
    elif variant == "space":
        text += " "
    elif variant == "version":
        current = current.model_copy(update={"version": 1})
    else:
        current = state(smoke_cases()[0][1]).model_copy(update={"criteria": Criteria.model_validate_json(
                '{"rental_mode":{"strength":"hard","value":"holiday"}}')})
    with pytest.raises(ProviderFailure):
        await parser.parse(text, current)
    assert parser.budget.summary()["attempts"] == 51


def test_fixture_vocabulary_does_not_read_live_corpus_or_depend_on_its_hash():
    with patch("lab.closed_ui.load_corpus", side_effect=AssertionError("unrelated LIVE corpus IO")):
        assert completion("Обязательно с балконом.", {})["patch"]["set"] == FIXTURES["Обязательно с балконом."]
        assert completion("ничего не менять", {})["status"] == "no_change"
    for case in smoke_cases()[0]:
        assert FIXTURES[case["text"]] == case["expected"]


def test_compose_override_requires_external_admission_and_keeps_it_backend_only():
    root = Path(__file__).resolve().parents[2]
    override = yaml.safe_load((root / "deploy/ai-text-lab/closed-ui.override.yml").read_text(encoding="utf-8"))
    assert set(override["services"]) == {"backend"}
    backend = override["services"]["backend"]
    assert "AI_CLOSED_UI_AUTHORITY_SHA256" in backend["environment"]
    mounts = {v["target"]: v for v in backend["volumes"]}
    assert mounts["/closed-ui-admission"]["read_only"]
    assert mounts["/closed-ui-secrets/dedicated-key.env"]["read_only"]
    assert all(not mount["bind"]["create_host_path"] for mount in mounts.values())


@pytest.mark.parametrize("fault", ["429", "500", "disconnect", "cancel", "malformed", "too_large", "usage_over", "timeout"])
async def test_each_failed_http_attempt_keeps_its_case_consumed_without_retry(tmp_path, fault):
    parser = parser_at(journal(tmp_path))
    calls = []
    async def handle(request):
        calls.append(True)
        if fault == "disconnect":
            raise httpx.ReadError("ambiguous acknowledgement")
        if fault == "cancel":
            raise asyncio.CancelledError
        if fault == "timeout":
            await asyncio.sleep(.2)
        if fault in {"429", "500"}:
            return httpx.Response(int(fault))
        if fault == "too_large":
            return httpx.Response(200, content=b"x" * 65537)
        if fault == "usage_over":
            return httpx.Response(200, json={"usage": {
                "prompt_tokens": 32769, "completion_tokens": 1, "total_tokens": 32770}})
        return httpx.Response(200, json={"invalid": True})
    if fault == "timeout":
        parser.policy = parser.policy.model_copy(update={"total_budget_seconds": .02})
    parser.transport = _UIBudgetTransport(httpx.MockTransport(handle), parser.budget)
    case = smoke_cases()[0][0]
    with pytest.raises(asyncio.CancelledError if fault == "cancel" else ProviderFailure):
        await parser.parse(case["text"], state(case))
    assert parser.budget.summary()["attempts"] == 52
    with pytest.raises(ProviderFailure, match="CASE_ALREADY_ATTEMPTED"):
        await parser.parse(case["text"], state(case))
    assert len(calls) == 1 and parser.budget.summary()["attempts"] == 52


def test_new_signed_document_cannot_rename_the_existing_journal_origin(tmp_path):
    path = journal(tmp_path)
    original = admission_fixture(path)
    ExistingSmokeBudget(path, corpus_sha256=original.data["corpus_sha256"], admission=original).reserve("ru-balcony")
    renamed = admission_fixture(path, journal_id="0" * 32)
    with pytest.raises(ProviderFailure, match="JOURNAL_IDENTITY_MISMATCH"):
        ExistingSmokeBudget(path, corpus_sha256=renamed.data["corpus_sha256"], admission=renamed).reserve("es-monthly")


async def test_competing_owned_sessions_cannot_spend_three_slots_on_one_case(tmp_path):
    parser = parser_at(journal(tmp_path))
    seen = []
    cases = smoke_cases()[0]
    async def fake_paid(request):
        data = json.loads(json.loads(request.content)["messages"][1]["content"])
        case = next(c for c in cases if c["text"] == data["text"])
        seen.append(case["id"])
        await asyncio.sleep(.01)
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps({"status": "patch", "patch": {
                "set": case["expected"], "remove": []}})}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})
    parser.transport = _UIBudgetTransport(httpx.MockTransport(fake_paid), parser.budget)
    results = await asyncio.gather(*(parser.parse(case["text"], state(case).model_copy(
        update={"session_id": uuid4()})) for case in [cases[0]] * 6 + cases[1:]), return_exceptions=True)
    assert sorted(seen) == sorted(c["id"] for c in cases)
    assert sum(isinstance(result, ProviderFailure) for result in results) == 5
    assert parser.budget.summary()["attempts"] == 54
