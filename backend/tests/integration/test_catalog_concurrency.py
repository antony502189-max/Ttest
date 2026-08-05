import pytest

from app.db.session import SessionLocal
from app.models import CatalogState

pytestmark = pytest.mark.integration


async def test_concurrent_catalog_updates_do_not_lose_a_version_increment():
    async with SessionLocal() as setup:
        setup.add(CatalogState(id=1, version=1))
        await setup.commit()

    first = SessionLocal()
    second = SessionLocal()
    try:
        first_state = await first.get(CatalogState, 1)
        second_state = await second.get(CatalogState, 1)
        assert first_state is not None and second_state is not None

        first_state.version += 1
        second_state.version += 1
        await first.commit()
        await second.commit()
    finally:
        await first.close()
        await second.close()

    async with SessionLocal() as check:
        state = await check.get(CatalogState, 1)
        assert state is not None
        assert state.version == 3
