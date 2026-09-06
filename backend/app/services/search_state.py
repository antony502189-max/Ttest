from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models import DiscardedListing, Favorite, Listing, SavedSearch, SearchHistory, User
from ..models.moderation import ListingRestriction, UserRestriction
from ..schemas.searches import GuestStateImport, SavedSearchPatch, SavedSearchResponse, SavedSearchWrite
from .moderation import active_window, enforce_listing_view_access
from .user_locks import lock_user_for_mutation

MAX_HISTORY = 20


def visible_listing_conditions():
    """Canonical public-visibility policy for saved listing collections.

    Favorites/discarded IDs are another public-listing surface: a moderation-
    hidden listing must not remain discoverable or be accepted by ID through
    these collections. Reuse the moderation service's active-window semantics so
    permanent user restrictions and dated listing restrictions match search and
    detail behavior.
    """
    active_owner_restriction = (
        select(UserRestriction.id)
        .where(UserRestriction.user_id == User.id, *active_window(UserRestriction))
        .correlate(User)
        .exists()
    )
    active_listing_restriction = (
        select(ListingRestriction.id)
        .where(ListingRestriction.listing_id == Listing.id, *active_window(ListingRestriction))
        .correlate(Listing)
        .exists()
    )
    return (
        Listing.status == "published",
        Listing.deleted_at.is_(None),
        (Listing.expires_at.is_(None)) | (Listing.expires_at > func.now()),
        User.deleted_at.is_(None),
        User.blocked.is_(False),
        ~active_owner_restriction,
        ~active_listing_restriction,
    )


async def require_listing(listing_id: UUID, session: AsyncSession) -> None:
    listing = await session.scalar(
        select(Listing.id)
        .join(User, User.id == Listing.owner_user_id)
        .where(Listing.id == listing_id, *visible_listing_conditions())
    )
    if not listing:
        raise HTTPException(404, "Listing not found")


def collection_query(model, user_id: UUID):
    return (
        select(model.listing_id)
        .join(Listing, Listing.id == model.listing_id)
        .join(User, User.id == Listing.owner_user_id)
        .where(model.user_id == user_id, *visible_listing_conditions())
        .order_by(model.created_at.desc(), model.listing_id.desc())
    )


async def lock_active_state_user(user_id: UUID, session: AsyncSession) -> User:
    """Serialize all durable per-user search state with account deletion.

    Users are soft-deleted, so foreign keys alone cannot prevent a request that
    loaded the account before deletion from re-creating favorites, saved
    searches or history after the deletion transaction has cleaned them up.
    Locking/repopulating the User row first gives these writes the same durable
    identity boundary used by listing/profile mutations.
    """
    user = await lock_user_for_mutation(user_id, session)
    if not user or user.blocked or user.deleted_at is not None:
        raise HTTPException(404, "User not found")
    return user


async def lock_collection(model, user_id: UUID, session: AsyncSession) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"listing-collection:{model.__tablename__}:{user_id}"},
    )


async def collection_count(model, user_id: UUID, session: AsyncSession) -> int:
    value = await session.scalar(
        select(func.count())
        .select_from(model)
        .join(Listing, Listing.id == model.listing_id)
        .join(User, User.id == Listing.owner_user_id)
        .where(
            model.user_id == user_id,
            Listing.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
    )
    return int(value or 0)


async def list_collection(model, user: User, session: AsyncSession) -> list[UUID]:
    await enforce_listing_view_access(user, session)
    limit = get_settings().max_listing_collection_items_per_user
    return list((await session.scalars(collection_query(model, user.id).limit(limit))).all())


async def add_collection_item(model, constraint: str, listing_id: UUID, user: User, session: AsyncSession) -> None:
    user = await lock_active_state_user(user.id, session)
    await enforce_listing_view_access(user, session)
    await require_listing(listing_id, session)
    await lock_collection(model, user.id, session)
    existing = await session.scalar(
        select(model.listing_id).where(model.user_id == user.id, model.listing_id == listing_id)
    )
    if existing is not None:
        await session.commit()
        return
    if await collection_count(model, user.id, session) >= get_settings().max_listing_collection_items_per_user:
        raise HTTPException(409, "Listing collection limit reached")
    await session.execute(
        insert(model).values(user_id=user.id, listing_id=listing_id).on_conflict_do_nothing(constraint=constraint)
    )
    await session.commit()


async def remove_collection_item(model, listing_id: UUID, user: User, session: AsyncSession) -> None:
    user = await lock_active_state_user(user.id, session)
    await enforce_listing_view_access(user, session)
    await session.execute(delete(model).where(model.user_id == user.id, model.listing_id == listing_id))
    await session.commit()


async def clear_collection(model, user: User, session: AsyncSession) -> None:
    user = await lock_active_state_user(user.id, session)
    await enforce_listing_view_access(user, session)
    await session.execute(delete(model).where(model.user_id == user.id))
    await session.commit()


def valid_uuid_values(values: list[str]) -> list[UUID]:
    result: list[UUID] = []
    for value in values:
        try:
            result.append(UUID(value))
        except (ValueError, TypeError, AttributeError):
            continue
    return result


async def lock_saved_searches(user_id: UUID, session: AsyncSession) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"saved-searches:{user_id}"},
    )


async def lock_search_history(user_id: UUID, session: AsyncSession) -> None:
    """Serialize per-user deduplication and overflow pruning."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"search-history:{user_id}"},
    )


async def saved_search_count(user_id: UUID, session: AsyncSession) -> int:
    value = await session.scalar(select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user_id))
    return int(value or 0)


async def import_guest_state(payload: GuestStateImport, user: User, session: AsyncSession) -> None:
    user = await lock_active_state_user(user.id, session)
    await enforce_listing_view_access(user, session)
    settings = get_settings()
    requested_ids = valid_uuid_values(payload.favoriteIds)
    valid_listing_ids = (
        set(
            (
                await session.scalars(
                    select(Listing.id)
                    .join(User, User.id == Listing.owner_user_id)
                    .where(Listing.id.in_(requested_ids), *visible_listing_conditions())
                )
            ).all()
        )
        if requested_ids
        else set()
    )
    if valid_listing_ids:
        await lock_collection(Favorite, user.id, session)
        current_count = await collection_count(Favorite, user.id, session)
        available = max(0, settings.max_listing_collection_items_per_user - current_count)
        if available:
            existing_ids = set(
                (
                    await session.scalars(
                        select(Favorite.listing_id).where(
                            Favorite.user_id == user.id,
                            Favorite.listing_id.in_(valid_listing_ids),
                        )
                    )
                ).all()
            )
            new_ids = sorted(valid_listing_ids - existing_ids, key=str)[:available]
            if new_ids:
                await session.execute(
                    insert(Favorite)
                    .values([{"user_id": user.id, "listing_id": listing_id} for listing_id in new_ids])
                    .on_conflict_do_nothing(constraint="uq_favorites_user_listing")
                )

    await lock_saved_searches(user.id, session)
    current_count = await saved_search_count(user.id, session)
    for item in payload.savedSearches:
        if current_count >= settings.max_saved_searches_per_user:
            break
        polygon = [point.model_dump() for point in item.polygon]
        duplicate = await session.scalar(
            select(SavedSearch.id).where(
                SavedSearch.user_id == user.id,
                SavedSearch.query == item.query.strip(),
                SavedSearch.rental_mode == item.rentalMode,
                SavedSearch.filters == item.filters,
                SavedSearch.polygon == polygon,
            )
        )
        if not duplicate:
            session.add(
                SavedSearch(
                    user_id=user.id,
                    name=item.name.strip(),
                    query=item.query.strip(),
                    rental_mode=item.rentalMode,
                    filters=item.filters,
                    polygon=polygon,
                    alerts_enabled=item.alertsEnabled,
                )
            )
            current_count += 1
    await session.commit()


def public_search(search: SavedSearch) -> SavedSearchResponse:
    return SavedSearchResponse(
        id=search.id,
        name=search.name,
        query=search.query,
        rentalMode=search.rental_mode,
        filters=search.filters,
        polygon=search.polygon,
        alertsEnabled=search.alerts_enabled,
        createdAt=search.created_at,
        updatedAt=search.updated_at,
    )


async def list_saved_searches(user: User, session: AsyncSession) -> list[SavedSearchResponse]:
    searches = (
        await session.scalars(
            select(SavedSearch)
            .where(SavedSearch.user_id == user.id)
            .order_by(SavedSearch.created_at.desc())
            .limit(get_settings().max_saved_searches_per_user)
        )
    ).all()
    return [public_search(search) for search in searches]


async def create_saved_search(
    payload: SavedSearchWrite,
    user: User,
    session: AsyncSession,
) -> SavedSearchResponse:
    user = await lock_active_state_user(user.id, session)
    settings = get_settings()
    await lock_saved_searches(user.id, session)
    if await saved_search_count(user.id, session) >= settings.max_saved_searches_per_user:
        raise HTTPException(409, "Saved search limit reached")
    search = SavedSearch(
        user_id=user.id,
        name=payload.name.strip(),
        query=payload.query.strip(),
        rental_mode=payload.rentalMode,
        filters=payload.filters,
        polygon=[point.model_dump() for point in payload.polygon],
        alerts_enabled=payload.alertsEnabled,
    )
    session.add(search)
    await session.commit()
    await session.refresh(search)
    return public_search(search)


async def update_saved_search(
    search_id: UUID,
    payload: SavedSearchPatch,
    user: User,
    session: AsyncSession,
) -> SavedSearchResponse:
    user = await lock_active_state_user(user.id, session)
    search = await session.scalar(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id).with_for_update()
    )
    if not search:
        raise HTTPException(404, "Saved search not found")
    mapping = {"alertsEnabled": "alerts_enabled"}
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "polygon" and value is not None:
            search.polygon = [point if isinstance(point, dict) else point.model_dump() for point in value]
        else:
            setattr(search, mapping.get(key, key), value.strip() if isinstance(value, str) else value)
    await session.commit()
    await session.refresh(search)
    return public_search(search)


async def delete_saved_search(search_id: UUID, user: User, session: AsyncSession) -> None:
    user = await lock_active_state_user(user.id, session)
    search = await session.scalar(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id).with_for_update()
    )
    if not search:
        raise HTTPException(404, "Saved search not found")
    await session.delete(search)
    await session.commit()


async def list_history(user: User, session: AsyncSession) -> list[str]:
    return list(
        (
            await session.scalars(
                select(SearchHistory.normalized_query)
                .where(SearchHistory.user_id == user.id)
                .order_by(SearchHistory.searched_at.desc())
                .limit(MAX_HISTORY)
            )
        ).all()
    )


async def add_history(query: str, user: User, session: AsyncSession) -> None:
    normalized = " ".join(query.split())
    if not normalized:
        return
    user = await lock_active_state_user(user.id, session)
    await lock_search_history(user.id, session)
    await session.execute(
        delete(SearchHistory).where(
            SearchHistory.user_id == user.id,
            SearchHistory.normalized_query == normalized,
        )
    )
    session.add(SearchHistory(user_id=user.id, normalized_query=normalized))
    await session.flush()
    overflow = (
        await session.scalars(
            select(SearchHistory.id)
            .where(SearchHistory.user_id == user.id)
            .order_by(SearchHistory.searched_at.desc(), SearchHistory.id.desc())
            .offset(MAX_HISTORY)
        )
    ).all()
    if overflow:
        await session.execute(delete(SearchHistory).where(SearchHistory.id.in_(overflow)))
    await session.commit()


async def clear_history(user: User, session: AsyncSession) -> None:
    user = await lock_active_state_user(user.id, session)
    await lock_search_history(user.id, session)
    await session.execute(delete(SearchHistory).where(SearchHistory.user_id == user.id))
    await session.commit()


FAVORITES = Favorite
DISCARDED = DiscardedListing
