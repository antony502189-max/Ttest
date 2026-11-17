import base64
import json
from uuid import uuid4

import pytest

from app.repositories.ai_search_sessions import CommittedIntent
from app.schemas.ai_search_intent import Criteria, SearchIntent
from app.services.ai_saved_handoff import SavedHandoffError, SavedHandoffSigner


def committed():
    return CommittedIntent(result_ref=uuid4(), count=1, intent_hash="a" * 64,
        intent=SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1",
            session_id=uuid4(), version=7, criteria=Criteria.model_validate_json(json.dumps({
                "geography": {"strength": "hard", "value": {"province_code": "38", "municipality_code": "38023"}},
                "budget": {"strength": "hard", "value": {"amount": "700", "currency": "EUR", "period": "monthly"}},
                "furnished": {"strength": "hard", "value": False}}))))


def test_handoff_copies_committed_criteria_without_ownership_or_quota_authority():
    original = committed()
    signer = SavedHandoffSigner(b"s" * 32)
    token = signer.issue(original, now=1000)
    body = signer.verify(token, now=1299)
    assert body.intent.criteria == original.intent.criteria
    assert body.intent.criteria.furnished.value is False
    assert body.result_ref == original.result_ref
    raw = base64.urlsafe_b64decode(token.split(".")[0] + "=" * (-len(token.split(".")[0]) % 4)).decode()
    assert str(original.intent.session_id) not in raw and "subject" not in raw and "quota" not in raw
    assert "geography" not in repr(body)
    assert set(json.loads(raw)) == {"schema_version", "issuer", "purpose", "result_ref", "intent", "issued_at", "expires_at"}


def test_handoff_preserves_total_only_party_without_inventing_age_composition():
    data = committed().model_dump(mode="json", exclude_none=True)
    data["intent"]["criteria"]["party"] = {"strength": "hard", "value": {"persons": 1}}
    original = CommittedIntent.model_validate_json(json.dumps(data))
    signer = SavedHandoffSigner(b"s" * 32)
    restored = signer.verify(signer.issue(original, now=1000), now=1001)
    assert restored.intent.criteria == original.intent.criteria
    assert restored.intent.criteria.party.value.model_dump() == {"persons": 1}


@pytest.mark.parametrize("now,code", [(1300, "EXPIRED"), (1400, "EXPIRED"), (969, "CLOCK_INVALID")])
def test_expiry_and_clock_are_not_extended_by_retry(now, code):
    signer = SavedHandoffSigner(b"s" * 32)
    with pytest.raises(SavedHandoffError, match=code):
        signer.verify(signer.issue(committed(), now=1000), now=now)


@pytest.mark.parametrize("mutate", [
    lambda t: t + ".extra", lambda t: t + "=", lambda t: " " + t,
    lambda t: t.replace(t[0], "!", 1), lambda t: t.split(".")[0] + "." + "A" * 43,
    lambda t: "é", lambda t: "A" * 32769, lambda t: None,
])
def test_tamper_malformed_or_cross_protocol_input_is_fixed_private_error(mutate):
    signer = SavedHandoffSigner(b"s" * 32)
    with pytest.raises(SavedHandoffError, match="^AI_HANDOFF_INVALID$"):
        signer.verify(mutate(signer.issue(committed(), now=1000)), now=1001)


def test_independent_signing_key_and_snapshot_validation():
    signer = SavedHandoffSigner(b"s" * 32)
    token = signer.issue(committed(), now=1000)
    with pytest.raises(SavedHandoffError, match="INVALID"):
        SavedHandoffSigner(b"t" * 32).verify(token, now=1001)
    for key in (b"", b"s" * 31, b"s" * 33):
        with pytest.raises(SavedHandoffError, match="KEY_REQUIRED"):
            SavedHandoffSigner(key)
