from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.main import app
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
    require_hard_delete_authorization(SimpleNamespace(email=raw))


@pytest.mark.parametrize("email", ["renter@example.test", "owner@example.test", "antony502189@gmail.co"])
def test_hard_delete_rejects_every_non_allowlisted_identity(email: str) -> None:
    with pytest.raises(HTTPException) as error:
        require_hard_delete_authorization(SimpleNamespace(email=email))
    assert error.value.status_code == 403


def test_chat_api_is_unreachable_and_notifications_are_authenticated_routes() -> None:
    paths = app.openapi()["paths"]
    assert not any("/messages" in path for path in paths)
    assert "/api/v1/notifications" in paths
    assert "/api/v1/notifications/{notification_id}/read" in paths
    assert "/api/v1/notifications/read-all" in paths
