from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.listings import _validate_effective_patch_state


def listing_state():
    return SimpleNamespace(
        room_type="Habitación compartida",
        room_capacity=3,
        room_size_m2=20,
        rental_mode="long",
        monthly_price=450,
        nightly_price=None,
        available_from=date(2026, 9, 1),
        available_until=date(2027, 6, 30),
    )


def room_details_state():
    return SimpleNamespace(
        rental_unit="bed",
        bed_type="single",
        bed_count=3,
        current_room_residents=2,
        home_size_m2=80,
    )


def assert_rejected(changes: dict[str, object], detail: str):
    with pytest.raises(HTTPException) as error:
        _validate_effective_patch_state(listing_state(), room_details_state(), changes)
    assert error.value.status_code == 422
    assert detail in str(error.value.detail)


def test_patch_cannot_reduce_capacity_to_current_room_occupancy():
    assert_rejected({"roomCapacity": 2}, "leave at least one available place")


def test_patch_cannot_turn_bed_space_listing_into_private_room():
    assert_rejected({"roomType": "Habitación individual"}, "only valid for shared rooms")


def test_patch_cannot_leave_too_few_sleeping_places():
    assert_rejected({"bedCount": 1}, "do not provide enough sleeping places")


def test_patch_cannot_make_home_smaller_than_room():
    assert_rejected({"homeSizeM2": 15}, "cannot be smaller")


def test_patch_cannot_invert_existing_availability_interval():
    assert_rejected({"availableUntil": date(2026, 8, 31)}, "cannot be before availableFrom")


def test_patch_cannot_switch_to_holiday_without_nightly_price():
    assert_rejected({"rentalMode": "holiday"}, "nightlyPrice is required")


def test_consistent_multi_field_room_patch_is_accepted():
    _validate_effective_patch_state(
        listing_state(),
        room_details_state(),
        {
            "roomCapacity": 4,
            "bedCount": 4,
            "currentRoomResidents": 2,
            "homeSizeM2": 90,
            "availableUntil": date(2027, 12, 31),
        },
    )
