from app.main import app
from app.schemas.auth import UserResponse, UserUpdateRequest
from app.schemas.listings import ListingResponse
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
