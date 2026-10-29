"""Actual saved-search migration and sessions in an isolated disposable schema.

Minimal named legacy tables below are stand-ins. Full legacy/PostGIS schema and
matcher parity are tested separately in integration/test_ai_saved_searches.py.
"""
import asyncio
import importlib.util
from contextlib import AsyncExitStack
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import delete, event, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_sessions import complete

from app.models import SavedSearch
from app.models.ai_saved_search import AiSavedSearch
from app.models.ai_search_quota import AISearchRequest
from app.models.ai_search_session import AISearchSession
from app.repositories.ai_saved_searches import RegisteredAISearches, SavedAIError
from app.repositories.ai_search_sessions import SessionError
from app.schemas.ai_search_quota import QuotaSubject
from app.schemas.searches import SavedSearchPatch, SavedSearchWrite
from app.services.search_state import create_saved_search, list_saved_searches, update_saved_search

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def saved_store(store, pg):
    async with pg[1].begin() as conn:
        await conn.execute(text("CREATE TABLE users (id uuid PRIMARY KEY, blocked boolean NOT NULL DEFAULT false, deleted_at timestamptz)"))
        await conn.execute(text("CREATE TABLE user_restrictions (id uuid PRIMARY KEY, user_id uuid NOT NULL, restriction_type text, "
                                "revoked_at timestamptz, starts_at timestamptz NOT NULL DEFAULT now(), ends_at timestamptz)"))
        await conn.execute(text("CREATE TYPE rental_mode AS ENUM ('long','holiday')"))
        await conn.execute(text("CREATE TABLE saved_searches (id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
            "name varchar(120) NOT NULL, query varchar(240) NOT NULL, rental_mode rental_mode NOT NULL, "
            "filters jsonb NOT NULL, polygon jsonb NOT NULL, alerts_enabled boolean NOT NULL, province_code varchar(2), "
            "created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())"))
        # Check actual upgrade defaults preserve a preexisting manual search.
        legacy_user, legacy_saved = uuid4(), uuid4()
        await conn.execute(text("INSERT INTO users(id) VALUES (:id)"), {"id": legacy_user})
        await conn.execute(text("INSERT INTO saved_searches(id,user_id,name,query,rental_mode,filters,polygon,alerts_enabled) "
                                "VALUES (:id,:user,'legacy','','long','{}','[]',true)"), {"id": legacy_saved, "user": legacy_user})
        def migrate(sync):
            path = Path(__file__).parents[2] / "alembic/versions/0074_ai_saved_searches.py"
            spec = importlib.util.spec_from_file_location("saved_migration", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(sync.connection())):
                module.upgrade()
        await conn.run_sync(migrate)
        assert await conn.scalar(select(SavedSearch.matcher).where(SavedSearch.id == legacy_saved)) == "manual.v1"
    return RegisteredAISearches(store, SimpleNamespace(sessions=pg[1]))


async def registered(saved_store, pg):
    owner = QuotaSubject(kind="auth", id=uuid4())
    async with pg[1].begin() as conn:
        await conn.execute(text("INSERT INTO users(id) VALUES (:id)"), {"id": owner.id})
    initial = await saved_store.sessions.create(owner)
    _, receipt, _ = await complete(saved_store.sessions, owner, initial, {"balcony": {"strength": "hard", "value": False}})
    return owner, initial, receipt


async def test_owned_original_snapshot_independent_of_followup_reset_and_expiry(saved_store, pg):
    owner, initial, receipt = await registered(saved_store, pg)
    snapshot = await saved_store.save(owner, receipt.result_ref, name="saved")
    current = await saved_store.sessions.get(owner, initial.intent.session_id)
    await complete(saved_store.sessions, owner, current, {"balcony": {"strength": "hard", "value": True}})
    second = await saved_store.save(owner, receipt.result_ref)
    assert second.intent == snapshot.intent and second.intent_hash == snapshot.intent_hash
    assert second.id != snapshot.id and snapshot.intent.criteria.balcony.value is False
    await saved_store.sessions.reset(owner, initial.intent.session_id, 2)
    assert await saved_store.get(owner, snapshot.id) == snapshot
    async with pg[1]() as conn:
        row = await conn.scalar(select(AiSavedSearch).where(AiSavedSearch.saved_search_id == snapshot.id))
        assert not {"session_id", "result_ref"}.intersection(row.criteria)
        assert await conn.scalar(select(func.count()).select_from(AISearchRequest)) == 2
        assert await list_saved_searches(SimpleNamespace(id=owner.id), conn) == []


async def test_guest_foreign_result_and_nonregistered_subject_cannot_save(saved_store, pg):
    owner, _, receipt = await registered(saved_store, pg)
    with pytest.raises(SavedAIError, match="REGISTERED_USER_REQUIRED"):
        await saved_store.save(QuotaSubject(kind="guest", id=owner.id), receipt.result_ref)
    with pytest.raises(SavedAIError, match="REGISTERED_USER_UNAVAILABLE"):
        await saved_store.save(QuotaSubject(kind="auth", id=uuid4()), receipt.result_ref)
    other, _, _ = await registered(saved_store, pg)
    with pytest.raises(SessionError, match="RESULT_NOT_FOUND"):
        await saved_store.save(other, receipt.result_ref)
    snapshot = await saved_store.save(owner, receipt.result_ref)
    with pytest.raises(SavedAIError, match="SAVED_AI_NOT_FOUND"):
        await saved_store.get(other, snapshot.id)


async def test_expired_result_cannot_be_saved_but_previous_saved_snapshot_survives(saved_store, pg):
    owner, initial, receipt = await registered(saved_store, pg)
    snapshot = await saved_store.save(owner, receipt.result_ref)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).where(AISearchSession.id == initial.intent.session_id).values(
            expires_at=text("clock_timestamp()-interval '1 second'")))
    with pytest.raises(SessionError, match="RESULT_EXPIRED_REQUERY_REQUIRED"):
        await saved_store.save(owner, receipt.result_ref)
    assert await saved_store.get(owner, snapshot.id) == snapshot


@pytest.mark.parametrize("corrupt", ["criteria", "hash", "vocabulary", "schema"])
async def test_corrupt_snapshot_or_vocabulary_fails_closed(saved_store, pg, corrupt):
    owner, _, receipt = await registered(saved_store, pg)
    snapshot = await saved_store.save(owner, receipt.result_ref)
    changes = {"criteria": {"invented": {"strength": "hard", "value": True}}} if corrupt == "criteria" else {"intent_hash": "a" * 64}
    if corrupt == "vocabulary":
        changes = {"criteria": {"amenities": {"strength": "hard", "value": ["unsupported"]}}}
    async with pg[1].begin() as conn:
        if corrupt == "schema":
            # DB check protects direct writes; bypass only to test read corruption.
            await conn.execute(text("ALTER TABLE ai_saved_searches DROP CONSTRAINT ck_ai_saved_versions"))
            changes = {"schema_version": "future"}
        await conn.execute(update(AiSavedSearch).where(AiSavedSearch.saved_search_id == snapshot.id).values(**changes))
    with pytest.raises(SavedAIError, match="SAVED_AI_STATE_INVALID"):
        await saved_store.get(owner, snapshot.id)


async def test_disable_cas_legacy_patch_guard_and_delete_cascade(saved_store, pg):
    from fastapi import HTTPException
    owner, _, receipt = await registered(saved_store, pg)
    snapshot = await saved_store.save(owner, receipt.result_ref)
    disabled = await saved_store.set_enabled(owner, snapshot.id, 1, False)
    assert not disabled.enabled and disabled.revision == 2 and disabled.intent_hash == snapshot.intent_hash
    with pytest.raises(SavedAIError, match="SAVED_AI_VERSION_CONFLICT"):
        await saved_store.set_enabled(owner, snapshot.id, 1, True)
    dry = await saved_store.dry_run(owner, snapshot.id, uuid4())
    assert dry.status == "disabled" and dry.delivery_enabled is False
    async with pg[1]() as conn:
        with pytest.raises(HTTPException) as error:
            await update_saved_search(snapshot.id, SavedSearchPatch(alertsEnabled=True), SimpleNamespace(id=owner.id), conn)
        assert error.value.status_code == 404
    async with pg[1].begin() as conn:
        await conn.execute(delete(SavedSearch).where(SavedSearch.id == snapshot.id))
    with pytest.raises(SavedAIError, match="SAVED_AI_NOT_FOUND"):
        await saved_store.get(owner, snapshot.id)
    async with pg[1]() as conn:
        assert await conn.scalar(select(func.count()).select_from(AiSavedSearch)) == 0


@pytest.mark.parametrize("changes", [{"alerts_enabled": True}, {"rental_mode": "long"}, {"filters": {"balcony": True}},
                                    {"query": "legacy text"}, {"polygon": [{"lat": 1, "lng": 1}]}])
async def test_database_prevents_old_binary_ai_parent_delivery_and_hybrids(saved_store, pg, changes):
    owner, _, receipt = await registered(saved_store, pg)
    snapshot = await saved_store.save(owner, receipt.result_ref)
    with pytest.raises(IntegrityError):
        async with pg[1].begin() as conn:
            await conn.execute(update(SavedSearch).where(SavedSearch.id == snapshot.id).values(**changes))


@pytest.mark.parametrize("change", ["blocked", "deleted", "restricted"])
async def test_current_owner_state_rechecked_for_get_disable_and_dryrun(saved_store, pg, change):
    owner, _, receipt = await registered(saved_store, pg)
    snapshot = await saved_store.save(owner, receipt.result_ref)
    async with pg[1].begin() as conn:
        if change == "restricted":
            await conn.execute(text("INSERT INTO user_restrictions(id,user_id,restriction_type) VALUES (:id,:owner,'full')"),
                               {"id": uuid4(), "owner": owner.id})
        else:
            await conn.execute(text("UPDATE users SET " + ("blocked=true" if change == "blocked" else "deleted_at=now()") + " WHERE id=:id"), {"id": owner.id})
    for call in (saved_store.get(owner, snapshot.id), saved_store.set_enabled(owner, snapshot.id, 1, False),
                 saved_store.dry_run(owner, snapshot.id, uuid4())):
        with pytest.raises(SavedAIError, match="REGISTERED_USER_UNAVAILABLE"):
            await call


async def test_manual_create_list_update_still_use_only_manual_matcher(saved_store, pg):
    owner, _, receipt = await registered(saved_store, pg)
    await saved_store.save(owner, receipt.result_ref)
    user = SimpleNamespace(id=owner.id)
    async with pg[1]() as conn:
        manual = await create_saved_search(SavedSearchWrite(rentalMode="holiday", filters={"maxPrice": 75}), user, conn)
        rows = await list_saved_searches(user, conn)
        assert len(rows) == 1 and rows[0].id == manual.id and rows[0].rentalMode == "holiday"
        changed = await update_saved_search(manual.id, SavedSearchPatch(name="new", alertsEnabled=False), user, conn)
        assert changed.name == "new" and changed.alertsEnabled is False


async def test_concurrent_ai_and_manual_saves_share_existing_collection_limit(saved_store, pg, monkeypatch):
    from fastapi import HTTPException

    from app.core.config import get_settings
    owner, _, receipt = await registered(saved_store, pg)
    monkeypatch.setattr(get_settings(), "max_saved_searches_per_user", 1)
    async def manual():
        async with pg[1]() as conn:
            return await create_saved_search(SavedSearchWrite(rentalMode="long"), SimpleNamespace(id=owner.id), conn)
    results = await asyncio.gather(saved_store.save(owner, receipt.result_ref), manual(), return_exceptions=True)
    assert sum(not isinstance(item, Exception) for item in results) == 1
    assert sum(isinstance(item, (SavedAIError, HTTPException)) for item in results) == 1
    async with pg[1]() as conn:
        assert await conn.scalar(select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == owner.id)) == 1


@pytest_asyncio.fixture
async def small_saved_store(saved_store, pg, monkeypatch, request):
    owner, initial, receipt = await registered(saved_store, pg)
    async with pg[1]() as conn:
        schema = await conn.scalar(text("select current_schema()"))
    size = request.param
    engine = create_async_engine(pg[1].kw["bind"].url, pool_size=size, max_overflow=0, pool_timeout=0.5,
        connect_args={"server_settings": {"search_path": schema}})
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(saved_store.sessions.ledger, "sessions", maker)
    repository = RegisteredAISearches(saved_store.sessions, SimpleNamespace(sessions=maker))
    try:
        yield repository, owner, initial, receipt, maker, engine, size
    finally:
        await engine.dispose()


@pytest.mark.parametrize("small_saved_store", [1, 2], indirect=True)
async def test_save_uses_one_checkout_even_with_minimum_or_saturated_pool(small_saved_store):
    repository, owner, _, receipt, _, engine, size = small_saved_store
    checkouts = []
    event.listen(engine.sync_engine, "checkout", lambda *args: checkouts.append(1))
    async with AsyncExitStack() as stack:
        if size == 2:
            await stack.enter_async_context(engine.connect())  # Occupy every connection except one.
        before = len(checkouts)
        saved = await asyncio.wait_for(repository.save(owner, receipt.result_ref), 2)
        assert len(checkouts) - before == 1
    assert saved.intent.criteria.balcony.value is False
    assert await repository.get(owner, saved.id) == saved


@pytest.mark.parametrize("small_saved_store", [1, 2], indirect=True)
async def test_concurrent_small_pool_ai_and_manual_collection_cap_is_atomic(small_saved_store, monkeypatch):
    from fastapi import HTTPException

    from app.core.config import get_settings
    repository, owner, _, receipt, maker, _, _ = small_saved_store
    # First prove concurrent valid saves succeed when the pool is saturated by
    # save transactions themselves (rather than masking pool failures as caps).
    saved = await asyncio.wait_for(asyncio.gather(*(repository.save(owner, receipt.result_ref) for _ in range(3))), 4)
    assert len({value.id for value in saved}) == 3
    async with maker.begin() as conn:
        await conn.execute(delete(SavedSearch).where(SavedSearch.user_id == owner.id))
    monkeypatch.setattr(get_settings(), "max_saved_searches_per_user", 1)
    async def manual():
        async with maker() as conn:
            return await create_saved_search(SavedSearchWrite(rentalMode="long"), SimpleNamespace(id=owner.id), conn)
    outcomes = await asyncio.wait_for(asyncio.gather(repository.save(owner, receipt.result_ref),
        repository.save(owner, receipt.result_ref), manual(), return_exceptions=True), 4)
    assert sum(not isinstance(item, Exception) for item in outcomes) == 1
    failures = [value for value in outcomes if isinstance(value, Exception)]
    assert len(failures) == 2
    assert all(isinstance(value, (SavedAIError, HTTPException)) for value in failures)
    async with maker() as conn:
        assert await conn.scalar(select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == owner.id)) == 1


@pytest.mark.parametrize("small_saved_store", [1], indirect=True)
@pytest.mark.parametrize("failure", ["foreign", "expired", "blocked", "deleted", "hash", "schema", "binding"])
async def test_same_connection_result_read_preserves_all_guards(small_saved_store, failure):
    from app.models.ai_search_session import AISearchResult
    repository, owner, initial, receipt, maker, _, _ = small_saved_store
    caller = owner
    async with maker.begin() as conn:
        if failure == "foreign":
            caller = QuotaSubject(kind="auth", id=uuid4())
            await conn.execute(text("INSERT INTO users(id) VALUES (:id)"), {"id": caller.id})
        elif failure == "expired":
            await conn.execute(update(AISearchSession).where(AISearchSession.id == initial.intent.session_id).values(
                expires_at=text("clock_timestamp()-interval '1 second'")))
        elif failure in {"blocked", "deleted"}:
            await conn.execute(text("UPDATE users SET " + ("blocked=true" if failure == "blocked" else "deleted_at=now()")
                + " WHERE id=:id"), {"id": owner.id})
        else:
            row = await conn.scalar(select(AISearchResult).where(AISearchResult.id == receipt.result_ref))
            if failure == "hash":
                row.intent_hash = "0" * 64
            elif failure == "schema":
                row.intent = {**row.intent, "schema_version": "future"}
            else:
                row.session_version += 1
    with pytest.raises((SessionError, SavedAIError)):
        await repository.save(caller, receipt.result_ref)
    async with maker() as conn:
        assert await conn.scalar(select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == owner.id)) == 0
        assert await conn.scalar(select(func.count()).select_from(AISearchRequest)) == 1
