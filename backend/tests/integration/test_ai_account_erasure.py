"""Real account deletion removes private AI state and fences pending work."""
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import SavedSearch, User
from app.models.ai_saved_search import AiSavedSearch
from app.models.ai_search_quota import AISearchRequest, AIUsageDay
from app.models.ai_search_session import AISearchResult, AISearchSession
from app.repositories.ai_search_quota import QuotaError, QuotaLedger
from app.repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionError, SessionPolicy
from app.schemas.ai_search_intent import IntentPatch
from app.schemas.ai_search_quota import LeasePolicy, QuotaOperation, QuotaSubject, ResultReceipt
from app.services.admin_users import soft_delete_user
from app.services.users import delete_account

pytestmark = pytest.mark.integration


async def test_restore_barrier_reapplies_erasure_and_rejects_blank_replacement(tmp_path, monkeypatch):
    import base64

    from app.models.ai_operating_policy import AiErasureBinding
    from app.services.ai_erasure_journal import ErasureJournal, bind_journal, replay_erasure
    key, path = b"k" * 32, tmp_path / "events.sqlite"
    monkeypatch.setenv("AI_ERASURE_JOURNAL_PATH", str(path))
    monkeypatch.setenv("AI_ERASURE_JOURNAL_KEY", base64.b64encode(key).decode())
    journal = ErasureJournal(path, key, initialize=True)
    await bind_journal(SessionLocal, journal, initialize=True)
    user = User(email=f"ai-restore-{uuid4().hex}@example.test", name="Synthetic", password_hash="unused",
        role="tenant", initials="S", email_verified=True)
    async with SessionLocal() as conn:
        conn.add(user)
        await conn.commit()
    owner = QuotaSubject(kind="auth", id=user.id)
    ledger = QuotaLedger(SessionLocal, LeasePolicy(reservation_seconds=10, running_seconds=30, recovery_grace_seconds=10))
    store = SearchSessions(ledger, SessionPolicy(inactivity_seconds=86400),
        IntentVocabulary(frozenset(), frozenset(), frozenset()), require_auth_owner=True)
    snapshot = await store.create(owner, idempotency_key=uuid4())
    # Models a rollback or restoring the pre-deletion DB snapshot: independent
    # accepted deletion intent remains while the SQL account is still active.
    journal.append(user.id)
    with pytest.raises(SessionError, match="SESSION_NOT_FOUND"):
        await store.create(owner)
    assert await replay_erasure(SessionLocal, journal) == 1
    async with SessionLocal() as conn:
        assert (await conn.get(User, user.id)).deleted_at is not None
        assert await conn.get(AISearchSession, snapshot.intent.session_id) is None
        assert await conn.get(AiErasureBinding, 1) is not None
    assert await replay_erasure(SessionLocal, journal) == 1
    replacement = ErasureJournal(tmp_path / "blank.sqlite", key, initialize=True)
    with pytest.raises(ValueError, match="BINDING_INVALID"):
        await bind_journal(SessionLocal, replacement, initialize=True)


async def test_account_deletion_physically_erases_ai_and_prevents_resurrection():
    user = User(email=f"ai-erasure-{uuid4().hex}@example.test", name="Synthetic", password_hash="unused",
        role="tenant", initials="S", email_verified=True)
    async with SessionLocal() as conn:
        conn.add(user)
        await conn.commit()
    ledger = QuotaLedger(SessionLocal, LeasePolicy(reservation_seconds=10, running_seconds=30, recovery_grace_seconds=10))
    store = SearchSessions(ledger, SessionPolicy(inactivity_seconds=86400),
        IntentVocabulary(frozenset(), frozenset(), frozenset()), require_auth_owner=True)
    owner = QuotaSubject(kind="auth", id=user.id)
    first, pending = await store.create(owner), await store.create(owner)
    def operation(snapshot):
        return QuotaOperation(idempotency_key=uuid4(), channel="text", payload_sha256="a" * 64,
            session_id=snapshot.intent.session_id, expected_session_version=0)
    succeeded, running = operation(first), operation(pending)
    for op in (succeeded, running):
        await ledger.reserve(owner, op)
        await ledger.claim(owner, op)
    receipt = ResultReceipt(result_ref=uuid4(), count=0)
    patch = IntentPatch(schema_version="ai-search.v1", session_id=first.intent.session_id, expected_version=0)
    assert (await store.finalize_patch(owner, succeeded, 1, patch, receipt)).status == "succeeded"
    async with SessionLocal() as conn:
        current = await conn.get(User, user.id)
        await delete_account(current, conn)
    async with SessionLocal() as conn:
        for model in (AISearchResult, AISearchSession, AISearchRequest, AIUsageDay):
            assert await conn.scalar(select(func.count()).select_from(model).where(
                model.subject_kind == "auth", model.subject_id == user.id)) == 0
    with pytest.raises(SessionError, match="SESSION_NOT_FOUND"):
        await store.create(owner)
    with pytest.raises(QuotaError, match="OPERATION_NOT_FOUND"):
        await ledger.claim(owner, running)
    with pytest.raises(SessionError, match="RESULT_NOT_FOUND"):
        await store.result(owner, receipt.result_ref)


async def test_administrative_deletion_also_removes_independent_ai_saved_snapshot():
    target = User(email=f"ai-erasure-target-{uuid4().hex}@example.test", name="Synthetic", password_hash="unused",
        role="tenant", initials="S", email_verified=True)
    actor = User(email=f"ai-erasure-actor-{uuid4().hex}@example.test", name="Synthetic Actor", password_hash="unused",
        role="tenant", initials="S", email_verified=True)
    saved_id = uuid4()
    async with SessionLocal() as conn:
        conn.add_all([target, actor])
        await conn.flush()
        conn.add(SavedSearch(id=saved_id, user_id=target.id, name="Synthetic AI", matcher="ai.v1", rental_mode="long",
            query="", filters={}, polygon=[], alerts_enabled=False))
        await conn.flush()
        conn.add(AiSavedSearch(saved_search_id=saved_id, user_id=target.id, name="Synthetic AI", matcher="ai.v1", revision=1, enabled=False,
            schema_version="ai-search.v1", taxonomy_version="rental.v1", criteria={}, intent_hash="a" * 64))
        await conn.commit()
        await soft_delete_user(target.id, reason="Synthetic erasure regression", actor=actor, session=conn)
        await conn.commit()
    async with SessionLocal() as conn:
        assert await conn.get(AiSavedSearch, saved_id) is None
        assert await conn.get(SavedSearch, saved_id) is None
        assert (await conn.get(User, target.id)).deleted_at is not None
