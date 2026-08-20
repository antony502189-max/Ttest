from __future__ import annotations

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
from .media_lifecycle import lock_media_assets, lock_media_owner
from .moderation import lock_active_admin_access, normalize_email, viable_admin_count
from .storage_deletions import enqueue_storage_deletion, enqueue_storage_deletions


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
    locked_user = await session.scalar(select(User).where(User.id == user.id).with_for_update())
    if not locked_user or locked_user.deleted_at is not None:
        raise HTTPException(404, "User not found")
    previous_id = locked_user.avatar_asset_id
    asset_ids = {asset_id for asset_id in (previous_id, payload.assetId) if asset_id is not None}
    assets_by_id = {asset.id: asset for asset in await lock_media_assets(session, asset_ids)}

    if payload.assetId is None:
        locked_user.avatar_asset_id = None
    else:
        asset = assets_by_id.get(payload.assetId)
        if not asset or asset.owner_id != locked_user.id or asset.deleted_at:
            raise HTTPException(404, "Media not found")
        listing_attachment = await session.scalar(
            select(ListingImage.listing_id).where(ListingImage.media_asset_id == asset.id).limit(1)
        )
        if listing_attachment and asset.id != previous_id:
            raise HTTPException(409, "A listing image cannot also be used as an avatar")
        asset.kind = "avatar"
        locked_user.avatar_asset_id = asset.id

    if previous_id and previous_id != locked_user.avatar_asset_id:
        previous = assets_by_id.get(previous_id)
        previous_attachment = await session.scalar(
            select(ListingImage.listing_id).where(ListingImage.media_asset_id == previous_id).limit(1)
        )
        if previous and not previous_attachment:
            previous.deleted_at = datetime.now(UTC)
            await enqueue_storage_deletion(session, previous.storage_key)
        elif previous and previous_attachment:
            previous.kind = "listing_image"

    await session.commit()
    await session.refresh(locked_user)
    return locked_user


async def delete_account(user: User, session: AsyncSession) -> None:
    await lock_media_owner(session, user.id)
    locked_user = await session.scalar(select(User).where(User.id == user.id).with_for_update())
    if not locked_user or locked_user.deleted_at is not None:
        raise HTTPException(404, "User not found")

    # Lock all grants in stable email order before evaluating the last-admin
    # invariant. A user lock alone is insufficient: two administrators could
    # otherwise each see the other account and both complete deletion.
    active_grants = await lock_active_admin_access(session)
    matching_grant = next((row for row in active_grants if row.email == normalize_email(locked_user.email)), None)
    is_viable_admin = bool(matching_grant and locked_user.google_subject and not locked_user.blocked)
    if is_viable_admin and await viable_admin_count(session) <= 1:
        raise HTTPException(409, "At least one viable administrator must remain active")

    owned_listing_ids = select(Listing.id).where(Listing.owner_user_id == locked_user.id)
    await session.scalars(owned_listing_ids.order_by(Listing.id).with_for_update())
    media_ids = set(
        (await session.scalars(select(MediaAsset.id).where(MediaAsset.owner_id == locked_user.id))).all()
    )
    locked_assets = await lock_media_assets(session, media_ids)
    media_paths = [asset.storage_key for asset in locked_assets]
    original_email = locked_user.email
    now = datetime.now(UTC)

    await session.execute(delete(AuthSession).where(AuthSession.user_id == locked_user.id))
    await session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == locked_user.id))
    await session.execute(delete(EmailVerificationToken).where(EmailVerificationToken.user_id == locked_user.id))
    await session.execute(
        delete(Favorite).where(
            (Favorite.user_id == locked_user.id) | (Favorite.listing_id.in_(owned_listing_ids))
        )
    )
    await session.execute(
        delete(DiscardedListing).where(
            (DiscardedListing.user_id == locked_user.id)
            | (DiscardedListing.listing_id.in_(owned_listing_ids))
        )
    )
    await session.execute(delete(SavedSearch).where(SavedSearch.user_id == locked_user.id))
    await session.execute(delete(SearchHistory).where(SearchHistory.user_id == locked_user.id))
    await session.execute(delete(MailOutbox).where(MailOutbox.recipient == original_email))
    if media_ids:
        await session.execute(delete(ListingImage).where(ListingImage.media_asset_id.in_(media_ids)))
    await session.execute(
        update(Listing)
        .where(Listing.owner_user_id == locked_user.id, Listing.deleted_at.is_(None))
        .values(deleted_at=now, status="closed", closed_reason="account_deleted")
    )
    await session.execute(
        update(MediaAsset)
        .where(MediaAsset.owner_id == locked_user.id, MediaAsset.deleted_at.is_(None))
        .values(deleted_at=now)
    )

    locked_user.deleted_at = now
    locked_user.blocked = True
    locked_user.email_verified = False
    locked_user.email = f"deleted-{locked_user.id}@deleted.invalid"
    locked_user.google_subject = None
    locked_user.password_hash = None
    locked_user.name = "Deleted user"
    locked_user.phone = locked_user.whatsapp = locked_user.telegram = locked_user.about = ""
    locked_user.show_phone = locked_user.show_whatsapp = False
    locked_user.allow_contact_form = False
    locked_user.avatar_asset_id = None
    if matching_grant:
        # Preserve the historical grant row but make it unusable immediately;
        # the anonymized deleted address must never count as an administrator.
        matching_grant.active = False
    await enqueue_storage_deletions(session, media_paths)
    await session.commit()
