from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.models import MailOutbox
from app.services.notifications import _listing_matches_saved_areas, _saved_search_payload, create_notification


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


@pytest.mark.parametrize(
    "filters",
    [
        {"minStay": "invalid"},
        {"minStay": []},
        {"currentResidents": {"unexpected": "object"}},
        {"tenantRequirement": []},
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


def test_saved_search_municipality_matching_never_broadens_detailed_zones() -> None:
    listing = SimpleNamespace(city="San Cristóbal de La Laguna")

    assert _listing_matches_saved_areas(listing, {"areas": ["municipality:san-cristobal-de-la-laguna"]})
    assert _listing_matches_saved_areas(listing, {"areas": ["Adeje", "San Cristóbal de La Laguna"]})
    assert not _listing_matches_saved_areas(listing, {"areas": ["district:san-cristobal-de-la-laguna:01"]})
