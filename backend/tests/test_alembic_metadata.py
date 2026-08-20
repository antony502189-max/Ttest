import app.models  # noqa: F401
from app.db.base import Base


def test_all_mapped_application_tables_are_registered_for_alembic() -> None:
    required = {
        "admin_access",
        "listing_promotions",
        "listing_room_details",
        "storage_deletion_jobs",
    }
    assert required <= set(Base.metadata.tables)
