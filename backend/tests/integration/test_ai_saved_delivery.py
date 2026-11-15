"""Real SQL: immutable guest handoff, baseline, fencing and current delivery."""
import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text, update
from test_ai_saved_searches import PET, configured, saved_result

from app.db.session import SessionLocal
from app.models import Listing, MailOutbox, Notification, User
from app.models.ai_query_proof import AiQueryProof
from app.models.ai_saved_rematch import AiSavedRematch, AiSavedSeen
from app.models.ai_saved_search import AiSavedSearch
from app.models.ai_search_quota import AIUsageDay
from app.repositories.ai_saved_searches import SavedAIError
from app.schemas.ai_search_quota import QuotaSubject
from app.services.ai_saved_handoff import SavedHandoffSigner
from app.services.ai_saved_notifications import SavedNotificationWorker
from app.services.search_state import delete_saved_search

pytestmark = pytest.mark.integration


async def setup_saved():
    query, repo, subject, ids, _sources = await configured()
    _, result_ref = await saved_result(query, repo, subject, PET)
    signer = SavedHandoffSigner(b"s" * 32)
    committed = await query.sessions.result(subject, result_ref)
    token = signer.issue(committed)
    saved = await repo.save_handoff(subject, token, signer, notifications=True)
    return query, repo, subject, ids, signer, token, saved


async def due(saved_id):
    async with SessionLocal.begin() as conn:
        await conn.execute(update(AiSavedRematch).where(AiSavedRematch.saved_search_id == saved_id)
            .values(next_at=text("clock_timestamp()-interval '1 second'")))


async def unseen(saved_id, listing_id):
    async with SessionLocal.begin() as conn:
        await conn.execute(delete(AiSavedSeen).where(AiSavedSeen.saved_search_id == saved_id,
            AiSavedSeen.listing_id == listing_id))


async def test_handoff_retry_concurrent_copy_and_deleted_receipt_never_resurrects():
    query, repo, subject, _, signer, token, saved = await setup_saved()
    snapshots = await asyncio.gather(*[repo.save_handoff(subject, token, signer, notifications=True) for _ in range(4)])
    assert {item.id for item in snapshots} == {saved.id}
    assert saved.intent.criteria.pets == (await query.sessions.result(subject, signer.verify(token).result_ref)).intent.criteria.pets
    async with SessionLocal() as conn:
        assert await conn.scalar(select(func.count()).select_from(AiSavedRematch)) == 1
        await delete_saved_search(saved.id, type("Owner", (), {"id": subject.id})(), conn)
    with pytest.raises(SavedAIError, match="SAVED_AI_DELETED"):
        await repo.save_handoff(subject, token, signer, notifications=True)
    with pytest.raises(SavedAIError, match="REGISTERED_USER_REQUIRED"):
        await repo.save_handoff(QuotaSubject(kind="guest", id=subject.id), token, signer)


async def test_baseline_no_alert_then_new_match_once_without_email_or_model_quota():
    _, repo, subject, ids, _, _, saved = await setup_saved()
    worker = SavedNotificationWorker(repo, daily_limit=20, batch_size=20, cadence_seconds=60)
    async with SessionLocal() as conn:
        used = await conn.scalar(select(func.sum(AIUsageDay.used)))
        seen = set(await conn.scalars(select(AiSavedSeen.listing_id).where(AiSavedSeen.saved_search_id == saved.id)))
    assert seen
    assert await worker.run(await worker.claim()) == 0
    new_id = next(iter(seen))
    await unseen(saved.id, new_id)
    await due(saved.id)
    claim = await worker.claim()
    assert claim and await worker.run(claim) == 1
    assert await worker.run(claim) == 0
    await due(saved.id)
    assert await worker.run(await worker.claim()) == 0
    async with SessionLocal() as conn:
        alerts = list(await conn.scalars(select(Notification).where(Notification.recipient_user_id == subject.id)))
        assert len(alerts) == 1 and alerts[0].entity_listing_id == new_id and new_id in ids
        assert await conn.scalar(select(func.count()).select_from(MailOutbox)) == 0
        assert await conn.scalar(select(func.sum(AIUsageDay.used))) == used


@pytest.mark.parametrize("change", ["disable", "delete", "proof", "fence", "lease", "revision", "user_block", "listing_hidden", "foreign_owner"])
async def test_claim_cannot_authorize_stale_or_disabled_or_deleted_delivery(change):
    _, repo, subject, _, _, _, saved = await setup_saved()
    worker = SavedNotificationWorker(repo, daily_limit=20, batch_size=20, cadence_seconds=60)
    async with SessionLocal() as conn:
        listing_id = await conn.scalar(select(AiSavedSeen.listing_id).where(AiSavedSeen.saved_search_id == saved.id).limit(1))
    await unseen(saved.id, listing_id)
    claim = await worker.claim()
    if change == "disable":
        await repo.set_enabled(subject, saved.id, 1, False)
    elif change == "delete":
        async with SessionLocal() as conn:
            await delete_saved_search(saved.id, type("Owner", (), {"id": subject.id})(), conn)
    elif change == "proof":
        async with SessionLocal.begin() as conn:
            await conn.execute(delete(AiQueryProof).where(AiQueryProof.canonical_listing_id == listing_id))
    elif change == "revision":
        await repo.set_enabled(subject, saved.id, 1, False)
        await repo.set_enabled(subject, saved.id, 2, True)
    elif change == "fence":
        claim = replace(claim, fence=claim.fence + 1)
    elif change == "foreign_owner":
        claim = replace(claim, owner_id=uuid4())
    elif change == "user_block":
        async with SessionLocal.begin() as conn:
            await conn.execute(update(User).where(User.id == subject.id).values(blocked=True))
    elif change == "listing_hidden":
        async with SessionLocal.begin() as conn:
            await conn.execute(update(Listing).where(Listing.id == listing_id).values(deleted_at=func.now()))
    else:
        async with SessionLocal.begin() as conn:
            await conn.execute(update(AiSavedRematch).values(lease_until=text("clock_timestamp()-interval '1 second'")))
    assert await worker.run(claim) == 0
    async with SessionLocal() as conn:
        assert await conn.scalar(select(func.count()).select_from(Notification)) == 0
        if change == "delete":
            assert await conn.get(AiSavedSearch, saved.id) is None
            assert await conn.get(AiSavedRematch, saved.id) is None
            assert not list(await conn.scalars(select(AiSavedSeen).where(AiSavedSeen.saved_search_id == saved.id)))


async def test_expired_claim_reclaimed_with_new_fence_and_daily_budget_shared():
    _, repo, subject, _, _, _, saved = await setup_saved()
    worker = SavedNotificationWorker(repo, daily_limit=1, batch_size=20, cadence_seconds=60)
    async with SessionLocal.begin() as conn:
        await conn.execute(delete(AiSavedSeen).where(AiSavedSeen.saved_search_id == saved.id))
    first = await worker.claim()
    assert await worker.claim() is None
    async with SessionLocal.begin() as conn:
        await conn.execute(update(AiSavedRematch).values(lease_until=text("clock_timestamp()-interval '1 second'")))
    replacement = await worker.claim()
    assert replacement.fence > first.fence and replacement.token != first.token
    assert await worker.run(first) == 0
    assert await worker.run(replacement) == 1
    await due(saved.id)
    assert await worker.run(await worker.claim()) == 0
    async with SessionLocal() as conn:
        assert await conn.scalar(select(func.count()).select_from(Notification).where(Notification.recipient_user_id == subject.id)) == 1


async def test_actual_account_erasure_cascades_scan_seen_and_claim_authority():
    from app.services.users import delete_account
    _, repo, subject, _, _, _, saved = await setup_saved()
    worker = SavedNotificationWorker(repo, daily_limit=20, batch_size=20, cadence_seconds=60)
    claim = await worker.claim()
    async with SessionLocal() as conn:
        await delete_account(await conn.get(User, subject.id), conn)
    assert await worker.run(claim) == 0
    async with SessionLocal() as conn:
        assert await conn.get(AiSavedRematch, saved.id) is None
        assert not list(await conn.scalars(select(AiSavedSeen).where(AiSavedSeen.saved_search_id == saved.id)))
        assert await conn.scalar(select(func.count()).select_from(Notification)) == 0
