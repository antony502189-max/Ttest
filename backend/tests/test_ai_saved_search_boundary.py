from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.searches import GuestStateImport, SavedSearchPatch, SavedSearchWrite
from app.services.notifications import _saved_search_payload


@pytest.mark.parametrize("filters", [{"ai_intent": {}}, {"aiIntent": {}}, {"ai_search": {}}, {"matcher": "ai.v1"},
    {"schema_version": "ai-search.v1"}, {"intent_hash": "x"}, {"criteria": {}}, {"other": [{"result_ref": "x"}]}])
def test_legacy_write_patch_and_import_reject_reserved_ai_metadata(filters):
    with pytest.raises(ValidationError):
        SavedSearchWrite(rentalMode="long", filters=filters)
    with pytest.raises(ValidationError):
        SavedSearchPatch(filters=filters)
    with pytest.raises(ValidationError):
        GuestStateImport(savedSearches=[{"rentalMode": "long", "filters": filters}])
    # A corrupt historical row cannot make the notifier invoke a broad manual query.
    search = SimpleNamespace(matcher="manual.v1", filters=filters)
    assert _saved_search_payload(search) is None


@pytest.mark.parametrize("matcher", ["ai.v1", "ai.v2", "unknown", None])
def test_unknown_or_typed_matcher_rejected_before_legacy_filter_interpretation(matcher):
    search = SimpleNamespace(id=uuid4(), matcher=matcher, filters={})
    # Missing query/rental/polygon is deliberate: discriminator rejection must
    # happen before reading any legacy semantic field.
    assert _saved_search_payload(search) is None


@pytest.mark.parametrize("field", ["matcher", "ai_intent", "intent_hash", "criteria", "session_id"])
def test_top_level_ai_metadata_cannot_be_ignored_by_legacy_models(field):
    with pytest.raises(ValidationError):
        SavedSearchWrite.model_validate({"rentalMode": "long", field: "PRIVATE"})
    with pytest.raises(ValidationError):
        SavedSearchPatch.model_validate({field: "PRIVATE"})


async def test_ai_and_unknown_notifier_rows_never_reach_manual_sql_or_delivery(monkeypatch):
    from unittest.mock import AsyncMock

    from app.services import notifications

    listing = SimpleNamespace(id=uuid4(), owner_user_id=uuid4())
    searches = [SimpleNamespace(matcher=matcher, filters=filters) for matcher, filters in
                [("ai.v1", {}), ("unknown", {}), ("manual.v1", {"ai_intent": {}})]]
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [
        (search, SimpleNamespace(id=uuid4())) for search in searches])), scalar=AsyncMock())
    manual, delivery = MagicMock(), AsyncMock()
    monkeypatch.setattr(notifications, "listing_price_allowed", lambda value: True)
    monkeypatch.setattr(notifications, "apply_search_filters", manual)
    monkeypatch.setattr(notifications, "create_notification", delivery)
    await notifications.notify_saved_search_matches(session, listing)
    manual.assert_not_called()
    delivery.assert_not_called()
    session.scalar.assert_not_called()
