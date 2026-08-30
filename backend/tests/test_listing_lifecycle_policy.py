from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.listings import ListingPatch, ListingWrite
from app.services.listings import resolve_owner_status_transition


@pytest.mark.parametrize("current", ["hidden", "rejected", "draft"])
def test_show_intent_returns_to_moderation_in_production(current: str) -> None:
    assert resolve_owner_status_transition(current, "published", auto_publish=False) == "pending"


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        ("pending", "draft"),
        ("published", "pending"),
        ("closed", "pending"),
        ("rejected", "hidden"),
    ],
)
def test_owner_cannot_bypass_canonical_lifecycle(current: str, requested: str) -> None:
    with pytest.raises(HTTPException) as error:
        resolve_owner_status_transition(current, requested, auto_publish=False)
    assert error.value.status_code == 409


def test_expired_create_and_patch_payloads_are_rejected_before_database_mutation() -> None:
    expired = datetime.now(UTC) - timedelta(minutes=1)
    with pytest.raises(ValidationError, match="expiresAt must be in the future"):
        ListingPatch(expiresAt=expired)

    valid = {
        "title": "Schema expiry lifecycle listing",
        "city": "Adeje",
        "area": "Centro",
        "approximateAddress": "Adeje · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 600,
        "roomType": "Habitación individual",
        "latitude": 28.1,
        "longitude": -16.7,
        "expiresAt": expired,
    }
    with pytest.raises(ValidationError, match="expiresAt must be in the future"):
        ListingWrite.model_validate(valid)

