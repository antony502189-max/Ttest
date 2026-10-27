"""Every HTTP call goes through MockTransport; no DNS/network/provider charges."""
import json
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.schemas.ai_search_intent import Criteria, SearchIntent
from app.services.ai_deepseek_intent import DeepSeekPolicy, OfflineDeepSeekIntent, OutboundIntentInput, ProviderFailure


def current():
    return SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1", session_id=uuid4(), version=7,
                        criteria=Criteria())


class Gate:
    async def prepare(self, text, state):
        return OutboundIntentInput(schema_version="ai-intent-input.v1", provider="deepseek", purpose="intent_patch",
                                   text="sanitized rental request", criteria=state.criteria)


def adapter(handler, **changes):
    policy = {"model": "deepseek-flash", "timeout_seconds": 1.0, "max_tokens": 512,
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
        return httpx.Response(200, json=response())
    parser = adapter(handler)
    patch = await parser.parse("PRIVATE_RAW_INPUT", state)
    assert patch.session_id == state.session_id and patch.expected_version == 7 and patch.set.balcony.value
    sent = json.dumps(seen)
    assert "PRIVATE_RAW_INPUT" not in sent and str(state.session_id) not in sent
    assert "sanitized rental request" in sent and seen[0]["response_format"] == {"type": "json_object"}
    assert seen[0]["stream"] is False and "synthetic-key-not-real" not in sent


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
