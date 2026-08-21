from datetime import date

import pytest
from pydantic import ValidationError

from app.repositories.listings import apply_search_filters, visible_query
from app.schemas.listings import ListingSearchRequest, ListingWrite


def base_payload() -> dict:
    return {
        "title": "Habitación privada con cocina y aseo propios",
        "city": "Adeje",
        "area": "Armeñime",
        "approximateAddress": "Armeñime · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 450,
        "roomType": "Habitación individual",
        "availableFrom": "2026-09-01",
        "availableUntil": "2027-06-30",
        "minimumStayMonths": 3,
        "depositAmount": 100,
        "bathroom": "Baño compartido",
        "kitchen": "Cocina privada",
        "roomSizeM2": 14,
        "bedroomCount": 5,
        "currentResidents": 4,
        "roomCapacity": 1,
        "shower": "Ducha compartida",
        "tenantRequirement": "single-man",
        "smokingAllowed": False,
        "petsAllowed": False,
        "childrenAllowed": False,
        "homeSizeM2": 85,
        "bathroomCount": 2,
        "rentalUnit": "room",
        "bedType": "single",
        "bedCount": 1,
        "currentRoomResidents": 0,
        "toilet": "Aseo privado",
        "householdGender": "men",
        "householdHasChildren": False,
        "heatingType": "none",
        "accessible": False,
        "couplesAllowed": False,
        "acceptedTenantTypes": ["man"],
        "latitude": 28.1272,
        "longitude": -16.739,
    }


def test_private_long_term_room_scenario_is_structured_and_valid():
    listing = ListingWrite.model_validate(base_payload())

    assert listing.roomSizeM2 == 14
    assert listing.homeSizeM2 == 85
    assert listing.currentResidents == 4
    assert listing.toilet == "Aseo privado"
    assert listing.kitchen == "Cocina privada"
    assert listing.depositAmount == 100
    assert listing.acceptedTenantTypes == ["man"]


def test_shared_room_with_three_individual_bed_spaces_is_valid():
    payload = base_payload() | {
        "title": "Plaza en habitación compartida con tres camas",
        "roomType": "Habitación compartida",
        "roomSizeM2": 20,
        "roomCapacity": 3,
        "rentalUnit": "bed",
        "bedType": "single",
        "bedCount": 3,
        "currentRoomResidents": 2,
        "bathroom": "Baño compartido",
        "toilet": "Aseo compartido",
        "shower": "Ducha compartida",
        "kitchen": "Cocina compartida",
        "tenantRequirement": "any",
        "acceptedTenantTypes": ["man", "woman"],
    }

    listing = ListingWrite.model_validate(payload)

    assert listing.rentalUnit == "bed"
    assert listing.bedCount == 3
    assert listing.roomCapacity == 3
    assert listing.currentRoomResidents == 2


def test_shared_room_with_bunk_bed_is_valid():
    payload = base_payload() | {
        "title": "Habitación compartida con litera",
        "roomType": "Habitación compartida",
        "roomCapacity": 2,
        "rentalUnit": "bed",
        "bedType": "bunk",
        "bedCount": 1,
        "currentRoomResidents": 1,
    }

    listing = ListingWrite.model_validate(payload)

    assert listing.bedType == "bunk"
    assert listing.bedCount == 1
    assert listing.roomCapacity == 2


def test_holiday_room_for_two_with_double_bed_is_valid():
    payload = base_payload() | {
        "title": "Habitación privada para dos huéspedes",
        "rentalMode": "holiday",
        "monthlyPrice": None,
        "nightlyPrice": 55,
        "minimumStayMonths": 0,
        "minimumNights": 3,
        "roomCapacity": 2,
        "bedType": "double",
        "bedCount": 1,
        "bathroom": "Baño privado",
        "toilet": "Aseo privado",
        "shower": "Ducha privada",
        "kitchen": "Cocina compartida",
        "tenantRequirement": "any",
        "acceptedTenantTypes": ["man", "woman", "couple"],
    }

    listing = ListingWrite.model_validate(payload)

    assert listing.nightlyPrice == 55
    assert listing.minimumNights == 3
    assert listing.roomCapacity == 2
    assert listing.bedType == "double"


def test_bed_space_cannot_be_published_as_private_room():
    payload = base_payload() | {"rentalUnit": "bed"}

    with pytest.raises(ValidationError, match="only valid for shared rooms"):
        ListingWrite.model_validate(payload)


def test_shared_room_must_keep_at_least_one_free_space():
    payload = base_payload() | {
        "roomType": "Habitación compartida",
        "rentalUnit": "bed",
        "roomCapacity": 3,
        "bedType": "single",
        "bedCount": 3,
        "currentRoomResidents": 3,
    }

    with pytest.raises(ValidationError, match="leave at least one available place"):
        ListingWrite.model_validate(payload)


def test_home_size_cannot_be_smaller_than_room():
    payload = base_payload() | {"homeSizeM2": 10, "roomSizeM2": 14}

    with pytest.raises(ValidationError, match="cannot be smaller"):
        ListingWrite.model_validate(payload)


def test_search_accepts_exact_interval_and_room_first_filters():
    search = ListingSearchRequest.model_validate(
        {
            "rentalMode": "holiday",
            "availableFrom": date(2026, 9, 10),
            "availableUntil": date(2026, 9, 17),
            "roomTypes": ["Habitación compartida"],
            "rentalUnit": "bed",
            "bedType": "single",
            "minBedCount": 3,
            "maxCurrentRoomResidents": 2,
            "minAvailableSpots": 1,
            "acceptedTenantTypes": ["man", "woman"],
        }
    )

    assert search.availableFrom == date(2026, 9, 10)
    assert search.availableUntil == date(2026, 9, 17)
    assert search.rentalUnit == "bed"
    assert search.acceptedTenantTypes == ["man", "woman"]


def test_multiple_accepted_tenant_types_compile_as_alternatives():
    query = apply_search_filters(
        visible_query(),
        ListingSearchRequest(acceptedTenantTypes=["man", "woman"]),
    )
    compiled = str(query)

    assert " OR " in compiled
    assert compiled.count("listing_room_details.accepted_tenant_types") >= 2
