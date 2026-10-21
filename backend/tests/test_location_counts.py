from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy.dialects import postgresql

from app.api.v1 import listings
from app.schemas.listings import ListingSearchRequest


async def test_location_counts_match_city_aliases_provinces_and_legacy_fallback(monkeypatch):
    monkeypatch.setattr(listings, 'enforce_listing_view_access', AsyncMock())
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [
        ('38', 'adeje', 3), ('38', 'la laguna', 2), ('38', 'san cristobal de la laguna', 4),
        (None, 'adeje', 1), (None, 'cabanes', 7), ('12', 'cabanes', 2), ('17', 'cabanes', 5),
    ])))
    result = await listings.province_counts(ListingSearchRequest(), session, None)
    provinces = {row['id']: row['count'] for row in result['items']}
    municipalities = {row['id']: row['count'] for row in result['municipalities']}
    assert provinces['38'] == 9
    assert provinces['28'] == 0
    assert municipalities['38001'] == 4
    assert municipalities['38023'] == 6
    assert municipalities['12033'] == 2
    assert municipalities['17030'] == 5
    assert municipalities.get('38004', 0) == 0


async def test_counts_keep_public_visibility_and_non_location_filters(monkeypatch):
    monkeypatch.setattr(listings, 'enforce_listing_view_access', AsyncMock())
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=list)))
    payload = ListingSearchRequest(municipalityCode='38004', provinceCode='38', query='Arafo',
                                   rentalMode='holiday', minPrice=50, maxPrice=100)
    await listings.province_counts(payload, session, None)
    statement = session.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    values = statement.params.values()
    assert 'Arafo' not in values and '38' not in values
    assert 'holiday' in values and 50 in values and 100 in values
    assert 'published' in values
    assert 'listings.deleted_at IS NULL' in str(statement)
    assert 'users.blocked IS false' in str(statement)
