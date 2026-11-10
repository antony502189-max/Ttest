"""One real disposable-PG operation; every ASR/intent/query is an offline fake."""
import asyncio
import hashlib
import json
import time
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, text, update
from test_deepseek_execution import parser as offline_parser
from test_execution import Gate, Parser, Query, card_request_mutations
from test_sessions import usage

from app.models.ai_search_quota import AISearchRequest, AIUsageDay
from app.models.ai_search_session import AISearchSession
from app.repositories.ai_search_quota import QuotaError
from app.repositories.ai_search_sessions import SessionError
from app.repositories.ai_verified_cards import SourceCoverageUnavailable
from app.schemas.ai_search_quota import QuotaOperation, QuotaSubject
from app.schemas.listings import ListingCardSearchRequest
from app.services.ai_http_policy import HTTP_DEADLINE
from app.services.ai_search_attempts import AIAttemptRejected
from app.services.ai_search_execution import TextSearchExecution
from app.services.ai_voice_execution import VoicePolicy, VoiceSearchExecution

pytestmark = pytest.mark.integration
AUDIO = b"synthetic-private-audio"


def policy(**changes):
    return VoicePolicy(media_types=("audio/wav", "audio/webm"), max_audio_bytes=1024, max_transcript_bytes=1024,
                       asr_budget_seconds=1.0, intent_budget_seconds=1.0, total_budget_seconds=3.0, **changes)


class ASR:
    def __init__(self):
        self.calls, self.error, self.result = 0, None, "synthetic private transcript"
        self.started, self.finish = asyncio.Event(), None

    async def transcribe(self, audio, media):
        self.calls += 1
        self.started.set()
        assert audio == AUDIO and media == "audio/wav"
        if self.finish:
            await self.finish.wait()
        if self.error:
            raise self.error
        return self.result


async def configured(store):
    subject = QuotaSubject(kind="guest", id=uuid4())
    snapshot = await store.create(subject)
    asr, parser, gate, query = ASR(), Parser(), Gate(), Query(store)
    service = VoiceSearchExecution(store, asr, parser, gate, query, policy())
    return subject, snapshot, asr, parser, gate, query, service


async def test_voice_metrics_count_success_and_replay_without_private_labels(store,pg):
    from prometheus_client import REGISTRY, generate_latest
    subject,snapshot,asr,parser,_,_,service=await configured(store)
    def value(name,labels=None):return REGISTRY.get_sample_value(name,labels or {}) or 0
    labels={'status':'succeeded','replay':'no','failure':'none'}
    before=value('ttest_ai_voice_execution_total',labels)
    asr_before=value('ttest_ai_voice_asr_seconds_count')
    key=uuid4()
    await execute(service,subject,snapshot,key)
    assert value('ttest_ai_voice_execution_total',labels)==before+1
    await execute(service,subject,snapshot,key)
    assert value('ttest_ai_voice_asr_seconds_count')==asr_before+1
    assert 'synthetic private transcript' not in generate_latest().decode()
    assert str(subject.id) not in generate_latest().decode()
    assert asr.calls==parser.calls==1 and await usage(pg,subject)==(1,0)


@pytest.mark.parametrize('phase',['claim','finalize','timeout','cancel'])
async def test_voice_uncertain_phase_metrics_never_claim_a_failed_debit(store,pg,monkeypatch,phase):
    from prometheus_client import REGISTRY, generate_latest
    subject,snapshot,asr,_,_,_,service=await configured(store)
    failure='cancelled' if phase=='cancel' else 'timeout' if phase=='timeout' else 'unavailable'
    labels={'status':'uncertain','replay':'no','failure':failure}
    before=REGISTRY.get_sample_value('ttest_ai_voice_execution_total',labels) or 0
    async def fail(*args,**kwargs):raise RuntimeError('PRIVATE_TRANSCRIPT_AND_ID')
    if phase=='claim':monkeypatch.setattr(service.ledger,'claim',fail)
    if phase=='finalize':monkeypatch.setattr(store,'finalize_patch',fail)
    if phase in {'timeout','cancel'}:
        asr.finish=asyncio.Event()
        if phase=='timeout':service.policy=policy().model_copy(update={'total_budget_seconds':.1})
    task=asyncio.create_task(execute(service,subject,snapshot,uuid4()))
    if phase=='cancel':await provider_started(asr,task);task.cancel()
    with pytest.raises(asyncio.CancelledError if phase=='cancel' else TimeoutError if phase=='timeout' else RuntimeError):await task
    assert REGISTRY.get_sample_value('ttest_ai_voice_execution_total',labels)==before+1
    assert 'PRIVATE_TRANSCRIPT_AND_ID' not in generate_latest().decode()
    assert (await usage(pg,subject))[0]==0


async def test_shared_local_asr_capacity_is_distinct_zero_debit_and_replayable(store,pg,tmp_path,monkeypatch):
    import io
    import sys
    import wave
    from pathlib import Path

    from app.services.ai_local_asr import LocalPCMTranscriber
    started,finish=asyncio.Event(),asyncio.Event()
    children=[]
    class Child:
        returncode=None
        def __init__(self):self.stdin=self;self.stdout=self
        def write(self,_):pass
        async def drain(self):pass
        def close(self):pass
        async def read(self,_):await finish.wait();return b'"synthetic private transcript"'
        async def wait(self):self.returncode=0;return 0
        def kill(self):self.returncode=-9;finish.set()
    async def spawn(*args,**kwargs):
        child=Child();children.append(child);started.set();return child
    monkeypatch.setattr(asyncio,'create_subprocess_exec',spawn)
    (tmp_path/'model.bin').write_bytes(b'synthetic-placeholder-not-loaded')
    local=LocalPCMTranscriber(python=Path(sys.executable),model=tmp_path,seconds=2)
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as wav:
        wav.setparams((1,2,16000,0,'NONE','not compressed'));wav.writeframes(b'\0'*6400)
    audio=buffer.getvalue()
    a,sa,_,pa,ga,qa,_=await configured(store)
    b,sb,_,pb,gb,qb,_=await configured(store)
    large=policy().model_copy(update={'max_audio_bytes':10000})
    first=VoiceSearchExecution(store,local,pa,ga,qa,large)
    second=VoiceSearchExecution(store,local,pb,gb,qb,large)
    task=asyncio.create_task(execute(first,a,sa,uuid4(),audio=audio))
    await started.wait()
    key=uuid4()
    try:
        rejected=await execute(second,b,sb,key,audio=audio)
        assert rejected.operation.failure_code=='VOICE_CAPACITY_LIMIT'
        replay=await execute(second,b,sb,key,audio=audio)
        assert replay.replay and replay.operation.failure_code=='VOICE_CAPACITY_LIMIT'
        assert await usage(pg,b)==(0,0) and pb.calls==qb.calls==0 and len(children)==1
    finally:finish.set();await task
    assert await usage(pg,a)==(1,0)


async def execute(service, subject, snapshot, key, payload=None, **changes):
    args = {"subject": subject, "key": key, "session_id": snapshot.intent.session_id, "version": snapshot.intent.version,
            "audio": AUDIO, "media_type": "audio/wav", "payload": payload or ListingCardSearchRequest()}
    return await service.execute(**{**args, **changes})


async def provider_started(provider, task):
    # A worker can reach its deadline before the provider. Waiting only for
    # started would then strand the test forever and hide the original error.
    waiter = asyncio.create_task(provider.started.wait())
    try:
        done, _ = await asyncio.wait({waiter, task}, timeout=3, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            await task
        assert waiter in done and provider.started.is_set(), "worker ended or timed out before provider barrier"
    except BaseException:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise
    finally:
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


@pytest.mark.parametrize("total", [0, 3])
async def test_success_replay_one_ledger_row_debit_and_both_providers_once(store, pg, total):
    subject, snapshot, asr, parser, gate, query, service = await configured(store)
    query.total = total
    key = uuid4()
    first = await execute(service, subject, snapshot, key)
    assert first.operation.status == "succeeded" and first.operation.receipt.count == total
    replay = await execute(service, subject, snapshot, key)
    assert replay.replay and replay.operation.receipt == first.operation.receipt
    assert asr.calls == parser.calls == gate.calls == query.calls == 1
    assert await usage(pg, subject) == (1, 0)
    async with pg[1]() as conn:
        rows = (await conn.scalars(select(AISearchRequest))).all()
        assert len(rows) == 1 and rows[0].channel == "voice"
        assert "private" not in json.dumps(rows[0].__dict__, default=str)


@pytest.mark.parametrize("phase,code", [("asr", "ASR_FAILURE"), ("parser", "LLM_FAILURE"), ("query", "BACKEND_FAILURE")])
async def test_failure_releases_and_retry_never_calls_providers(store, pg, phase, code):
    subject, snapshot, asr, parser, gate, query, service = await configured(store)
    {"asr": asr, "parser": parser, "query": query}[phase].error = RuntimeError("PRIVATE_INPUT")
    key = uuid4()
    first = await execute(service, subject, snapshot, key)
    assert first.operation.failure_code == code and first.cards is None
    calls = asr.calls, parser.calls, gate.calls, query.calls
    replay = await execute(service, subject, snapshot, key)
    assert replay.replay and replay.operation.failure_code == code
    assert calls == (asr.calls, parser.calls, gate.calls, query.calls)
    assert await usage(pg, subject) == (0, 0)
    assert (await store.get(subject, snapshot.intent.session_id)).intent.version == 0
    assert "PRIVATE" not in repr(first)


@pytest.mark.parametrize("transcript", [None, "", "  ", "x" * 1025, "é" * 513, b"bytes"])
async def test_malformed_empty_oversize_transcripts_release_before_parser(store, pg, transcript):
    subject, snapshot, asr, parser, _, _, service = await configured(store)
    asr.result = transcript
    result = await execute(service, subject, snapshot, uuid4())
    assert result.operation.failure_code == "ASR_FAILURE"
    assert parser.calls == 0 and await usage(pg, subject) == (0, 0)


async def test_running_duplicate_and_conflicting_bytes_media_version_channel(store, pg):
    subject, snapshot, asr, parser, gate, query, service = await configured(store)
    asr.finish = asyncio.Event()
    key = uuid4()
    task = asyncio.create_task(execute(service, subject, snapshot, key))
    await provider_started(asr, task)
    duplicate = await execute(service, subject, snapshot, key)
    assert duplicate.operation.status == "running" and asr.calls == 1 and parser.calls == 0
    for change in ({"audio": b"different"}, {"media_type": "audio/webm"}, {"version": 1}, {"session_id": uuid4()}):
        with pytest.raises(QuotaError, match="IDEMPOTENCY_CONFLICT"):
            await execute(service, subject, snapshot, key, **change)
    op = QuotaOperation(idempotency_key=key, channel="text", session_id=snapshot.intent.session_id,
                        expected_session_version=0, payload_sha256=hashlib.sha256(b"text").hexdigest())
    with pytest.raises(QuotaError, match="IDEMPOTENCY_CONFLICT"):
        await TextSearchExecution(store, parser, gate, query).execute(subject, op, "text", ListingCardSearchRequest())
    assert asr.calls == 1 and parser.calls == 0
    asr.finish.set()
    assert (await task).operation.status == "succeeded"
    assert await usage(pg, subject) == (1, 0)


@pytest.mark.parametrize("name,change", card_request_mutations(), ids=lambda value: value if isinstance(value, str) else "")
async def test_all_card_request_mutations_conflict_without_asr_or_intent(store, pg, name, change):
    subject, snapshot, asr, parser, _, _, service = await configured(store)
    key = uuid4()
    assert (await execute(service, subject, snapshot, key)).operation.status == "succeeded"
    with pytest.raises(QuotaError, match="IDEMPOTENCY_CONFLICT"):
        await execute(service, subject, snapshot, key, ListingCardSearchRequest.model_validate_json(json.dumps(change)))
    assert asr.calls == parser.calls == 1 and await usage(pg, subject) == (1, 0)


async def test_invalid_audio_media_and_cursor_before_reservation(store, pg):
    subject, snapshot, asr, parser, gate, _, service = await configured(store)
    for changes in ({"audio": b""}, {"audio": b"x" * 1025}, {"audio": bytearray(AUDIO)}, {"media_type": "video/mp4"},
                    {"payload": ListingCardSearchRequest(cursor="paging")}):
        with pytest.raises(ValueError):
            await execute(service, subject, snapshot, uuid4(), **changes)
    assert asr.calls == parser.calls == gate.calls == 0
    async with pg[1]() as conn:
        assert await conn.scalar(select(func.count()).select_from(AIUsageDay)) == 0


async def test_voice_catalog_preflight_failure_preserves_distinct_zero_debit_code(store, pg):
    subject, snapshot, asr, parser, _, _, service = await configured(store)
    asr.error = SourceCoverageUnavailable("PILOT_CATALOG_STALE")
    result = await execute(service, subject, snapshot, uuid4())
    assert result.operation.failure_code == "SOURCE_COVERAGE_UNAVAILABLE"
    assert parser.calls == 0 and await usage(pg, subject) == (0, 0)


@pytest.mark.parametrize("phase", ["asr", "intent"])
async def test_cancel_releases_and_sync_late_provider_result_is_rejected(store, pg, monkeypatch, phase):
    subject, snapshot, asr, parser, _, _, service = await configured(store)
    target, method = (asr, "transcribe") if phase == "asr" else (parser, "parse")
    target.finish = asyncio.Event()
    task = asyncio.create_task(execute(service, subject, snapshot, uuid4()))
    await provider_started(target, task)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await usage(pg, subject) == (0, 0)
    original = getattr(target, method)
    target.finish.set()
    async def late(*args):
        time.sleep(0.03)  # noqa: ASYNC251 - deliberately simulate synchronous late provider work
        return await original(*args)
    monkeypatch.setattr(target, method, late)
    changes = {"asr_budget_seconds" if phase == "asr" else "intent_budget_seconds": 0.01}
    service.policy = service.policy.model_copy(update=changes)
    late_result = await execute(service, subject, snapshot, uuid4())
    assert late_result.operation.failure_code == ("ASR_FAILURE" if phase == "asr" else "LLM_FAILURE")
    assert await usage(pg, subject) == (0, 0)


async def test_ack_loss_replays_committed_operation_without_second_asr_or_release(store, pg, monkeypatch):
    subject, snapshot, asr, parser, _, _, service = await configured(store)
    finalize = store.finalize_patch
    async def ack_lost(*args):
        await finalize(*args)
        raise OSError("PRIVATE_ACK_LOSS")
    monkeypatch.setattr(store, "finalize_patch", ack_lost)
    key = uuid4()
    with pytest.raises(OSError):
        await execute(service, subject, snapshot, key)
    retry = await execute(service, subject, snapshot, key)
    assert retry.replay and retry.operation.status == "succeeded"
    assert asr.calls == parser.calls == 1 and await usage(pg, subject) == (1, 0)


@pytest.mark.parametrize("code", ["RESULT_EXPIRED_REQUERY_REQUIRED", "RESULT_NOT_FOUND", "SESSION_EXPIRED", "SESSION_NOT_FOUND"])
async def test_committed_voice_replay_retains_receipt_when_cards_unavailable(store, pg, monkeypatch, code):
    subject, snapshot, asr, parser, gate, query, service = await configured(store)
    key = uuid4()
    first = await execute(service, subject, snapshot, key)
    async def unavailable(*args):
        raise SessionError(code)
    monkeypatch.setattr(query, "query_result", unavailable)
    replay = await execute(service, subject, snapshot, key)
    assert replay.replay and replay.operation.status == "succeeded"
    assert replay.operation.receipt == first.operation.receipt
    assert replay.cards is None and replay.cards_error == code
    assert asr.calls == parser.calls == gate.calls == query.calls == 1
    assert await usage(pg, subject) == (1, 0)


async def test_voice_replay_propagates_unexpected_card_errors(store, pg, monkeypatch):
    subject, snapshot, asr, parser, _, query, service = await configured(store)
    key = uuid4()
    await execute(service, subject, snapshot, key)
    async def unavailable(*args):
        raise SessionError("RESULT_CORRUPT")
    monkeypatch.setattr(query, "query_result", unavailable)
    with pytest.raises(SessionError, match="RESULT_CORRUPT"):
        await execute(service, subject, snapshot, key)
    assert asr.calls == parser.calls == 1 and await usage(pg, subject) == (1, 0)


async def test_lost_voice_ack_then_real_session_expiry_recovers_receipt(store, pg, monkeypatch):
    subject, snapshot, asr, parser, gate, query, service = await configured(store)
    finalize = store.finalize_patch
    async def ack_lost(*args):
        await finalize(*args)
        raise OSError("synthetic lost acknowledgement")
    monkeypatch.setattr(store, "finalize_patch", ack_lost)
    key = uuid4()
    with pytest.raises(OSError):
        await execute(service, subject, snapshot, key)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).where(AISearchSession.id == snapshot.intent.session_id).values(
            expires_at=text("clock_timestamp() - interval '1 second'")))
    replay = await execute(service, subject, snapshot, key)
    assert replay.replay and replay.operation.status == "succeeded"
    assert replay.operation.receipt.count == query.total
    assert replay.cards is None and replay.cards_error == "RESULT_EXPIRED_REQUERY_REQUIRED"
    with pytest.raises(SessionError, match="RESULT_EXPIRED_REQUERY_REQUIRED"):
        await store.result(subject, replay.operation.receipt.result_ref)
    assert asr.calls == parser.calls == gate.calls == query.calls == 1
    assert await usage(pg, subject) == (1, 0)


async def test_lease_expiry_fences_late_worker_and_recovery_releases(store, pg):
    subject, snapshot, asr, parser, _, query, service = await configured(store)
    query.finish = asyncio.Event()
    key = uuid4()
    task = asyncio.create_task(execute(service, subject, snapshot, key))
    await provider_started(query, task)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchRequest).where(AISearchRequest.idempotency_key == key).values(
            lease_until=text("clock_timestamp() - interval '31 seconds'"),
            recover_after=text("clock_timestamp() - interval '1 second'")))
    query.finish.set()
    with pytest.raises(QuotaError, match="STALE_WORKER"):
        await task
    # Recovery is durable and must not run either provider again.
    await service.ledger.recover(subject, key)
    result = await execute(service, subject, snapshot, key)
    assert result.operation.status == "failed" and result.operation.failure_code == "LEASE_EXPIRED"
    assert await usage(pg, subject) == (0, 0) and asr.calls == parser.calls == 1


def test_combined_budgets_leave_query_and_finalize_time(store):
    asr, parser, gate, query = ASR(), Parser(), Gate(), Query(store)
    with pytest.raises(ValueError, match="query time"):
        policy().model_validate({**policy().model_dump(), "total_budget_seconds": 2.0})
    with pytest.raises(ValueError, match="running lease"):
        VoiceSearchExecution(store, asr, parser, gate, query, policy().model_copy(update={"total_budget_seconds": 60.0}))


@pytest.mark.parametrize("failure,code", [("owner", "SESSION_NOT_FOUND"), ("version", "SESSION_VERSION_CONFLICT"),
                                        ("gate", "ABUSE_GATE_UNAVAILABLE")])
async def test_identity_version_and_technical_gate_fail_before_asr(store, pg, failure, code):
    subject, snapshot, asr, parser, gate, _, service = await configured(store)
    changes = {}
    if failure == "owner":
        subject = QuotaSubject(kind="guest", id=uuid4())
    elif failure == "version":
        changes["version"] = 1
    else:
        gate.error = AIAttemptRejected(code)
    if failure in {"owner", "version"}:
        # HTTP voice shares text admission: reject invalid ownership/version
        # before creating even a zero-debit request under a foreign session ID.
        with pytest.raises(SessionError, match=code):
            await execute(service, subject, snapshot, uuid4(), **changes)
        async with pg[1]() as conn:
            assert await conn.scalar(select(func.count()).select_from(AISearchRequest)) == 0
    else:
        result = await execute(service, subject, snapshot, uuid4(), **changes)
        assert result.operation.failure_code == code
    assert asr.calls == parser.calls == 0
    assert await usage(pg, subject) == ((None, None) if failure in {"owner", "version"} else (0, 0))


@pytest.mark.parametrize("changed", [False, True])
async def test_reviewed_provider_noop_rejection_preserved_in_combined_voice(store, pg, changed):
    subject, snapshot, asr, _, gate, query, _ = await configured(store)
    calls = []
    def handler(request):
        calls.append(request)
        patch = {"set": {"balcony": {"strength": "hard", "value": True}} if changed else {}, "remove": []}
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps(patch)}}]})
    service = VoiceSearchExecution(store, asr, offline_parser(handler), gate, query, policy())
    key = uuid4()
    first = await execute(service, subject, snapshot, key)
    replay = await execute(service, subject, snapshot, key)
    assert replay.replay and len(calls) == asr.calls == 1
    assert first.operation.status == ("succeeded" if changed else "failed")
    assert first.operation.failure_code == (None if changed else "LLM_FAILURE")
    assert await usage(pg, subject) == (int(changed), 0)


async def test_total_monotonic_budget_bounds_query_before_durable_finalize(store, pg, monkeypatch):
    subject, snapshot, _, _, _, query, service = await configured(store)
    service.policy = VoicePolicy.model_validate({**policy().model_dump(), "asr_budget_seconds": 0.1,
        "intent_budget_seconds": 0.1, "total_budget_seconds": 0.5})
    original = query.query_candidate
    async def late(*args):
        time.sleep(0.6)  # noqa: ASYNC251 - assert post-synchronous-work deadline
        return await original(*args)
    monkeypatch.setattr(query, "query_candidate", late)
    with pytest.raises(TimeoutError):
        await execute(service, subject, snapshot, uuid4())
    assert await usage(pg, subject) == (0, 1)
    assert (await store.get(subject, snapshot.intent.session_id)).intent.version == 0


async def test_exhausted_http_deadline_defers_cancellation_cleanup_to_fenced_recovery(store, pg, monkeypatch):
    from unittest.mock import AsyncMock
    subject, snapshot, asr, parser, _, _, service = await configured(store)
    asr.finish = asyncio.Event()
    key = uuid4()
    release = AsyncMock(wraps=service.ledger.release)
    monkeypatch.setattr(service.ledger, "release", release)
    token = HTTP_DEADLINE.set(asyncio.get_running_loop().time() + 0.2)
    try:
        task = asyncio.create_task(execute(service, subject, snapshot, key))
        await provider_started(asr, task)
        with pytest.raises(TimeoutError):
            await task
    finally:
        HTTP_DEADLINE.reset(token)
    release.assert_not_awaited()
    assert asr.calls == 1 and parser.calls == 0 and await usage(pg, subject) == (0, 1)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchRequest).where(AISearchRequest.idempotency_key == key).values(
            lease_until=text("clock_timestamp() - interval '31 seconds'"),
            recover_after=text("clock_timestamp() - interval '1 second'")))
    await service.ledger.recover(subject, key)
    assert await usage(pg, subject) == (0, 0)


@pytest.mark.parametrize("phase", ["asr", "intent", "cancel", "http"])
async def test_contended_cleanup_is_bounded_and_fenced_recovery_replays(store, pg, phase):
    subject, snapshot, asr, parser, _, _, service = await configured(store)
    service.policy = VoicePolicy.model_validate({**policy().model_dump(), "asr_budget_seconds": 0.1,
        "intent_budget_seconds": 0.1, "total_budget_seconds": 0.4})
    target = parser if phase == "intent" else asr
    target.finish = asyncio.Event()
    key = uuid4()
    token = HTTP_DEADLINE.set(asyncio.get_running_loop().time() + 0.3) if phase == "http" else None
    try:
        task = asyncio.create_task(execute(service, subject, snapshot, key))
        await provider_started(target, task)
        async with pg[1].begin() as blocker:
            await blocker.execute(select(AIUsageDay).where(AIUsageDay.subject_id == subject.id).with_for_update())
            if phase in {"cancel", "http"}:
                task.cancel()
            # The SQL lock stays held until after bounded task completion.
            cleanup_started = asyncio.get_running_loop().time()
            with pytest.raises(asyncio.CancelledError if phase in {"cancel", "http"} else TimeoutError):
                await asyncio.wait_for(task, 0.8)
            assert asyncio.get_running_loop().time() - cleanup_started < 0.65
            assert task.done()
            assert await usage(pg, subject) == (0, 1)
    finally:
        if token is not None:
            HTTP_DEADLINE.reset(token)
    assert (await store.get(subject, snapshot.intent.session_id)).intent.version == 0
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchRequest).where(AISearchRequest.idempotency_key == key).values(
            lease_until=text("clock_timestamp()-interval '31 seconds'"),
            recover_after=text("clock_timestamp()-interval '1 second'")))
    from app.schemas.ai_listing_facts import digest
    from app.schemas.ai_search_quota import ResultReceipt
    op = QuotaOperation(idempotency_key=key, channel="voice", session_id=snapshot.intent.session_id,
        expected_session_version=0, payload_sha256=hashlib.sha256(AUDIO).hexdigest(),
        filters_sha256=digest({"media_type": "audio/wav", "search": ListingCardSearchRequest().model_dump(mode="json")}))
    async def forbidden_commit(*args):
        pytest.fail("stale worker cannot mutate session or result")
    with pytest.raises(QuotaError, match="STALE_WORKER"):
        await service.ledger.finalize(subject, op, 1, ResultReceipt(result_ref=uuid4(), count=0),
                                      commit_session=forbidden_commit)
    await service.ledger.recover(subject, key)
    before = asr.calls, parser.calls
    replay = await execute(service, subject, snapshot, key)
    assert replay.replay and replay.operation.failure_code == "LEASE_EXPIRED"
    assert (asr.calls, parser.calls) == before
    assert await usage(pg, subject) == (0, 0)
    late = await service.ledger.finalize(subject, op, 1, ResultReceipt(result_ref=uuid4(), count=0),
                                         commit_session=forbidden_commit)
    assert late.status == "failed" and await usage(pg, subject) == (0, 0)



@pytest.mark.parametrize("committed", [False, True])
async def test_finalize_deadline_never_speculatively_releases_ambiguous_debit(store, pg, monkeypatch, committed):
    from unittest.mock import AsyncMock
    subject, snapshot, asr, parser, _, _, service = await configured(store)
    service.policy = VoicePolicy.model_validate({**policy().model_dump(), "asr_budget_seconds": 0.1,
        "intent_budget_seconds": 0.1, "total_budget_seconds": 0.4})
    original = store.finalize_patch
    async def wait_for_ack(*args):
        if committed:
            await original(*args)
        await asyncio.Event().wait()
    monkeypatch.setattr(store, "finalize_patch", wait_for_ack)
    release = AsyncMock(wraps=service.ledger.release)
    monkeypatch.setattr(service.ledger, "release", release)
    key = uuid4()
    with pytest.raises(TimeoutError):
        await execute(service, subject, snapshot, key)
    release.assert_not_awaited()
    assert await usage(pg, subject) == ((1, 0) if committed else (0, 1))
    if not committed:
        async with pg[1].begin() as conn:
            await conn.execute(update(AISearchRequest).values(lease_until=text("clock_timestamp()-interval '31 seconds'"),
                recover_after=text("clock_timestamp()-interval '1 second'")))
        await service.ledger.recover(subject, key)
    replay = await execute(service, subject, snapshot, key)
    assert replay.replay and replay.operation.status == ("succeeded" if committed else "failed")
    assert asr.calls == parser.calls == 1
    assert await usage(pg, subject) == ((1, 0) if committed else (0, 0))
