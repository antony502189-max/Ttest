"""Synthetic PostgreSQL design experiments; never imports backend application code."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb


@pytest.fixture
def lab():
    dsn = os.environ.get("AI_QUOTA_LAB_DSN")
    if not dsn:
        pytest.fail(
            "AI_QUOTA_LAB_DSN required: use a disposable local ai_quota_lab_* database"
        )
    config = conninfo_to_dict(dsn)
    if config.get("host") not in {"127.0.0.1", "localhost", "::1"} or not config.get(
        "dbname", ""
    ).startswith("ai_quota_lab_"):
        pytest.fail(
            "Lab refuses non-loopback hosts and databases outside ai_quota_lab_*"
        )
    schema = "lab_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            with psycopg.connect(dsn, options=f"-csearch_path={schema}") as setup:
                setup.execute(Path(__file__).with_name("schema.sql").read_text())
            yield dsn, schema
        finally:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


def connect(lab):
    return psycopg.connect(
        lab[0],
        options=f"-csearch_path={lab[1]} -clock_timeout=5000 -cstatement_timeout=10000",
    )


def call(lab, name, args):
    with connect(lab) as conn:
        return conn.execute(
            sql.SQL("SELECT {}({})").format(
                sql.Identifier(name), sql.SQL(",").join(sql.Placeholder() for _ in args)
            ),
            args,
        ).fetchone()[0]


def reserve(lab, subject, key=None, kind="guest", digest="a" * 64):
    return call(lab, "reserve", (kind, subject, key or uuid4(), digest))


def claim(lab, subject, key, kind="guest"):
    return call(lab, "claim", (kind, subject, key))


def finish(
    lab, subject, key, fence=1, result=None, failure=None, recover=False, kind="guest"
):
    return call(
        lab,
        "finish",
        (
            kind,
            subject,
            key,
            fence,
            None if result is None else Jsonb(result),
            failure,
            recover,
        ),
    )


def counts(lab, subject, kind="guest"):
    with connect(lab) as conn:
        return conn.execute(
            "SELECT sum(used)::int, sum(reserved)::int FROM ai_usage_days "
            "WHERE subject_id=%s AND subject_kind=%s",
            (subject, kind),
        ).fetchone()


def expire(lab, subject, key):
    with connect(lab) as conn:
        conn.execute(
            "UPDATE ai_search_requests SET lease_until=clock_timestamp()-interval '1 second' "
            "WHERE subject_id=%s AND idempotency_key=%s",
            (subject, key),
        )


@pytest.mark.parametrize("kind,limit", [("guest", 3), ("auth", 200)])
def test_exact_limits(lab, kind, limit):
    subject = uuid4()
    for _ in range(limit):
        reserve(lab, subject, kind=kind)
    with pytest.raises(psycopg.Error, match="QUOTA_EXHAUSTED"):
        reserve(lab, subject, kind=kind)
    assert counts(lab, subject, kind) == (0, limit)


@pytest.mark.parametrize("channel", ["text", "voice"])
def test_success_zero_and_disconnect_replay(lab, channel):
    subject, key = uuid4(), uuid4()
    assert reserve(lab, subject, key)["action"] == "created"
    assert reserve(lab, subject, key)["action"] == "inflight"
    worker = claim(lab, subject, key)
    result = {"count": 0, "channel": channel, "operation": str(key)}
    committed = finish(lab, subject, key, worker["fence"], result)
    # Response discarded after transaction commit; HTTP retry must replay stored result.
    assert reserve(lab, subject, key) == {"action": "replay", "operation": committed}
    assert finish(lab, subject, key, worker["fence"], result) == committed
    assert counts(lab, subject) == (1, 0)


@pytest.mark.parametrize("failure", ["ASR_FAILURE", "LLM_FAILURE", "BACKEND_FAILURE"])
def test_failure_release_once_terminal_key(lab, failure):
    subject, key = uuid4(), uuid4()
    reserve(lab, subject, key)
    claim(lab, subject, key)
    failed = finish(lab, subject, key, failure=failure)
    assert finish(lab, subject, key, failure=failure) == failed
    assert reserve(lab, subject, key)["action"] == "replay"
    with pytest.raises(psycopg.Error, match="CLAIM_REJECTED"):
        claim(lab, subject, key)
    assert counts(lab, subject) == (0, 0)


def test_hash_conflict_and_subject_isolation(lab):
    subject, key = uuid4(), uuid4()
    reserve(lab, subject, key)
    with pytest.raises(psycopg.Error, match="IDEMPOTENCY_CONFLICT"):
        reserve(lab, subject, key, digest="b" * 64)
    assert reserve(lab, uuid4(), key)["action"] == "created"
    assert reserve(lab, subject, key, kind="auth")["action"] == "created"
    assert counts(lab, subject) == (0, 1)


def test_voice_and_text_share_success_quota(lab):
    subject = uuid4()
    for channel in ("text", "voice", "text"):
        key = uuid4()
        # Channel is represented in the server hash, never in the quota bucket.
        reserve(lab, subject, key, digest=("a" if channel == "text" else "b") * 64)
        claim(lab, subject, key)
        finish(lab, subject, key, result={"count": 0, "channel": channel})
    with pytest.raises(psycopg.Error, match="QUOTA_EXHAUSTED"):
        reserve(lab, subject, digest="b" * 64)
    assert counts(lab, subject) == (3, 0)


@pytest.mark.parametrize("digest", [None, "", "not-a-hash", "a" * 63])
def test_invalid_operation_cannot_reserve(lab, digest):
    subject = uuid4()
    with pytest.raises(psycopg.Error, match="INVALID_OPERATION"):
        reserve(lab, subject, digest=digest)
    assert counts(lab, subject) == (None, None)


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_last_slot(lab, same_key):
    subject, key = uuid4(), uuid4()
    reserve(lab, subject)
    reserve(lab, subject)
    barrier = Barrier(12)

    def race(_):
        barrier.wait(timeout=10)
        try:
            return reserve(lab, subject, key if same_key else uuid4())["action"]
        except psycopg.Error as exc:
            assert "QUOTA_EXHAUSTED" in str(exc)
            return "quota"

    with ThreadPoolExecutor(max_workers=12) as workers:
        results = list(workers.map(race, range(12)))
    assert results.count("created") == 1
    assert results.count("inflight" if same_key else "quota") == 11
    assert counts(lab, subject) == (0, 3)


def test_only_one_worker_and_concurrent_finalize(lab):
    subject, key = uuid4(), uuid4()
    reserve(lab, subject, key)
    barrier = Barrier(8)

    def race(_):
        barrier.wait(timeout=10)
        try:
            return claim(lab, subject, key)["fence"]
        except psycopg.Error as exc:
            assert "CLAIM_REJECTED" in str(exc)
            return None

    with ThreadPoolExecutor(max_workers=8) as workers:
        assert list(workers.map(race, range(8))).count(1) == 1
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(
            workers.map(
                lambda _: finish(lab, subject, key, result={"count": 2}), range(8)
            )
        )
    assert all(result == results[0] for result in results)
    assert counts(lab, subject) == (1, 0)


@pytest.mark.parametrize("running", [True, False])
def test_crash_release_fences_and_never_reclaims(lab, running):
    subject, key = uuid4(), uuid4()
    reserve(lab, subject, key)
    if running:
        claim(lab, subject, key)
    fence = int(running)
    with pytest.raises(psycopg.Error, match="RECOVERY_REJECTED"):
        finish(lab, subject, key, fence, failure="LEASE_EXPIRED", recover=True)
    expire(lab, subject, key)
    with pytest.raises(psycopg.Error, match="STALE_WORKER"):
        finish(lab, subject, key, fence, result={"count": 0})
    recovered = finish(lab, subject, key, fence, failure="LEASE_EXPIRED", recover=True)
    assert recovered["fence"] == fence + 1
    assert finish(lab, subject, key, fence, result={"count": 1}) == recovered
    assert reserve(lab, subject, key)["action"] == "replay"
    assert counts(lab, subject) == (0, 0)


def test_finalize_rollback_has_no_partial_debit(lab):
    subject, key = uuid4(), uuid4()
    reserve(lab, subject, key)
    claim(lab, subject, key)
    with connect(lab) as conn:
        conn.execute(
            "SELECT finish(%s,%s,%s,%s,%s)",
            ("guest", subject, key, 1, Jsonb({"count": 1})),
        )
        conn.rollback()  # Future AI-08 CAS failure must abort the entire transaction.
    assert counts(lab, subject) == (0, 1)
    assert reserve(lab, subject, key)["operation"]["status"] == "running"
    finish(lab, subject, key, result={"count": 1})
    assert counts(lab, subject) == (1, 0)


def test_concurrent_recovery_and_late_success(lab):
    subject, key = uuid4(), uuid4()
    reserve(lab, subject, key)
    claim(lab, subject, key)
    expire(lab, subject, key)
    barrier = Barrier(12)

    def race(index):
        barrier.wait(timeout=10)
        try:
            if index % 2:
                return finish(lab, subject, key, failure="LEASE_EXPIRED", recover=True)[
                    "status"
                ]
            return finish(lab, subject, key, result={"count": 1})["status"]
        except psycopg.Error as exc:
            assert "STALE_WORKER" in str(exc)
            return "stale"

    with ThreadPoolExecutor(max_workers=12) as workers:
        results = list(workers.map(race, range(12)))
    assert "succeeded" not in results
    assert results.count("failed") >= 6
    assert counts(lab, subject) == (0, 0)
    assert reserve(lab, subject, key)["operation"]["fence"] == 2


def test_completion_uses_reservation_day(lab):
    subject, key = uuid4(), uuid4()
    reserve(lab, subject, key)
    claim(lab, subject, key)
    # Move fixture's immutable reservation bucket back a day without changing server clock.
    with connect(lab) as conn:
        old_day = conn.execute(
            "SELECT madrid_date FROM ai_search_requests WHERE subject_id=%s", (subject,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO ai_usage_days(subject_kind,subject_id,madrid_date,reserved) VALUES (%s,%s,%s,1)",
            ("guest", subject, old_day - timedelta(days=1)),
        )
        conn.execute(
            "UPDATE ai_search_requests SET madrid_date=%s WHERE subject_id=%s",
            (old_day - timedelta(days=1), subject),
        )
        conn.execute(
            "UPDATE ai_usage_days SET reserved=0 WHERE subject_id=%s AND madrid_date=%s",
            (subject, old_day),
        )
    finish(lab, subject, key, result={"count": 0})
    assert reserve(lab, subject, key)["action"] == "replay"
    reserve(lab, subject)
    with connect(lab) as conn:
        rows = conn.execute(
            "SELECT used,reserved FROM ai_usage_days WHERE subject_id=%s ORDER BY madrid_date",
            (subject,),
        ).fetchall()
    assert rows == [(1, 0), (0, 1)]


@pytest.mark.parametrize(
    "start,end,hours",
    [
        ("2026-03-28T23:00:00+00:00", "2026-03-29T22:00:00+00:00", 23),
        ("2026-10-24T22:00:00+00:00", "2026-10-25T23:00:00+00:00", 25),
        ("2026-10-25T23:00:00+00:00", "2026-10-26T23:00:00+00:00", 24),
    ],
)
def test_madrid_dst(lab, start, end, hours):
    with connect(lab) as conn:
        day, reset = conn.execute(
            "SELECT * FROM madrid_window(%s)", (datetime.fromisoformat(start),)
        ).fetchone()
    assert reset == datetime.fromisoformat(end)
    assert (reset - datetime.fromisoformat(start)).total_seconds() == hours * 3600
    assert day == datetime.fromisoformat(end).date()


def test_database_constraints_and_invalid_outcomes(lab):
    subject, key = uuid4(), uuid4()
    reserve(lab, subject, key)
    claim(lab, subject, key)
    for fence, result, failure in [
        (0, {}, None),
        (None, {}, None),
        (1, None, None),
        (1, {}, "LLM_FAILURE"),
        (1, None, "clarification"),
    ]:
        with pytest.raises(psycopg.Error):
            finish(lab, subject, key, fence, result, failure)
    with connect(lab) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE ai_usage_days SET used=3 WHERE subject_id=%s", (subject,)
            )
    assert counts(lab, subject) == (0, 1)
