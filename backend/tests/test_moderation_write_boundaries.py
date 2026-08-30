from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.listings import ListingImagesRequest, ListingPatch
from app.services import listings


@pytest.mark.asyncio
async def test_published_listing_edit_enforces_publish_restriction(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=uuid4())
    listing = SimpleNamespace(
        id=uuid4(),
        owner_user_id=user.id,
        deleted_at=None,
        status="published",
    )
    session = SimpleNamespace()
    monkeypatch.setattr(listings, "_lock_mutable_listing", AsyncMock(return_value=(listing, user)))
    monkeypatch.setattr(listings, "ensure_owner_or_admin", AsyncMock(return_value=False))
    enforce_publish = AsyncMock(side_effect=HTTPException(403, "Publishing restricted"))
    monkeypatch.setattr(listings, "enforce_publish_access", enforce_publish)

    with pytest.raises(HTTPException) as exc:
        await listings.update_listing(
            listing.id,
            ListingPatch(title="Updated room"),
            user,
            session,
        )

    assert exc.value.status_code == 403
    enforce_publish.assert_awaited_once_with(user, session)


@pytest.mark.asyncio
async def test_published_listing_image_edit_enforces_publish_restriction(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=uuid4())
    listing = SimpleNamespace(
        id=uuid4(),
        owner_user_id=user.id,
        deleted_at=None,
        status="published",
    )
    session = SimpleNamespace()
    monkeypatch.setattr(listings, "_lock_mutable_listing", AsyncMock(return_value=(listing, user)))
    monkeypatch.setattr(listings, "ensure_owner_or_admin", AsyncMock(return_value=False))
    enforce_publish = AsyncMock(side_effect=HTTPException(403, "Publishing restricted"))
    monkeypatch.setattr(listings, "enforce_publish_access", enforce_publish)

    with pytest.raises(HTTPException) as exc:
        await listings.replace_listing_images(
            listing.id,
            ListingImagesRequest(assetIds=[]),
            user,
            session,
        )

    assert exc.value.status_code == 403
    enforce_publish.assert_awaited_once_with(user, session)
