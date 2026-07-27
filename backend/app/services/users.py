from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    AuthSession,
    DiscardedListing,
    EmailVerificationToken,
    Favorite,
    Listing,
    ListingImage,
    MailOutbox,
    MediaAsset,
    PasswordResetToken,
    SavedSearch,
    SearchHistory,
    User,
)
from ..schemas.auth import AvatarUpdateRequest, UserUpdateRequest
from ..storage import get_storage


async def update_profile(payload: UserUpdateRequest, user: User, session: AsyncSession) -> User:
    fields = payload.model_dump(exclude_unset=True)
    mapping = {
        "showPhone": "show_phone",
        "showWhatsApp": "show_whatsapp",
        "allowContactForm": "allow_contact_form",
    }
    for key, value in fields.items():
        setattr(user, mapping.get(key, key), value)
    if "name" in fields:
        user.initials = "".join(part[:1].upper() for part in user.name.split()[:2])
    await session.commit()
    await session.refresh(user)
    return user


async def update_avatar(payload: AvatarUpdateRequest, user: User, session: AsyncSession) -> User:
    previous_id = user.avatar_asset_id
    previous_key: str | None = None

    if payload.assetId is None:
        user.avatar_asset_id = None
    else:
        asset = await session.get(MediaAsset, payload.assetId)
        if not asset or asset.owner_id != user.id or asset.deleted_at:
            raise HTTPException(404, "Media not found")
        listing_attachment = await session.scalar(
            select(ListingImage.listing_id).where(ListingImage.media_asset_id == asset.id).limit(1)
        )
        if listing_attachment and asset.id != previous_id:
            raise HTTPException(409, "A listing image cannot also be used as an avatar")
        asset.kind = "avatar"
        user.avatar_asset_id = asset.id

    if previous_id and previous_id != user.avatar_asset_id:
        previous = await session.get(MediaAsset, previous_id)
        previous_attachment = await session.scalar(
            select(ListingImage.listing_id).where(ListingImage.media_asset_id == previous_id).limit(1)
        )
        if previous and not previous_attachment:
            previous.deleted_at = datetime.now(UTC)
            previous_key = previous.storage_key
        elif previous and previous_attachment:
            previous.kind = "listing_image"

    await session.commit()
    await session.refresh(user)
    if previous_key:
        await asyncio.to_thread(get_storage().delete, previous_key)
    return user


async def delete_account(user: User, session: AsyncSession) -> None:
    media_paths = list(
        (await session.scalars(select(MediaAsset.storage_key).where(MediaAsset.owner_id == user.id))).all()
    )
    original_email = user.email
    now = datetime.now(UTC)

    await session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    await session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    await session.execute(delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id))
    await session.execute(delete(Favorite).where(Favorite.user_id == user.id))
    await session.execute(delete(DiscardedListing).where(DiscardedListing.user_id == user.id))
    await session.execute(delete(SavedSearch).where(SavedSearch.user_id == user.id))
    await session.execute(delete(SearchHistory).where(SearchHistory.user_id == user.id))
    await session.execute(delete(MailOutbox).where(MailOutbox.recipient == original_email))
    await session.execute(
        update(Listing)
        .where(Listing.owner_user_id == user.id, Listing.deleted_at.is_(None))
        .values(deleted_at=now, status="closed", closed_reason="account_deleted")
    )
    await session.execute(
        update(MediaAsset).where(MediaAsset.owner_id == user.id, MediaAsset.deleted_at.is_(None)).values(deleted_at=now)
    )

    user.deleted_at = now
    user.blocked = True
    user.email_verified = False
    user.email = f"deleted-{user.id}@deleted.invalid"
    user.google_subject = None
    user.password_hash = None
    user.name = "Deleted user"
    user.phone = user.whatsapp = user.telegram = user.about = ""
    user.show_phone = user.show_whatsapp = False
    user.allow_contact_form = False
    user.avatar_asset_id = None
    await session.commit()

    await asyncio.gather(
        *(asyncio.to_thread(get_storage().delete, storage_key) for storage_key in media_paths),
        return_exceptions=True,
    )
