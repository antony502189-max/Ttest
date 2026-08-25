from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models import Listing
from app.repositories.listings import apply_search_filters
from app.schemas.listings import ListingSearchRequest


def compiled_search(*amenities: str) -> tuple[str, list[object]]:
    query = apply_search_filters(select(Listing), ListingSearchRequest(amenities=list(amenities)))
    compiled = query.compile(dialect=postgresql.dialect())
    return str(compiled), list(compiled.params.values())


def test_balcony_filter_accepts_legacy_and_structured_positive_value() -> None:
    sql, params = compiled_search("Balcón")
    assert " OR " in sql
    assert ["Balcón"] in params
    assert ["Balcón disponible"] in params
    assert ["Sin balcón"] not in params


def test_washing_machine_filter_accepts_both_structured_positive_values() -> None:
    sql, params = compiled_search("Lavadora")
    assert sql.count(" OR ") >= 2
    assert ["Lavadora"] in params
    assert ["Lavadora individual"] in params
    assert ["Lavadora compartida"] in params
    assert ["Sin lavadora"] not in params


def test_multiple_amenity_filters_remain_conjunctive() -> None:
    sql, params = compiled_search("Lavadora", "Ascensor")
    assert " AND " in sql
    assert ["Lavadora individual"] in params
    assert ["Lavadora compartida"] in params
    assert ["Ascensor"] in params
