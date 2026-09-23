from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.session import SessionLocal
from app.models import Listing, User
from app.repositories.listings import owned_query, owned_response_from, point
from app.schemas.listings import ListingPatch
from app.services import listings

pytestmark = pytest.mark.integration


async def _owned_listing(session, listing_id):
    row = (await session.execute(owned_query().where(Listing.id == listing_id))).one()
    return owned_response_from(row)


async def test_location_edit_syncs_only_owner_rooms_with_same_previous_private_address():
    async with SessionLocal() as session:
        owner = User(
            email=f"address-group-{uuid4()}@example.test",
            password_hash="unused",
            name="Address Group Owner",
            role="host",
            initials="AG",
            email_verified=True,
        )
        other_owner = User(
            email=f"address-group-other-{uuid4()}@example.test",
            password_hash="unused",
            name="Other Owner",
            role="host",
            initials="OO",
            email_verified=True,
        )
        session.add_all([owner, other_owner])
        await session.flush()

        def room(user_id, title, street, postcode, city, area, lng, lat):
            return Listing(
                owner_user_id=user_id,
                title=title,
                city=city,
                area=area,
                street=street,
                postcode=postcode,
                approximate_address=f"{area} · ubicación aproximada",
                rental_mode="long",
                monthly_price=650,
                room_type="Habitación individual",
                location=point(lng, lat),
                exact_location=point(lng, lat),
                status="published",
            )

        edited = room(
            owner.id, "Edited room", "Calle Poetas Españoles 3", "38678",
            "Adeje", "Playa de las Américas", -16.7318, 28.0701,
        )
        sibling = room(
            owner.id, "Sibling room", "  calle   poetas españoles 3  ", "38678",
            "Adeje", "Adeje", -16.7244, 28.1227,
        )
        unrelated = room(
            owner.id, "Independent room", "Calle Poetas Españoles 9", "38678",
            "Adeje", "Adeje", -16.7240, 28.1220,
        )
        foreign = room(
            other_owner.id, "Other owner room", "Calle Poetas Españoles 3", "38678",
            "Adeje", "Adeje", -16.7244, 28.1227,
        )
        session.add_all([edited, sibling, unrelated, foreign])
        await session.commit()
        edited_id, sibling_id, unrelated_id, foreign_id = edited.id, sibling.id, unrelated.id, foreign.id
        owner_id = owner.id

    payload = ListingPatch(
        city="Adeje",
        area="Playa de las Américas",
        street="Avenida V Centenario 1",
        postcode="38660",
        approximateAddress="Playa de las Américas · ubicación aproximada",
        latitude=28.0690,
        longitude=-16.7282,
        exactLatitude=28.0674,
        exactLongitude=-16.7268,
        syncAddressGroup=True,
    )

    async with SessionLocal() as session:
        owner = await session.get(User, owner_id)
        assert owner is not None
        updated = await listings.update_listing(edited_id, payload, owner, session)
        assert updated.street == "Avenida V Centenario 1"
        assert updated.postcode == "38660"

    async with SessionLocal() as session:
        sibling_after = await _owned_listing(session, sibling_id)
        unrelated_after = await _owned_listing(session, unrelated_id)
        foreign_after = await _owned_listing(session, foreign_id)

        assert sibling_after.city == "Adeje"
        assert sibling_after.area == "Playa de las Américas"
        assert sibling_after.street == "Avenida V Centenario 1"
        assert sibling_after.postcode == "38660"
        assert sibling_after.latitude == pytest.approx(28.0690)
        assert sibling_after.longitude == pytest.approx(-16.7282)
        assert sibling_after.exactLatitude == pytest.approx(28.0674)
        assert sibling_after.exactLongitude == pytest.approx(-16.7268)

        assert unrelated_after.street == "Calle Poetas Españoles 9"
        assert unrelated_after.postcode == "38678"
        assert foreign_after.street == "Calle Poetas Españoles 3"
        assert foreign_after.postcode == "38678"


def test_group_sync_requires_complete_location_payload():
    with pytest.raises(ValueError, match="complete owner location payload"):
        ListingPatch(
            street="Avenida V Centenario 1",
            postcode="38660",
            syncAddressGroup=True,
        )
