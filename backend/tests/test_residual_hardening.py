import pytest
from pydantic import ValidationError

from app.main import app, rate_rule
from app.schemas.auth import LoginRequest

PAGINATED_GETS = (
    "/api/v1/messages/threads",
    "/api/v1/messages/threads/{thread_id}",
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
