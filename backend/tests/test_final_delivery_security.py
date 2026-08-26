from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.main import app
from app.schemas.auth import UserResponse, UserUpdateRequest
from app.schemas.listings import ListingResponse
from app.services.listings import canonical_email, require_hard_delete_authorization


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" Antony502189@GMAIL.COM ", "antony502189@gmail.com"),
        ("\ttf.shuler@gmail.com\n", "tf.shuler@gmail.com"),
    ],
)
def test_hard_delete_email_is_canonicalized_from_server_identity(raw: str, expected: str) -> None:
    assert canonical_email(raw) == expected
    require_hard_delete_authorization(SimpleNamespace(email=raw, email_verified=True))


@pytest.mark.parametrize("email", ["renter@example.test", "owner@example.test", "antony502189@gmail.co"])
def test_hard_delete_rejects_every_non_allowlisted_identity(email: str) -> None:
    with pytest.raises(HTTPException) as error:
        require_hard_delete_authorization(SimpleNamespace(email=email, email_verified=True))
    assert error.value.status_code == 403


@pytest.mark.parametrize("email", ["antony502189@gmail.com", "TF.SHULER@gmail.com"])
def test_hard_delete_rejects_unverified_allowlisted_identity(email: str) -> None:
    with pytest.raises(HTTPException) as error:
        require_hard_delete_authorization(SimpleNamespace(email=email, email_verified=False))
    assert error.value.status_code == 403


def test_chat_api_is_unreachable_and_notifications_are_authenticated_routes() -> None:
    paths = app.openapi()["paths"]
    assert not any("/messages" in path for path in paths)
    assert "/api/v1/notifications" in paths
    assert "/api/v1/notifications/{notification_id}/read" in paths
    assert "/api/v1/notifications/read-all" in paths


def test_retired_contact_form_is_not_part_of_any_customer_contract() -> None:
    assert "allowContactForm" not in UserResponse.model_fields
    assert "allowContactForm" not in UserUpdateRequest.model_fields
    assert "allowContactForm" not in ListingResponse.model_fields
    assert "emailVerified" in UserResponse.model_fields
