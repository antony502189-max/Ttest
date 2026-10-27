"""Every HTTP call goes through MockTransport; no DNS/network/provider charges."""
import asyncio
import gzip
import json
import time
import tracemalloc
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.schemas.ai_search_intent import Criteria, SearchIntent, apply_patch
from app.services.ai_deepseek_intent import DeepSeekPolicy, OfflineDeepSeekIntent, OutboundIntentInput, ProviderFailure
from app.services.ai_hard_matching import CriterionRules, compile_hard_match, evaluate_hard_match


def current():
    return SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1", session_id=uuid4(), version=7,
                        criteria=Criteria())


class Gate:
    async def prepare(self, text, state):
        return OutboundIntentInput(schema_version="ai-intent-input.v1", provider="deepseek", purpose="intent_patch",
                                   text="sanitized rental request", criteria=state.criteria)


def adapter(handler, **changes):
    policy = {"model": "deepseek-flash", "timeout_seconds": 1.0, "max_tokens": 512,
              "total_budget_seconds": 3.0,
              "max_attempts": 2, "retry_delay_seconds": 0.0, "max_response_bytes": 4096, **changes}
    return OfflineDeepSeekIntent(transport=httpx.MockTransport(handler), key=SecretStr("synthetic-key-not-real"),
                                policy=DeepSeekPolicy(**policy), gate=Gate())


def response(content=None, reason="stop", **changes):
    return {"choices": [{"finish_reason": reason, "message": {"role": "assistant", "content": content or json.dumps({
        "set": {"balcony": {"strength": "hard", "value": True}}, "remove": []})}}], **changes}


async def test_minimized_payload_json_contract_and_server_bound_patch():
    seen = []
    state = current()
    def handler(request):
        seen.append(json.loads(request.content))
        assert request.url == "https://api.deepseek.com/chat/completions"
        assert request.headers["authorization"] == "Bearer synthetic-key-not-real"
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, json=response())
    parser = adapter(handler)
    patch = await parser.parse("PRIVATE_RAW_INPUT", state)
    assert patch.session_id == state.session_id and patch.expected_version == 7 and patch.set.balcony.value
    sent = json.dumps(seen)
    assert "PRIVATE_RAW_INPUT" not in sent and str(state.session_id) not in sent
    assert "sanitized rental request" in sent and seen[0]["response_format"] == {"type": "json_object"}
    assert seen[0]["stream"] is False and "synthetic-key-not-real" not in sent
    assert seen[0]["thinking"] == {"type": "disabled"}
    prompt = seen[0]["messages"][0]["content"]
    assert 'example JSON output: {"set":{"balcony":{"strength":"hard","value":true}},"remove":[]}' in prompt


@pytest.mark.parametrize("code", [429, 500, 503])
async def test_transient_http_status_retries_with_explicit_bound(code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(code if len(calls) == 1 else 200, json=response())
    assert (await adapter(handler).parse("synthetic", current())).set.balcony.value
    assert len(calls) == 2


@pytest.mark.parametrize("code", [301, 307, 400, 401, 403])
async def test_permanent_errors_and_redirects_never_retry_or_follow(code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(code, headers={"Location": "https://example.invalid/steal"}, text="PRIVATE_REMOTE_BODY")
    with pytest.raises(ProviderFailure, match="^PROVIDER_REQUEST_REJECTED$") as error:
        await adapter(handler).parse("synthetic", current())
    assert len(calls) == 1 and "PRIVATE" not in str(error.value)


@pytest.mark.parametrize("content", ["", "not json", "{}", '{"set":{},"set":{},"remove":[]}',
    '{"set":{"balcony":{"strength":"hard","value":"yes"}},"remove":[]}',
    '{"set":{},"remove":[],"session_id":"chosen-by-model"}',
    '{"set":{"balcony":{"strength":"hard","value":true}},"remove":["balcony"]}',
    '{"set":{"balcony":null},"remove":[]}', '{"set":{},"remove":["invented"]}',
    '{"set":{"party":{"strength":"hard","value":NaN}},"remove":[]}'])
async def test_untrusted_json_never_broadens_or_selects_identity(content):
    with pytest.raises(ProviderFailure, match="^PROVIDER_RESULT_INVALID$"):
        await adapter(lambda request: httpx.Response(200, json=response(content=content or " "))).parse("synthetic", current())


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls", "insufficient_system_resource", "aborted"])
async def test_truncation_refusal_and_tool_output_are_failures(reason):
    with pytest.raises(ProviderFailure, match="PROVIDER_RESULT_INVALID"):
        await adapter(lambda request: httpx.Response(200, json=response(reason=reason))).parse("synthetic", current())


async def test_transport_failure_and_response_budget_are_bounded():
    calls = []
    def failed(request):
        calls.append(request)
        raise httpx.ReadTimeout("PRIVATE_REMOTE_ERROR", request=request)
    with pytest.raises(ProviderFailure, match="^PROVIDER_TRANSPORT_FAILED$"):
        await adapter(failed).parse("synthetic", current())
    assert len(calls) == 2
    with pytest.raises(ProviderFailure, match="PROVIDER_RESPONSE_TOO_LARGE"):
        await adapter(lambda request: httpx.Response(200, text="x" * 4097)).parse("synthetic", current())


async def test_gate_failure_happens_before_any_fake_http():
    calls = []
    class Blocked:
        async def prepare(self, text, state):
            raise ValueError("OUTBOUND_PRIVACY_APPROVAL_REQUIRED")
    parser = adapter(lambda request: calls.append(request))
    parser.gate = Blocked()
    with pytest.raises(ValueError, match="OUTBOUND_PRIVACY"):
        await parser.parse("synthetic", current())
    assert not calls


def test_live_transport_is_disabled():
    with pytest.raises(TypeError, match="LIVE_PROVIDER_TRANSPORT_DISABLED"):
        OfflineDeepSeekIntent(transport=None, key=SecretStr("synthetic"), policy=None, gate=None)


@pytest.mark.parametrize("field,value", [("tool_calls", [{"name": "synthetic_tool"}]), ("refusal", "synthetic refusal")])
async def test_tool_or_refusal_fields_are_not_accepted_with_valid_content(field, value):
    body = response()
    body["choices"][0]["message"][field] = value
    with pytest.raises(ProviderFailure, match="PROVIDER_RESULT_INVALID"):
        await adapter(lambda request: httpx.Response(200, json=body)).parse("synthetic", current())


@pytest.mark.parametrize("name", ["pets", "amenities"])
@pytest.mark.parametrize("strength", ["hard", "soft"])
async def test_empty_collections_cannot_remove_existing_criteria(name, strength):
    from ai_facts_pg.typed_match_cases import VOCABULARY, intent, projection
    original = {"pets": {"strength": strength, "value": [{"species": "dog", "size": "small", "count": 1}]},
                "amenities": {"strength": strength, "value": ["synthetic_wifi"]}}
    state = intent(original)
    before = state.model_dump_json()
    bad = {"set": {name: {"strength": strength, "value": []}}, "remove": []}
    with pytest.raises(ValidationError):
        Criteria.model_validate_json(json.dumps(bad["set"]))
    with pytest.raises(ProviderFailure, match="^PROVIDER_RESULT_INVALID$"):
        await adapter(lambda request: httpx.Response(200, json=response(json.dumps(bad)))).parse("synthetic", state)
    assert state.model_dump_json() == before
    if strength == "hard":
        assert evaluate_hard_match(compile_hard_match(state, VOCABULARY), projection([])) == ("pets", "amenities")
        # Only explicit removal can drop one requirement; the other stays hard.
        good = {"set": {}, "remove": [name]}
        patch = await adapter(lambda request: httpx.Response(200, json=response(json.dumps(good)))).parse("synthetic", state)
        result = apply_patch(state, patch)
        assert evaluate_hard_match(compile_hard_match(result, VOCABULARY), projection([])) == (
            "amenities" if name == "pets" else "pets",)


def test_empty_hard_rule_group_fails_before_sql_or_offline_evaluation():
    with pytest.raises(ValueError, match="empty hard criterion"):
        CriterionRules("pets", ())


class RawStream(httpx.AsyncByteStream):
    def __init__(self, chunks, delay=0):
        self.chunks, self.delay, self.reads, self.closed = chunks, delay, 0, False

    async def __aiter__(self):
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            self.reads += 1
            yield chunk

    async def aclose(self):
        self.closed = True


@pytest.mark.parametrize("encoding", ["gzip", "deflate", "br", "identity, gzip"])
async def test_encoded_bomb_is_rejected_without_reading_or_decoding(encoding, monkeypatch):
    import httpx._decoders as decoders
    compressed = gzip.compress(b"x" * 8_388_608)
    stream = RawStream([compressed])
    def forbidden_decode(*args):
        pytest.fail("HTTPX must never decompress the provider response")
    monkeypatch.setattr(decoders.GZipDecoder, "decode", forbidden_decode)
    monkeypatch.setattr(decoders.DeflateDecoder, "decode", forbidden_decode)
    parser = adapter(lambda request: httpx.Response(200, headers={"Content-Encoding": encoding}, stream=stream),
                     max_response_bytes=1024)
    # Fixture construction is outside the measured adapter path. A decoded
    # eight-MiB chunk alone would exceed this generous four-MiB peak bound.
    tracemalloc.start()
    try:
        with pytest.raises(ProviderFailure, match="^PROVIDER_RESPONSE_ENCODING_UNSUPPORTED$"):
            await parser.parse("synthetic", current())
        assert tracemalloc.get_traced_memory()[1] < 4_194_304
    finally:
        tracemalloc.stop()
    assert stream.reads == 0 and stream.closed


async def test_identity_raw_stream_budget_stops_before_extending_or_reading_more():
    stream = RawStream([b"x" * 1000, b"y" * 1000, b"unread"])
    with pytest.raises(ProviderFailure, match="^PROVIDER_RESPONSE_TOO_LARGE$"):
        await adapter(lambda request: httpx.Response(200, stream=stream), max_response_bytes=1024).parse("synthetic", current())
    assert stream.reads == 2 and stream.closed


async def test_slow_chunks_total_deadline_and_stream_cleanup():
    stream = RawStream([b" " for _ in range(100)], delay=.02)
    parser = adapter(lambda request: httpx.Response(200, stream=stream), total_budget_seconds=.05)
    with pytest.raises(ProviderFailure, match="^PROVIDER_DEADLINE_EXCEEDED$"):
        await asyncio.wait_for(parser.parse("synthetic", current()), timeout=1)
    assert stream.reads < 100 and stream.closed


async def test_total_deadline_includes_all_attempts():
    calls = []
    async def handler(request):
        calls.append(request)
        await asyncio.sleep(.03)
        return httpx.Response(503)
    with pytest.raises(ProviderFailure, match="^PROVIDER_DEADLINE_EXCEEDED$"):
        await adapter(handler, total_budget_seconds=.05, max_attempts=3).parse("synthetic", current())
    assert 1 <= len(calls) <= 2


async def test_total_deadline_includes_gate_before_http():
    calls = []
    class SlowGate:
        async def prepare(self, text, state):
            await asyncio.Event().wait()
    parser = adapter(lambda request: calls.append(request), total_budget_seconds=.03)
    parser.gate = SlowGate()
    with pytest.raises(ProviderFailure, match="^PROVIDER_DEADLINE_EXCEEDED$"):
        await parser.parse("synthetic", current())
    assert not calls


async def test_late_synchronous_decode_is_not_accepted_before_timer_delivery(monkeypatch):
    original = OfflineDeepSeekIntent._decode
    def slow(data, state):
        time.sleep(.06)
        return original(data, state)
    monkeypatch.setattr(OfflineDeepSeekIntent, "_decode", staticmethod(slow))
    with pytest.raises(ProviderFailure, match="^PROVIDER_DEADLINE_EXCEEDED$"):
        await adapter(lambda request: httpx.Response(200, json=response()), total_budget_seconds=.03).parse("synthetic", current())


@pytest.mark.parametrize("body", [
    {"set": {}, "remove": []},
    {"set": {}, "remove": ["pets"]},
    {"set": {"balcony": {"strength": "hard", "value": True}}, "remove": []},
])
async def test_empty_or_unchanged_patch_is_not_a_success(body):
    state = current().model_copy(update={"criteria": Criteria.model_validate_json(json.dumps({
        "balcony": {"strength": "hard", "value": True}}))})
    with pytest.raises(ProviderFailure, match="^PROVIDER_RESULT_INVALID$"):
        await adapter(lambda request: httpx.Response(200, json=response(json.dumps(body)))).parse("synthetic", state)


async def test_reordering_conjunctions_and_money_format_do_not_manufacture_change():
    values = {"amenities": {"strength": "hard", "value": ["wifi", "elevator"]},
              "pets": {"strength": "hard", "value": [{"species": "dog", "size": "small", "count": 1},
                                                         {"species": "cat", "size": "small", "count": 1}]},
              "budget": {"strength": "hard", "value": {"amount": "650", "currency": "EUR", "period": "monthly"}}}
    state = current().model_copy(update={"criteria": Criteria.model_validate_json(json.dumps(values))})
    values["amenities"]["value"].reverse()
    values["pets"]["value"].reverse()
    values["budget"]["value"]["amount"] = "650.00"
    with pytest.raises(ProviderFailure, match="^PROVIDER_RESULT_INVALID$"):
        await adapter(lambda request: httpx.Response(200, json=response(json.dumps({"set": values, "remove": []})))).parse("synthetic", state)


@pytest.mark.parametrize("header", ["1", "http-date"])
async def test_retry_after_minimum_is_honored(header, monkeypatch):
    import app.services.ai_deepseek_intent as module
    delays, calls = [], []
    if header == "http-date":
        header = format_datetime(datetime.now(UTC) + timedelta(seconds=2), usegmt=True)
    async def sleep(delay):
        delays.append(delay)
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": header}) if len(calls) == 1 else httpx.Response(200, json=response())
    await adapter(handler).parse("synthetic", current())
    assert len(calls) == 2 and len(delays) == 1 and 0 < delays[0] <= 2
    if header == "1":
        assert delays == [1]


@pytest.mark.parametrize("delay", ["86400", "9" * 129])
async def test_long_retry_after_stops_instead_of_retrying_early(delay):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": delay})
    with pytest.raises(ProviderFailure, match="^PROVIDER_RETRY_BUDGET_EXHAUSTED$"):
        await adapter(handler).parse("synthetic", current())
    assert len(calls) == 1


@pytest.mark.parametrize("length,code", [("99999", "PROVIDER_RESPONSE_TOO_LARGE"),
    ("-1", "PROVIDER_RESPONSE_INVALID_LENGTH"), ("1,2", "PROVIDER_RESPONSE_INVALID_LENGTH")])
async def test_content_length_rejection_does_not_read_body(length, code):
    stream = RawStream([b"unread"])
    with pytest.raises(ProviderFailure, match=f"^{code}$"):
        await adapter(lambda request: httpx.Response(200, headers={"Content-Length": length}, stream=stream)).parse("synthetic", current())
    assert stream.reads == 0 and stream.closed


async def test_exponential_jittered_retry_stays_in_budget(monkeypatch):
    import app.services.ai_deepseek_intent as module
    delays, ceilings, calls = [], [], []
    async def sleep(delay):
        delays.append(delay)
    def jitter(self, low, high):
        ceilings.append(high)
        return high / 2
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    monkeypatch.setattr(module.random.SystemRandom, "uniform", jitter)
    def handler(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json=response())
    await adapter(handler, max_attempts=3, retry_delay_seconds=.1).parse("synthetic", current())
    assert ceilings == [.1, .2] and delays == [.05, .1]


async def test_external_cancellation_is_not_converted_or_retried():
    started = asyncio.Event()
    class Stream(RawStream):
        async def __aiter__(self):
            started.set()
            await asyncio.Event().wait()
            yield b"unreachable"
    stream = Stream([])
    task = asyncio.create_task(adapter(lambda request: httpx.Response(200, stream=stream)).parse("synthetic", current()))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stream.closed
