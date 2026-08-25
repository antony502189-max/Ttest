from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.models import MailOutbox
from app.services.notifications import (
    _listing_matches_saved_areas,
    _saved_search_payload,
    create_notification,
    notify_favorited_listing_unavailable,
)


@pytest.mark.asyncio
async def test_notification_creation_is_idempotent_and_uses_the_existing_outbox() -> None:
    notification_id = uuid4()
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: notification_id)),
        add=MagicMock(),
    )
    recipient = SimpleNamespace(id=uuid4(), email="host@example.test")

    created = await create_notification(
        session,
        recipient=recipient,
        kind="listing_published",
        title="Published",
        body="Your listing is live.",
        entity_listing_id=uuid4(),
        idempotency_key="listing-status:one",
        email_path="/habitacion/example",
    )

    assert created is True
    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (recipient_user_id, idempotency_key) DO NOTHING" in sql
    mail = session.add.call_args.args[0]
    assert isinstance(mail, MailOutbox)
    assert mail.recipient == "host@example.test"
    assert mail.kind == "notification_listing_published"


@pytest.mark.asyncio
async def test_duplicate_notification_does_not_enqueue_another_email() -> None:
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        add=MagicMock(),
    )
    recipient = SimpleNamespace(id=uuid4(), email="host@example.test")

    created = await create_notification(
        session,
        recipient=recipient,
        kind="listing_published",
        title="Published",
        body="Your listing is live.",
        idempotency_key="listing-status:one",
        email_path="/habitacion/example",
    )

    assert created is False
    session.add.assert_not_called()


def test_saved_search_alerts_use_the_canonical_search_dto() -> None:
    search = SimpleNamespace(
        id=uuid4(),
        query="Adeje",
        rental_mode="long",
        polygon=[
            {"lat": 28.12, "lng": -16.72},
            {"lat": 28.13, "lng": -16.72},
            {"lat": 28.12, "lng": -16.71},
        ],
        filters={
            "minPrice": 300,
            "maxPrice": 700,
            "areas": ["Adeje"],
            "roomType": "Habitación individual",
            "conditions": ["No fumar"],
            "availableSpotsMin": 1,
            "amenities": ["Wi-Fi"],
        },
    )

    payload = _saved_search_payload(search)

    assert payload is not None
    assert payload.query == "Adeje"
    assert payload.rentalMode == "long"
    assert payload.minPrice == 300 and payload.maxPrice == 700
    assert payload.restrictions == ["No fumar"]
    assert payload.polygon[0].latitude == 28.12


def test_saved_search_defaults_and_removed_filters_do_not_become_hidden_constraints() -> None:
    search = SimpleNamespace(
        id=uuid4(),
        query="Tenerife",
        rental_mode="long",
        polygon=[],
        filters={
            "minPrice": 0,
            "maxPrice": 1200,
            "roomSizeMin": 0,
            "roomSizeMax": 50,
            "homeSizeMin": 0,
            "homeSizeMax": 250,
            "furnished": False,
            "billsIncluded": False,
            "amenities": ["Aire acondicionado"],
        },
    )

    payload = _saved_search_payload(search)

    assert payload is not None
    assert payload.minPrice is None
    assert payload.maxPrice is None
    assert payload.minRoomSizeM2 is None
    assert payload.maxRoomSizeM2 is None
    assert payload.minHomeSizeM2 is None
    assert payload.maxHomeSizeM2 is None
    assert payload.furnished is None
    assert payload.billsIncluded is None
    assert payload.amenities == []


@pytest.mark.parametrize(
    "filters",
    [
        {"minStay": "invalid"},
        {"minStay": []},
        {"currentResidents": {"unexpected": "object"}},
        {"tenantRequirement": []},
        {"smoking": []},
        {"furnished": "false"},
    ],
)
def test_malformed_legacy_saved_search_filters_are_skipped_without_raising(filters) -> None:
    search = SimpleNamespace(
        id=uuid4(),
        query="Adeje",
        rental_mode="long",
        polygon=[],
        filters=filters,
    )

    assert _saved_search_payload(search) is None


def test_malformed_saved_search_polygon_is_skipped_without_broadening() -> None:
    search = SimpleNamespace(
        id=uuid4(),
        query="Adeje",
        rental_mode="long",
        polygon={"lat": 28.12, "lng": -16.72},
        filters={},
    )

    assert _saved_search_payload(search) is None


def test_saved_search_municipality_matching_never_broadens_detailed_or_malformed_zones() -> None:
    listing = SimpleNamespace(city="San Cristóbal de La Laguna")

    assert _listing_matches_saved_areas(listing, {"areas": ["municipality:san-cristobal-de-la-laguna"]})
    assert _listing_matches_saved_areas(listing, {"areas": ["Adeje", "San Cristóbal de La Laguna"]})
    assert not _listing_matches_saved_areas(listing, {"areas": ["district:san-cristobal-de-la-laguna:01"]})
    assert not _listing_matches_saved_areas(listing, {"areas": "San Cristóbal de La Laguna"})


@pytest.mark.asyncio
async def test_favorite_unavailable_notifications_exclude_deleted_and_blocked_accounts() -> None:
    session = SimpleNamespace(
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [])),
    )
    listing = SimpleNamespace(id=uuid4(), title="Room")

    await notify_favorited_listing_unavailable(session, listing, event_key="hidden")

    statement = session.scalars.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect())).lower()
    assert "users.deleted_at is null" in sql
    assert "users.blocked is false" in sql
