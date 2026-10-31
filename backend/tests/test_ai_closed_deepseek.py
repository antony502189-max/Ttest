"""Offline certification of closed provider and semantic evaluator; no paid IO."""
import asyncio
import json
import ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pydantic import SecretStr

from app.services.ai_closed_deepseek import (
    APPROVAL,
    INPUT_TOKEN_ALLOWANCE,
    MAX_CALLS,
    MAX_MICRO_USD,
    POLICY,
    RESERVE_MICRO_USD,
    ClosedDeepSeekIntent,
    EvaluationBudget,
    _BudgetTransport,
)
from app.services.ai_deepseek_intent import ProviderFailure
from lab.intent_eval import SyntheticCorpusGate, evaluate, load_corpus, manifest, state


def completion(*, status="patch", patch=None, usage=None):
    if status == "patch" and patch is None:
        patch = {"set": {"balcony": {"strength": "hard", "value": True}}, "remove": []}
    return {"model": "deepseek-flash", "choices": [{"finish_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps({"status": status, "patch": patch})}}],
        "usage": usage or {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}}


def setup(tmp_path, handler):
    cases, digest = load_corpus()
    budget = EvaluationBudget(tmp_path / "budget.sqlite3", corpus_sha256=digest)
    parser = ClosedDeepSeekIntent(key=SecretStr("synthetic-test-secret"), gate=SyntheticCorpusGate(cases),
                                  budget=budget, approval=APPROVAL)
    # Only the test replaces the real transport; no configurable production URL.
    parser.transport = _BudgetTransport(httpx.MockTransport(handler), budget)
    return parser, budget, cases


async def test_closed_parse_real_composition_contract_and_minimal_outbound(tmp_path):
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        assert request.url == "https://api.deepseek.com/chat/completions"
        assert request.headers["authorization"] == "Bearer synthetic-test-secret"
        return httpx.Response(200, json=completion())
    parser, budget, cases = setup(tmp_path, handler)
    patch = await parser.parse(cases[0]["text"], state(cases[0]))
    assert patch.session_id == state(cases[0]).session_id and patch.expected_version == 0
    outbound = json.loads(seen[0]["messages"][1]["content"])
    assert outbound == {"text": cases[0]["text"], "criteria": {}}
    assert seen[0]["max_tokens"] == 1024 and seen[0]["thinking"] == {"type": "disabled"}
    serialized = json.dumps(seen)
    for private in ("synthetic-test-secret", str(patch.session_id), "ru-balcony", '"expected":'):
        assert private not in serialized
    assert budget.summary() == {"attempts": 1, "reserved_micro_usd": RESERVE_MICRO_USD,
        "observed_usage_attempts": 1, "prompt_tokens": 100, "completion_tokens": 20, "observed_peak_micro_usd": 54}


async def test_gate_blocks_arbitrary_text_and_modified_state_before_io(tmp_path):
    calls = []
    parser, budget, cases = setup(tmp_path, lambda request: calls.append(request))
    with pytest.raises(ProviderFailure, match="SYNTHETIC_OUTBOUND_CASE_NOT_APPROVED"):
        await parser.parse("private user message", state(cases[0]))
    with pytest.raises(ProviderFailure, match="SYNTHETIC_OUTBOUND_CASE_NOT_APPROVED"):
        await parser.parse(cases[0]["text"], state(cases[3]))
    assert not calls and budget.summary()["attempts"] == 0


async def test_retry_reserves_before_each_attempt_and_does_not_refund(tmp_path):
    seen = []
    parser, budget, cases = setup(tmp_path, lambda request: httpx.Response(503))
    def handler(request):
        seen.append(budget.summary()["attempts"])
        return httpx.Response(503) if len(seen) == 1 else httpx.Response(200, json=completion())
    parser.transport = _BudgetTransport(httpx.MockTransport(handler), budget)
    await parser.parse(cases[0]["text"], state(cases[0]))
    assert seen == [1, 2]
    resumed = EvaluationBudget(budget.path, corpus_sha256=load_corpus()[1])
    assert resumed.summary()["reserved_micro_usd"] == 2 * RESERVE_MICRO_USD
    assert resumed.summary()["observed_usage_attempts"] == 1
    assert b"synthetic-test-secret" not in budget.path.read_bytes()
    assert cases[0]["text"].encode() not in budget.path.read_bytes()


def test_durable_atomic_budget_fences_concurrent_process_equivalent_connections(tmp_path):
    budget = EvaluationBudget(tmp_path / "budget.sqlite3", corpus_sha256="synthetic")
    def reserve(_):
        try:
            return budget.reserve()
        except ProviderFailure as error:
            assert str(error) == "PROVIDER_COST_BUDGET_EXHAUSTED"
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        tickets = list(pool.map(reserve, range(MAX_CALLS + 16)))
    assert len(set(tickets) - {None}) == MAX_CALLS
    assert budget.summary()["reserved_micro_usd"] == MAX_CALLS * RESERVE_MICRO_USD <= MAX_MICRO_USD
    with pytest.raises(ProviderFailure, match="JOURNAL_MISMATCH"):
        EvaluationBudget(budget.path, corpus_sha256="different-corpus")


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens": True, "completion_tokens": 0, "total_tokens": 1},
    {"prompt_tokens": 100, "completion_tokens": 1, "total_tokens": 900},
    {"prompt_tokens": -1, "completion_tokens": 1, "total_tokens": 0}])
async def test_missing_or_invalid_usage_is_not_a_success(tmp_path, usage):
    body = completion()
    body["usage"] = usage
    parser, budget, cases = setup(tmp_path, lambda request: httpx.Response(200, json=body))
    with pytest.raises(ProviderFailure, match="PROVIDER_USAGE_INVALID"):
        await parser.parse(cases[0]["text"], state(cases[0]))
    assert budget.summary()["attempts"] == 1


async def test_usage_overrun_poison_budget_and_prevents_further_http(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=completion(usage={"prompt_tokens": INPUT_TOKEN_ALLOWANCE + 1,
            "completion_tokens": 1, "total_tokens": INPUT_TOKEN_ALLOWANCE + 2}))
    parser, budget, cases = setup(tmp_path, handler)
    with pytest.raises(ProviderFailure, match="PROVIDER_USAGE_ALLOWANCE_EXCEEDED"):
        await parser.parse(cases[0]["text"], state(cases[0]))
    with pytest.raises(ProviderFailure, match="PROVIDER_COST_BUDGET_EXHAUSTED"):
        await parser.parse(cases[0]["text"], state(cases[0]))
    assert len(calls) == 1 and budget.summary()["reserved_micro_usd"] == MAX_MICRO_USD


@pytest.mark.parametrize("status,code", [("clarification", "INTENT_CLARIFICATION_REQUIRED"),
    ("no_change", "INTENT_NO_CHANGE"), ("unsupported", "INTENT_UNSUPPORTED")])
async def test_non_patch_decisions_never_generate_a_search(tmp_path, status, code):
    parser, _, cases = setup(tmp_path, lambda request: httpx.Response(200, json=completion(status=status)))
    with pytest.raises(ProviderFailure, match=f"^{code}$"):
        await parser.parse(cases[0]["text"], state(cases[0]))


@pytest.mark.parametrize("change", ["patch_on_clarify", "empty_patch", "identity", "refusal", "truncated"])
async def test_decision_schema_and_base_guards_fail_closed(tmp_path, change):
    body = completion()
    message = body["choices"][0]["message"]
    if change == "patch_on_clarify":
        decision = json.loads(message["content"])
        decision["status"] = "clarification"
        message["content"] = json.dumps(decision)
    elif change == "empty_patch":
        message["content"] = json.dumps({"status": "patch", "patch": {"set": {}, "remove": []}})
    elif change == "identity":
        decision = json.loads(message["content"])
        decision["patch"]["session_id"] = "invented"
        message["content"] = json.dumps(decision)
    elif change == "refusal":
        message["refusal"] = "private body"
    else:
        body["choices"][0]["finish_reason"] = "length"
    parser, _, cases = setup(tmp_path, lambda request: httpx.Response(200, json=body))
    with pytest.raises(ProviderFailure, match="^PROVIDER_RESULT_INVALID$"):
        await parser.parse(cases[0]["text"], state(cases[0]))


async def test_valid_typed_json_with_wrong_meaning_fails_semantic_evaluation(tmp_path):
    wrong = {"set": {"budget": {"strength": "hard", "value": {
        "amount": "600", "currency": "EUR", "period": "nightly"}}}, "remove": []}
    parser, _, cases = setup(tmp_path, lambda request: httpx.Response(200, json=completion(patch=wrong)))
    result = await evaluate(parser, [cases[4]])
    assert result["typed_patch_count"] == 1 and result["passed"] == 0 and not result["all_passed"]
    assert result["results"][0]["different_criteria"] == ["budget"]


async def test_evaluator_rejects_false_acceptance_and_transport_failure(tmp_path):
    parser, _, cases = setup(tmp_path, lambda request: httpx.Response(200, json=completion()))
    result = await evaluate(parser, [cases[7], cases[15], cases[18]])
    assert result["passed"] == 0
    class Failed:
        async def parse(self, *args):
            raise ProviderFailure("PROVIDER_REQUEST_REJECTED")
    result = await evaluate(Failed(), [cases[7]])
    assert result["passed"] == 0


async def test_cancellation_keeps_reservation_and_closes_transport(tmp_path):
    entered = asyncio.Event()
    async def handler(request):
        entered.set()
        await asyncio.Event().wait()
    parser, budget, cases = setup(tmp_path, handler)
    task = asyncio.create_task(parser.parse(cases[0]["text"], state(cases[0])))
    await asyncio.wait_for(entered.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert budget.summary()["attempts"] == 1 and budget.summary()["observed_usage_attempts"] == 0


@pytest.mark.parametrize("url", ["http://api.deepseek.com/chat/completions", "https://example.invalid/steal",
    "https://api.deepseek.com/chat/completions?api_key=secret"])
async def test_transport_only_allows_fixed_https_destination(tmp_path, url):
    _, budget, _ = setup(tmp_path, lambda request: None)
    transport = _BudgetTransport(httpx.MockTransport(lambda request: None), budget)
    with pytest.raises(ProviderFailure, match="PROVIDER_DESTINATION_REJECTED"):
        await transport.handle_async_request(httpx.Request("POST", url))
    assert budget.summary()["attempts"] == 0


def test_explicit_activation_and_real_transport_factory(tmp_path):
    cases, digest = load_corpus()
    budget = EvaluationBudget(tmp_path / "budget.sqlite3", corpus_sha256=digest)
    for key, approval, code in [(SecretStr("synthetic"), "", "APPROVAL_REQUIRED"),
                               (SecretStr(""), APPROVAL, "TEST_KEY_REQUIRED")]:
        with pytest.raises(ProviderFailure, match=code):
            ClosedDeepSeekIntent(key=key, gate=SyntheticCorpusGate(cases), budget=budget, approval=approval)
    parser = ClosedDeepSeekIntent(key=SecretStr("synthetic"), gate=SyntheticCorpusGate(cases),
                                  budget=budget, approval=APPROVAL)
    assert isinstance(parser.transport.inner, httpx.AsyncHTTPTransport)
    plan = manifest(cases, digest)
    assert plan["live_calls_made"] == 0 and plan["cases"] == 24 and len(digest) == 64
    assert POLICY.max_attempts == 2


@pytest.mark.parametrize("variant", ["no_approval", "wrong_hash", "no_key"])
async def test_live_cli_requires_all_explicit_gates_before_transport_construction(tmp_path, monkeypatch, variant):
    import lab.intent_eval as cli
    _, digest = load_corpus()
    args = ["intent_eval", "--live", "--output", str(tmp_path / "result.json"),
            "--journal", str(tmp_path / "budget.sqlite3"), "--approval",
            "" if variant == "no_approval" else APPROVAL, "--approved-corpus-sha256",
            "wrong" if variant == "wrong_hash" else digest]
    monkeypatch.setattr("sys.argv", args)
    monkeypatch.setenv("AI_INTENT_EVAL_DEEPSEEK_KEY", "" if variant == "no_key" else "synthetic")
    def forbidden(**kwargs):
        raise AssertionError("must not construct transport before authorization/key validation")
    monkeypatch.setattr(cli, "ClosedDeepSeekIntent", forbidden)
    with pytest.raises(SystemExit) as error:
        await cli.main()
    assert error.value.code == 2
    assert not (tmp_path / "budget.sqlite3").exists()
    assert not (tmp_path / "result.json").exists()


def tls_contexts(tmp_path, *, trusted):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "api.deepseek.com")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
        .not_valid_after(datetime.now(UTC) + timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("api.deepseek.com")]), critical=False)
        .sign(key, hashes.SHA256()))
    pem, secret = tmp_path / "certificate.pem", tmp_path / "tls-key.pem"
    pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    secret.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()))
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(pem, secret)
    client = ssl.create_default_context(cafile=str(pem) if trusted else None)
    return server, client


@pytest.mark.parametrize("trusted", [True, False])
async def test_real_httpx_tls_wire_on_loopback_without_provider_network(tmp_path, trusted):
    """Real sockets/TLS/HTTPX, routed to a local TLS server by a TEST-ONLY backend.

    The production factory keeps CA/hostname verification and the fixed HTTPS
    destination. No new URL/DNS/verify override is exposed by the application.
    """
    server_tls, client_tls = tls_contexts(tmp_path, trusted=trusted)
    seen = []
    async def serve(reader, writer):
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(int(line.split(b":", 1)[1]) for line in headers.split(b"\r\n")
                          if line.lower().startswith(b"content-length:"))
            payload = json.loads(await reader.readexactly(length))
            seen.append((headers, payload))
            body = json.dumps(completion()).encode()
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                         + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
    server = await asyncio.start_server(serve, "127.0.0.1", 0, ssl=server_tls)
    port = server.sockets[0].getsockname()[1]
    parser, budget, cases = setup(tmp_path, lambda request: None)
    inner = httpx.AsyncHTTPTransport(verify=client_tls, trust_env=False, retries=0)
    original_backend = inner._pool._network_backend
    class LoopbackBackend:
        async def connect_tcp(self, host, port, **kwargs):
            assert host == "api.deepseek.com" and port == 443
            return await original_backend.connect_tcp(host="127.0.0.1", port=local_port, **kwargs)
    local_port = port
    inner._pool._network_backend = LoopbackBackend()
    parser.transport = _BudgetTransport(inner, budget)
    try:
        async with server:
            if trusted:
                for _ in range(2):  # Transport can be reused across independently bounded parses.
                    patch = await parser.parse(cases[0]["text"], state(cases[0]))
                    assert patch.set.balcony.value is True
                assert len(seen) == 2 and budget.summary()["observed_usage_attempts"] == 2
                assert b"Host: api.deepseek.com" in seen[0][0]
                assert seen[0][1]["model"] == "deepseek-flash"
            else:
                with pytest.raises(ProviderFailure, match="^PROVIDER_TRANSPORT_FAILED$"):
                    await parser.parse(cases[0]["text"], state(cases[0]))
                assert not seen and budget.summary()["attempts"] == 2
    finally:
        server.close()
        await server.wait_closed()
        await inner.aclose()
