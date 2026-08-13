from datetime import UTC, datetime
from types import SimpleNamespace

from app.repositories.listings import owned_response_from, response_from, visible_query


def listing(**overrides):
    values = {
        "id": "listing-id",
        "owner_user_id": "owner-id",
        "rental_mode": "long",
        "nightly_price": 75,
        "monthly_price": 700,
        "external_image_urls": [],
        "external_contact_phone": None,
        "external_contact_whatsapp": None,
        "external_contact_email": None,
        "is_external": False,
        "title": "Room",
        "city": "Adeje",
        "area": "Costa Adeje",
        "approximate_address": "Costa Adeje",
        "weekly_price": None,
        "room_type": "HabitaciГіn individual",
        "available_from": None,
        "available_until": None,
        "minimum_stay_months": 0,
        "minimum_nights": None,
        "deposit_amount": 0,
        "deposit_text": None,
        "bills_included": False,
        "bills_text": None,
        "bathroom": "BaГ±o compartido",
        "kitchen": "Cocina compartida",
        "furnished": True,
        "room_size_m2": 12,
        "bedroom_count": 2,
        "current_residents": 1,
        "room_capacity": 1,
        "shower": "Ducha compartida",
        "tenant_requirement": "any",
        "smoking_allowed": False,
        "pets_allowed": False,
        "children_allowed": False,
        "empadronamiento_allowed": False,
        "restrictions": [],
        "amenities": [],
        "status": "published",
        "description": "Description",
        "home_description": "Home description",
        "advertiser_type": "Particular",
        "advertiser_name": None,
        "source": None,
        "primary_source": None,
        "primary_source_url": None,
        "source_price_text": None,
        "source_price_currency": None,
        "source_price_period": None,
        "source_price_is_from": None,
        "published_at": datetime(2026, 1, 1, tzinfo=UTC),
        "expires_at": None,
        "views": 0,
        "closed_reason": None,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
        "street": "Street",
        "postcode": "38660",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def owner():
    return SimpleNamespace(
        name="Owner Name",
        initials="ON",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        email_verified=True,
        phone="+34 600 000 000",
        whatsapp="+34 600 000 000",
        show_phone=True,
        show_whatsapp=True,
        allow_contact_form=True,
    )


def test_coordinate_projection_preserves_public_response_values():
    response = response_from((listing(), -16.732123456789, 28.087987654321, owner(), ["asset-id"]))

    assert response.longitude == -16.732123456789
    assert response.latitude == 28.087987654321
    assert response.imageUrls == ["/api/v1/media/asset-id"]


def test_owned_coordinate_projection_preserves_exact_location_values():
    response = owned_response_from((listing(), -16.732, 28.087, owner(), [], -16.733, 28.088))

    assert response.longitude == -16.732
    assert response.latitude == 28.087
    assert response.exactLongitude == -16.733
    assert response.exactLatitude == 28.088


def test_public_projection_uses_scalar_coordinates_without_geojson():
    projected_sql = str(visible_query())

    assert "ST_X" in projected_sql
    assert "ST_Y" in projected_sql
    assert "array_agg" in projected_sql
    assert "ST_AsGeoJSON" not in projected_sql
