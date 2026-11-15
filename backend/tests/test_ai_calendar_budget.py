import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from app.services.ai_calendar_budget import CalendarBudgetPolicy, CalendarProviderBudget
from app.services.ai_closed_deepseek import RESERVE_MICRO_USD
from app.services.ai_deepseek_intent import ProviderFailure
from pilot.budget import ATTEMPT, BINDING, PilotBudget

NOW = datetime(2026, 11, 15, 20, tzinfo=UTC)
ACCOUNT = "a" * 64
POLICY = CalendarBudgetPolicy(daily_micro_usd=5_000_000, monthly_micro_usd=50_000_000)
USAGE = json.dumps({"usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}}).encode()


def identity(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def legacy(tmp_path, calls=3):
    path = tmp_path / "original.sqlite3"
    budget = PilotBudget(path, initialize=True)
    for number in range(calls):
        token = ATTEMPT.set(identity(number))
        try:
            ticket = budget.reserve()
        finally:
            ATTEMPT.reset(token)
        budget.record_usage(ticket, USAGE)
    return path


def adopt(path, policy=POLICY, now=NOW):
    snapshot = CalendarProviderBudget.inspect_legacy(path)
    budget = CalendarProviderBudget.adopt_existing(path, policy, account_binding=ACCOUNT,
        expected_snapshot_sha256=snapshot["snapshot_sha256"], expected_legacy_binding=BINDING, now=now)
    budget.clock = lambda: now
    budget.dispatch_guard = lambda: None  # Synthetic authorization, no IO.
    return budget


def accepted(budget, key):
    ticket = budget.reserve(identity(key))
    budget.record_usage(ticket, USAGE)
    return ticket


def test_adoption_preserves_all_historical_spend_and_original_journal(tmp_path):
    path = legacy(tmp_path, 30)
    before = CalendarProviderBudget.inspect_legacy(path)
    budget = adopt(path)
    assert CalendarProviderBudget.inspect_legacy(path) == before
    status = budget.status()
    assert status["attempts"] == 30
    assert status["day_reserved_micro_usd"] == status["month_reserved_micro_usd"] == 331800
    accepted(budget, "new")
    reopened = CalendarProviderBudget(path, POLICY, account_binding=ACCOUNT, clock=lambda: NOW)
    assert reopened.status()["attempts"] == 31
    assert reopened.status()["month_reserved_micro_usd"] == 342860
    with pytest.raises(ProviderFailure, match="ALREADY_ADOPTED"):
        adopt(path)


def test_missing_journal_never_created_and_unadopted_never_implicitly_initialized(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(ProviderFailure, match="JOURNAL_REQUIRED"):
        CalendarProviderBudget(missing, POLICY, account_binding=ACCOUNT)
    assert not missing.exists()
    with pytest.raises(ProviderFailure, match="ADOPTION_REQUIRED"):
        CalendarProviderBudget(legacy(tmp_path), POLICY, account_binding=ACCOUNT)


def test_changed_snapshot_and_account_policy_binding_fail_closed(tmp_path):
    path = legacy(tmp_path)
    snapshot = CalendarProviderBudget.inspect_legacy(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE attempts SET reserved=reserved+1 WHERE id=1")
    with pytest.raises(ProviderFailure, match="SNAPSHOT_CHANGED"):
        CalendarProviderBudget.adopt_existing(path, POLICY, account_binding=ACCOUNT,
            expected_snapshot_sha256=snapshot["snapshot_sha256"], expected_legacy_binding=BINDING, now=NOW)
    adopt(path)
    for policy, binding in ((POLICY, "b" * 64), (CalendarBudgetPolicy(6_000_000, 50_000_000), ACCOUNT)):
        with pytest.raises(ProviderFailure, match="MISMATCH"):
            CalendarProviderBudget(path, policy, account_binding=binding)


def test_daily_and_monthly_reservations_reset_by_period_without_deleting_history(tmp_path):
    budget = adopt(legacy(tmp_path, 1), CalendarBudgetPolicy(2 * RESERVE_MICRO_USD, 3 * RESERVE_MICRO_USD))
    accepted(budget, "second")
    with pytest.raises(ProviderFailure, match="EXHAUSTED"):
        budget.reserve(identity("third"))
    budget.clock = lambda: NOW + timedelta(days=1)
    accepted(budget, "third")
    assert budget.status()["day_reserved_micro_usd"] == RESERVE_MICRO_USD
    assert budget.status()["month_reserved_micro_usd"] == 3 * RESERVE_MICRO_USD
    budget.clock = lambda: NOW + timedelta(days=2)
    with pytest.raises(ProviderFailure, match="EXHAUSTED"):
        budget.reserve(identity("fourth"))
    budget.clock = lambda: datetime(2026, 12, 1, tzinfo=UTC)
    accepted(budget, "fourth")
    assert budget.status()["attempts"] == 4
    assert budget.status()["month_reserved_micro_usd"] == RESERVE_MICRO_USD


@pytest.mark.parametrize("first,second,third", [
    (datetime(2026, 10, 25, 0, 30, tzinfo=UTC), datetime(2026, 10, 25, 1, 30, tzinfo=UTC), datetime(2026, 10, 25, 23, 0, tzinfo=UTC)),
    (datetime(2026, 3, 29, 0, 30, tzinfo=UTC), datetime(2026, 3, 29, 1, 30, tzinfo=UTC), datetime(2026, 3, 29, 22, 0, tzinfo=UTC)),
])
def test_madrid_dst_does_not_refill_day_during_clock_change(tmp_path, first, second, third):
    budget = adopt(legacy(tmp_path, 1), CalendarBudgetPolicy(RESERVE_MICRO_USD, 10 * RESERVE_MICRO_USD), first)
    budget.clock = lambda: second
    with pytest.raises(ProviderFailure, match="EXHAUSTED"):
        budget.reserve(identity("same Madrid date"))
    budget.clock = lambda: third
    accepted(budget, "next Madrid date")


def test_unknown_usage_blocks_even_after_day_change_and_duplicate_never_dispatches(tmp_path):
    budget = adopt(legacy(tmp_path))
    ticket = budget.reserve(identity("pending"))
    budget.clock = lambda: NOW + timedelta(days=1)
    with pytest.raises(ProviderFailure, match="USAGE_REVIEW"):
        budget.reserve(identity("later"))
    budget.record_usage(ticket, USAGE)
    budget.record_usage(ticket, USAGE)
    with pytest.raises(ProviderFailure, match="ALREADY_RESERVED"):
        budget.reserve(identity("pending"))
    assert budget.status()["attempts"] == 4


@pytest.mark.parametrize("data", [b"{}", b"not json", b'{"usage":{"prompt_tokens":true}}',
    b'{"usage":{"prompt_tokens":32769,"completion_tokens":1,"total_tokens":32770}}'])
def test_bad_usage_retains_reservation_and_durable_halt(tmp_path, data):
    budget = adopt(legacy(tmp_path))
    ticket = budget.reserve(identity("bad usage"))
    with pytest.raises(ProviderFailure, match="USAGE_INVALID"):
        budget.record_usage(ticket, data)
    reopened = CalendarProviderBudget(budget.path, POLICY, account_binding=ACCOUNT, clock=lambda: NOW)
    assert reopened.status()["usage_review_required"]
    assert reopened.status()["day_reserved_micro_usd"] == 4 * RESERVE_MICRO_USD
    with pytest.raises(ProviderFailure, match="USAGE_REVIEW"):
        reopened.reserve(identity("after bad usage"))


def test_parallel_connections_cannot_overreserve_or_refund(tmp_path):
    policy = CalendarBudgetPolicy(2 * RESERVE_MICRO_USD, 2 * RESERVE_MICRO_USD)
    path = legacy(tmp_path, 1)
    adopt(path, policy)
    def attempt(number):
        budget = CalendarProviderBudget(path, policy, account_binding=ACCOUNT, clock=lambda: NOW,
            dispatch_guard=lambda: None)
        try:
            accepted(budget, "parallel" + str(number))
            return True
        except ProviderFailure:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(20))) == 1
    budget = CalendarProviderBudget(path, policy, account_binding=ACCOUNT, clock=lambda: NOW)
    assert budget.status()["attempts"] == 2
    assert budget.status()["day_reserved_micro_usd"] == 2 * RESERVE_MICRO_USD


@pytest.mark.parametrize("mutation", [
    "DELETE FROM calendar_reservations WHERE ticket=1",
    "DELETE FROM attempts WHERE id=1",
    "UPDATE attempts SET reserved=1 WHERE id=1",
    "DELETE FROM dispatches WHERE ticket=1",
])
def test_missing_or_changed_history_cannot_refill_budget(tmp_path, mutation):
    budget = adopt(legacy(tmp_path))
    with sqlite3.connect(budget.path) as db:
        db.execute(mutation)
    with pytest.raises(ProviderFailure, match="MISMATCH|LEGACY_CHANGED"):
        budget.reserve(identity("after tamper"))


def test_clock_rollback_and_legacy_dispatcher_cannot_bypass_calendar_caps(tmp_path):
    path = legacy(tmp_path)
    budget = adopt(path)
    budget.clock = lambda: NOW - timedelta(microseconds=1)
    with pytest.raises(ProviderFailure, match="CLOCK_ROLLBACK"):
        budget.reserve(identity("rollback"))
    old = PilotBudget(path)
    token = ATTEMPT.set(identity("old runtime"))
    try:
        with pytest.raises(ProviderFailure, match="CALENDAR_BUDGET_MIGRATED"):
            old.reserve()
    finally:
        ATTEMPT.reset(token)


def test_budget_approval_does_not_enable_dispatch_and_revocation_preserves_spend(tmp_path):
    budget = adopt(legacy(tmp_path))
    budget.dispatch_guard = None
    with pytest.raises(ProviderFailure, match="APPROVAL_REQUIRED"):
        budget.reserve(identity("no account approval"))
    assert budget.status()["attempts"] == 3
    def revoked():
        raise ProviderFailure("ACCOUNT_APPROVAL_REVOKED")
    budget.dispatch_guard = revoked
    with pytest.raises(ProviderFailure, match="ACCOUNT_APPROVAL_REVOKED"):
        budget.reserve(identity("revoked account"))
    assert budget.status()["attempts"] == 3


def test_uncertain_legacy_attempt_cannot_be_adopted_or_disappear(tmp_path):
    path = legacy(tmp_path)
    old = PilotBudget(path)
    token = ATTEMPT.set(identity("uncertain legacy dispatch"))
    try:
        old.reserve()
    finally:
        ATTEMPT.reset(token)
    with pytest.raises(ProviderFailure, match="RECONCILIATION_REQUIRED"):
        CalendarProviderBudget.inspect_legacy(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 4
        assert db.execute("SELECT 1 FROM sqlite_master WHERE name='calendar_budget'").fetchone() is None
