"""Real account lifecycle and authenticated collection management regressions."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from test_ai_saved_searches import PET, configured, saved_result

from app.api.dependencies import current_user
from app.db.session import SessionLocal
from app.main import app
from app.models import SavedSearch, User
from app.models.ai_saved_search import AiSavedSearch, AiSavedSearchCommand
from app.repositories.ai_saved_searches import SavedAIError
from app.schemas.searches import SavedSearchWrite
from app.services import users
from app.services.search_state import create_saved_search, saved_search_count

pytestmark = pytest.mark.integration


async def assert_removed(owner):
    async with SessionLocal() as conn:
        assert (await conn.get(User, owner.id)).deleted_at is not None
        for model in (SavedSearch, AiSavedSearch, AiSavedSearchCommand):
            assert await conn.scalar(select(func.count()).select_from(model).where(model.user_id == owner.id)) == 0


async def test_actual_self_delete_removes_manual_ai_snapshots_and_receipts():
    query, repo, owner, _, _ = await configured()
    await saved_result(query, repo, owner, PET)
    async with SessionLocal() as conn:
        user = await conn.get(User, owner.id)
        await create_saved_search(SavedSearchWrite(rentalMode="long"), user, conn)
        await users.delete_account(user, conn)
    await assert_removed(owner)


@pytest.mark.parametrize("first", ["save", "delete"])
async def test_self_delete_and_save_serialization_never_resurrects_private_data(monkeypatch, first):
    from app.repositories import ai_saved_searches
    from app.services.search_state import lock_saved_searches
    query, repo, owner, _, _ = await configured()
    _, result_ref = await saved_result(query, repo, owner, PET)
    acquired, proceed = asyncio.Event(), asyncio.Event()
    async def hold(*args):
        await lock_saved_searches(*args)
        acquired.set()
        await proceed.wait()
    monkeypatch.setattr(ai_saved_searches if first == "save" else users, "lock_saved_searches", hold)
    async def save():
        return await repo.save(owner, result_ref, idempotency_key=uuid4())
    async def remove():
        async with SessionLocal() as conn:
            await users.delete_account(await conn.get(User, owner.id), conn)
    task = asyncio.create_task(save() if first == "save" else remove())
    await asyncio.wait_for(acquired.wait(), 5)
    other = asyncio.create_task(remove() if first == "save" else save())
    try:
        await asyncio.sleep(0.05)
        assert not other.done()
    finally:
        proceed.set()
    results = await asyncio.wait_for(asyncio.gather(task, other, return_exceptions=True), 10)
    if first == "delete":
        assert isinstance(results[1], SavedAIError) and str(results[1]) == "REGISTERED_USER_UNAVAILABLE"
    else:
        assert not any(isinstance(item, BaseException) for item in results)
    await assert_removed(owner)


async def test_owned_paginated_management_and_rollback_overcap_without_data_loss(monkeypatch):
    from app.core.config import get_settings
    query, repo, owner, _, _ = await configured()
    _, result_ref = await saved_result(query, repo, owner, PET)
    await repo.save(owner, result_ref, name="Another", idempotency_key=uuid4())
    monkeypatch.setattr(get_settings(), "max_saved_searches_per_user", 2)
    # SQL written by an old binary knows only the manual table and its count.
    async with SessionLocal.begin() as conn:
        await conn.execute(text("INSERT INTO saved_searches(id,user_id,name,query,rental_mode,filters,polygon,alerts_enabled) "
            "VALUES (:id,:user,'old binary','','long','{}','[]',false)"), {"id": uuid4(), "user": owner.id})
    async with SessionLocal() as conn:
        assert await saved_search_count(owner.id, conn) == 3
        with pytest.raises(Exception) as error:
            await create_saved_search(SavedSearchWrite(rentalMode="long"), SimpleNamespace(id=owner.id), conn)
        assert getattr(error.value, "status_code", None) == 409
    async def owner_user():
        async with SessionLocal() as conn:
            return await conn.get(User, owner.id)
    app.dependency_overrides[current_user] = owner_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            first = await client.get("/api/v1/saved-searches/ai?limit=1")
            assert first.status_code == 200 and first.headers["cache-control"] == "private, no-store"
            page = first.json()
            assert page["collection_count"] == 3 and page["next_cursor"]
            assert not {"criteria", "intent", "intent_hash"}.intersection(page["items"][0])
            second = (await client.get("/api/v1/saved-searches/ai", params={"limit": 1, "after": page["next_cursor"]})).json()
            assert second["items"][0]["id"] != page["items"][0]["id"] and second["next_cursor"] is None
            for item in page["items"] + second["items"]:
                assert item["matcher"] == "ai.v1"
                assert (await client.delete(f'/api/v1/saved-searches/{item["id"]}')).status_code == 204
    finally:
        app.dependency_overrides.pop(current_user, None)
    async with SessionLocal() as conn:
        assert await saved_search_count(owner.id, conn) == 1
        await create_saved_search(SavedSearchWrite(rentalMode="long"), SimpleNamespace(id=owner.id), conn)


async def test_management_is_private_and_cross_owner_ids_cannot_be_deleted():
    query, repo, owner, _, _ = await configured()
    saved, _ = await saved_result(query, repo, owner, PET)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        assert (await client.get("/api/v1/saved-searches/ai")).status_code == 401
        async def foreign_user():
            return SimpleNamespace(id=uuid4())
        app.dependency_overrides[current_user] = foreign_user
        try:
            page = await client.get("/api/v1/saved-searches/ai")
            assert page.status_code == 200 and page.json()["items"] == []
            assert (await client.delete(f"/api/v1/saved-searches/{saved.id}")).status_code == 404
        finally:
            app.dependency_overrides.pop(current_user, None)
    assert (await repo.get(owner, saved.id)).id == saved.id


async def test_expand_only_downgrade_fails_without_stamp_or_snapshot_change():
    from pathlib import Path

    from alembic.config import Config

    from alembic import command
    query, repo, owner, _, _ = await configured()
    saved, _ = await saved_result(query, repo, owner, PET)
    backend = Path(__file__).parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    with pytest.raises(RuntimeError, match="SCHEMA_DOWNGRADE_DISABLED"):
        command.downgrade(config, "0073_ai_command_seed")
    async with SessionLocal() as conn:
        assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == "0077_ai_live_inputs"
    assert (await repo.get(owner, saved.id)).id == saved.id
