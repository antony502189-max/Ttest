import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas import searches
from app.schemas.searches import SavedSearchPatch, SavedSearchWrite


def payload(filters: dict) -> dict:
    return {
        "name": "Centro",
        "query": "Santa Cruz",
        "rentalMode": "long",
        "filters": filters,
        "polygon": [],
    }


def test_normal_saved_search_filter_is_valid(monkeypatch):
    settings = Settings(max_saved_search_filter_bytes=16_384, max_saved_search_filter_nodes=500)
    monkeypatch.setattr(searches, "get_settings", lambda: settings)

    search = SavedSearchWrite(
        **payload(
            {
                "price": {"min": 300, "max": 900},
                "amenities": ["Wifi", "Ascensor"],
                "furnished": True,
            }
        )
    )
    assert search.filters["furnished"] is True


def test_saved_search_filter_rejects_oversized_json(monkeypatch):
    settings = Settings(max_saved_search_filter_bytes=256, max_saved_search_filter_nodes=500)
    monkeypatch.setattr(searches, "get_settings", lambda: settings)

    with pytest.raises(ValidationError, match="storage limit"):
        SavedSearchWrite(**payload({"query": "x" * 300}))


def test_saved_search_filter_rejects_excessive_depth(monkeypatch):
    settings = Settings(max_saved_search_filter_bytes=16_384, max_saved_search_filter_nodes=500)
    monkeypatch.setattr(searches, "get_settings", lambda: settings)
    value: dict = {}
    cursor = value
    for _ in range(10):
        nested: dict = {}
        cursor["next"] = nested
        cursor = nested

    with pytest.raises(ValidationError, match="nested too deeply"):
        SavedSearchWrite(**payload(value))


def test_saved_search_filter_rejects_excessive_node_count(monkeypatch):
    settings = Settings(max_saved_search_filter_bytes=100_000, max_saved_search_filter_nodes=500)
    monkeypatch.setattr(searches, "get_settings", lambda: settings)
    value = {"groups": [[index for index in range(100)] for _ in range(6)]}

    with pytest.raises(ValidationError, match="too many values"):
        SavedSearchWrite(**payload(value))


def test_patch_uses_the_same_filter_validation(monkeypatch):
    settings = Settings(max_saved_search_filter_bytes=256, max_saved_search_filter_nodes=500)
    monkeypatch.setattr(searches, "get_settings", lambda: settings)

    with pytest.raises(ValidationError, match="storage limit"):
        SavedSearchPatch(filters={"query": "x" * 300})
