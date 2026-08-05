from datetime import UTC, datetime
from hashlib import sha256
from hmac import new as hmac_new

from sqlalchemy import delete, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models import Listing, ListingView


def anonymous_viewer_key(network_identity: str) -> str:
    return hmac_new(
        get_settings().jwt_secret.encode(),
        network_identity.encode(),
        sha256,
    ).hexdigest()


async def register_view(listing: Listing, viewer_key: str, session: AsyncSession) -> bool:
    today = datetime.now(UTC).date()
    inserted = await session.scalar(
        insert(ListingView)
        .values(listing_id=listing.id, viewer_key=viewer_key, view_date=today)
        .on_conflict_do_nothing(constraint="uq_listing_views_daily")
        .returning(ListingView.id)
    )
    if inserted is None:
        return False

    await session.execute(
        update(Listing)
        .where(Listing.id == listing.id)
        .values(views=Listing.views + 1)
    )
    # Historical rows are needed only for current-day deduplication; the
    # durable aggregate lives in listings.views. Prune prior days whenever the
    # listing receives its first new unique view after them.
    await session.execute(
        delete(ListingView).where(
            ListingView.listing_id == listing.id,
            ListingView.view_date < today,
        )
    )
    await session.commit()
    return True
