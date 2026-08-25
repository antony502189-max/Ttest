import pytest
from pydantic import ValidationError

from app.main import app, rate_limit_rule, rate_rule
from app.schemas.auth import LoginRequest
from app.schemas.searches import SavedSearchPatch

PAGINATED_GETS = (
    "/api/v1/notifications",
    "/api/v1/reports",
    "/api/v1/admin/listings",
    "/api/v1/admin/users",
    "/api/v1/admin/external-import/runs",
    "/api/v1/listings/mine",
)


def test_login_password_is_bounded_before_argon2_work():
    parsed = LoginRequest(email="user@example.com", password="x" * 256)
    assert len(parsed.password) == 256
    with pytest.raises(ValidationError):
        LoginRequest(email="user@example.com", password="x" * 257)


def test_every_offset_endpoint_has_a_hard_upper_bound():
    schema = app.openapi()
    for path in PAGINATED_GETS:
        parameters = schema["paths"][path]["get"]["parameters"]
        offset = next(item for item in parameters if item["name"] == "offset" and item["in"] == "query")
        assert offset["schema"]["maximum"] == 10_000, path


def test_listing_collection_mutations_are_rate_limited():
    assert rate_rule("PUT", "/api/v1/favorites/00000000-0000-4000-8000-000000000001") == (60, 60)
    assert rate_rule("PUT", "/api/v1/discarded-listings/00000000-0000-4000-8000-000000000001") == (60, 60)
    assert rate_rule("POST", "/api/v1/account/import-guest-state") == (5, 60)


def test_dynamic_rate_limits_share_stable_buckets_and_cover_deletes():
    favorite_one = rate_limit_rule("PUT", "/api/v1/favorites/00000000-0000-4000-8000-000000000001")
    favorite_two = rate_limit_rule("PUT", "/api/v1/favorites/00000000-0000-4000-8000-000000000002")
    assert favorite_one == favorite_two == ("/api/v1/favorites/{listing_id}", 60, 60)
    assert rate_limit_rule(
        "DELETE",
        "/api/v1/favorites/00000000-0000-4000-8000-000000000003",
    ) == ("/api/v1/favorites/{listing_id}", 60, 60)
    assert rate_limit_rule(
        "DELETE",
        "/api/v1/discarded-listings/00000000-0000-4000-8000-000000000004",
    ) == ("/api/v1/discarded-listings/{listing_id}", 60, 60)
    assert rate_limit_rule("DELETE", "/api/v1/discarded-listings") == (
        "/api/v1/discarded-listings",
        60,
        60,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"name": None},
        {"query": None},
        {"filters": None},
        {"polygon": None},
        {"alertsEnabled": None},
    ],
)
def test_saved_search_patch_rejects_explicit_nulls(payload):
    with pytest.raises(ValidationError):
        SavedSearchPatch.model_validate(payload)
