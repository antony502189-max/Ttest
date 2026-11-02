import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.schemas.ai_search_intent import Criteria, SearchIntent
from app.services.ai_decision_intent import DecisionDeepSeekIntent
from app.services.ai_deepseek_intent import DeepSeekPolicy, ProviderFailure
from app.services.ai_provider_privacy import DeepSeekPrivacyReview, RealUserOutboundDenied, load_review

POLICY = Path(__file__).parents[2] / "deploy/ai-text-lab/deepseek-outbound-review.json"


def test_review_cannot_be_edited_into_activation():
    review = load_review(POLICY)
    assert review.real_user_outbound is False
    for update in ({"real_user_outbound": True}, {"status": "approved"},
                   {"account_training_exclusion": "confirmed"}, {"account_retention_days": 0},
                   {"api_key": "synthetic-canary"}):
        with pytest.raises(ValidationError):
            DeepSeekPrivacyReview.model_validate_json(json.dumps(review.model_dump() | update))


@pytest.mark.parametrize("text", ["my email is private@example.invalid", "one small dog", "обязательно с балконом"])
async def test_real_user_gate_denies_even_innocuous_text_before_transport(text):
    calls = []
    parser = DecisionDeepSeekIntent(transport=httpx.MockTransport(lambda r: calls.append(r)),
        key=SecretStr("synthetic-canary"), gate=RealUserOutboundDenied(),
        policy=DeepSeekPolicy(model="deepseek-flash", timeout_seconds=1, total_budget_seconds=2,
            max_tokens=1024, max_attempts=1, retry_delay_seconds=0, max_response_bytes=65536))
    state = SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1",
                         session_id=uuid4(), version=7, criteria=Criteria())
    with pytest.raises(ProviderFailure, match="^REAL_USER_OUTBOUND_NOT_APPROVED$"):
        await parser.parse(text, state)
    assert not calls


def test_decision_adapter_rejects_live_transport():
    with pytest.raises(TypeError, match="LIVE_PROVIDER_TRANSPORT_DISABLED"):
        DecisionDeepSeekIntent(transport=httpx.AsyncHTTPTransport(), key=SecretStr("synthetic"),
                              gate=RealUserOutboundDenied(), policy=None)
