from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.auth import VerifyEmailRequest
from app.schemas.listings import ListingSearchRequest
from app.services.mail import frontend_link


def test_search_schema_accepts_extended_filters():
    filters = ListingSearchRequest(
        rentalMode="long",
        roomType="Habitación individual",
        availableFrom=date(2026, 8, 1),
        maxMinimumStayMonths=3,
        restrictions=["No fumar"],
        furnished=True,
        minRoomSizeM2=10,
        maxRoomSizeM2=20,
        minCurrentResidents=5,
        smokingAllowed=False,
        amenities=["Ascensor"],
        publishedWithinDays=7,
        sort="oldest",
    )

    assert filters.sort == "oldest"
    assert filters.amenities == ["Ascensor"]


def test_search_schema_rejects_reversed_room_size_range():
    with pytest.raises(ValidationError, match="minRoomSizeM2 cannot exceed maxRoomSizeM2"):
        ListingSearchRequest(minRoomSizeM2=30, maxRoomSizeM2=10)


def test_email_verification_token_requires_secure_length():
    with pytest.raises(ValidationError):
        VerifyEmailRequest(token="too-short")


def test_mail_links_use_existing_hash_routes():
    assert frontend_link("/restablecer-contrasena?token=test").endswith("/#/restablecer-contrasena?token=test")
    assert frontend_link("/habitacion/listing-id").endswith("/#/habitacion/listing-id")
