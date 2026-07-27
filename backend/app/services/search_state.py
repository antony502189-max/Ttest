from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DiscardedListing, Favorite, Listing, SavedSearch, SearchHistory, User
from ..schemas.searches import GuestStateImport, SavedSearchPatch, SavedSearchResponse, SavedSearchWrite

MAX_HISTORY = 20


async def require_listing(listing_id: UUID, session: AsyncSession) -> None:
    listing = await session.scalar(
        select(Listing.id).where(Listing.id == listing_id, Listing.deleted_at.is_(None))
    )
    if not listing:
        raise HTTPException(404, "Listing not found")


def collection_query(model, user_id: UUID):
    return select(model.listing_id).where(model.user_id == user_id).order_by(model.created_at.desc())


async def list_collection(model, user: User, session: AsyncSession) -> list[UUID]:
    return list((await session.scalars(collection_query(model, user.id))).all())


async def add_collection_item(model, constraint: str, listing_id: UUID, user: User, session: AsyncSession) -> None:
    await require_listing(listing_id, session)
    await session.execute(
        insert(model)
        .values(user_id=user.id, listing_id=listing_id)
        .on_conflict_do_nothing(constraint=constraint)
    )
    await session.commit()


async def remove_collection_item(model, listing_id: UUID, user: User, session: AsyncSession) -> None:
    await session.execute(delete(model).where(model.user_id == user.id, model.listing_id == listing_id))
    await session.commit()


async def clear_collection(model, user: User, session: AsyncSession) -> None:
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


async def import_guest_state(payload: GuestStateImport, user: User, session: AsyncSession) -> None:
    requested_ids = valid_uuid_values(payload.favoriteIds)
    valid_listing_ids = set(
        (
            await session.scalars(
                select(Listing.id).where(
                    Listing.id.in_(requested_ids),
                    Listing.deleted_at.is_(None),
                )
            )
        ).all()
    ) if requested_ids else set()
    if valid_listing_ids:
        await session.execute(
            insert(Favorite)
            .values([{"user_id": user.id, "listing_id": listing_id} for listing_id in valid_listing_ids])
            .on_conflict_do_nothing(constraint="uq_favorites_user_listing")
        )
    for item in payload.savedSearches:
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
        )
    ).all()
    return [public_search(search) for search in searches]


async def create_saved_search(
    payload: SavedSearchWrite,
    user: User,
    session: AsyncSession,
) -> SavedSearchResponse:
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
    search = await session.scalar(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id)
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
    search = await session.scalar(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id)
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
    await session.execute(delete(SearchHistory).where(SearchHistory.user_id == user.id))
    await session.commit()


FAVORITES = Favorite
DISCARDED = DiscardedListing
