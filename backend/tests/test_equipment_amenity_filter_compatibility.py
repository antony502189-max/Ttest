from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models import Listing
from app.repositories.listings import apply_search_filters
from app.schemas.listings import ListingSearchRequest


def compiled_search(*amenities: str) -> str:
    query = apply_search_filters(select(Listing), ListingSearchRequest(amenities=list(amenities)))
    return str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_balcony_filter_accepts_legacy_and_structured_positive_value() -> None:
    sql = compiled_search("Balcón")
    assert "Balcón" in sql
    assert "Balcón disponible" in sql
    assert "Sin balcón" not in sql


def test_washing_machine_filter_accepts_both_structured_positive_values() -> None:
    sql = compiled_search("Lavadora")
    assert "Lavadora individual" in sql
    assert "Lavadora compartida" in sql
    assert "Sin lavadora" not in sql


def test_multiple_amenity_filters_remain_conjunctive() -> None:
    sql = compiled_search("Lavadora", "Ascensor")
    assert "Lavadora individual" in sql
    assert "Lavadora compartida" in sql
    assert "Ascensor" in sql
