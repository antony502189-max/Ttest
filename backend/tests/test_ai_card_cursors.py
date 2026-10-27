import pytest

from app.services.ai_card_cursors import AICardCursors, InvalidAICursor


def test_ai_cursor_signs_raw_cursor_and_subject_intent_context():
    service = AICardCursors(b"synthetic-key-32bytes-not-a-secret")
    assert service.encode(None, "context") is None
    assert service.decode(None, "context") is None
    token = service.encode("manual-cursor", "context")
    assert service.decode(token, "context") == "manual-cursor"
    for bad in (token + "x", token[1:], "manual-cursor", "x" * 1025, "a.b.c", "!.abc"):
        with pytest.raises(InvalidAICursor):
            service.decode(bad, "context")
    with pytest.raises(InvalidAICursor):
        service.decode(token, "different-subject-intent-or-revision")
    with pytest.raises(InvalidAICursor):
        AICardCursors(b"other-synthetic-key32bytes-secret").decode(token, "context")
    with pytest.raises(ValueError):
        AICardCursors(b"short")
