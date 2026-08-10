from app.services import catalog, external_import


def test_external_import_reuses_atomic_catalog_touch() -> None:
    assert external_import.touch_catalog is catalog.touch_catalog
