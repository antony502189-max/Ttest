"""Explicit single-host calendar spending ledger; never enables provider IO.

Adopts a reviewed existing journal in place, retaining every attempt/dispatch.
All historical reservations are conservatively charged to the adoption day and
month because legacy attempts have no trusted timestamps. Account/privacy/source
approval and the provider's own invoice limit remain separate release gates.
"""
import hashlib
import json
import re
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .ai_closed_deepseek import INPUT_TOKEN_ALLOWANCE, OUTPUT_TOKENS, RESERVE_MICRO_USD
from .ai_deepseek_intent import ProviderFailure, _strict_json


@dataclass(frozen=True)
class CalendarBudgetPolicy:
    daily_micro_usd: int
    monthly_micro_usd: int

    def __post_init__(self):
        if (type(self.daily_micro_usd) is not int or type(self.monthly_micro_usd) is not int
                or not RESERVE_MICRO_USD <= self.daily_micro_usd <= self.monthly_micro_usd <= 1_000_000_000):
            raise ValueError("CALENDAR_BUDGET_POLICY_INVALID")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _binding(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("CALENDAR_BUDGET_BINDING_REQUIRED")
    return value


def _period(now):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("CALENDAR_BUDGET_UTC_CLOCK_REQUIRED")
    utc = now.astimezone(UTC)
    local = utc.astimezone(ZoneInfo("Europe/Madrid"))
    return utc.isoformat(timespec="microseconds"), local.date().isoformat(), local.strftime("%Y-%m")


class CalendarProviderBudget:
    """Shared SQLite file for processes on one host, not a multi-host ledger.

    Constructing/reading never creates or repairs state. Adoption is a separate
    explicit offline operation against an exact reviewed legacy snapshot.
    """
    def __init__(self, path: Path, policy: CalendarBudgetPolicy, *, account_binding: str, clock=None, dispatch_guard=None):
        self.path = Path(path).absolute()
        self.policy = CalendarBudgetPolicy(**asdict(policy))
        self.account_binding = _binding(account_binding)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.dispatch_guard = dispatch_guard
        self.policy_hash = _digest({"contract": "calendar-provider-budget.v1", **asdict(self.policy),
            "timezone": "Europe/Madrid", "reserve_micro_usd": RESERVE_MICRO_USD,
            "input_tokens": INPUT_TOKEN_ALLOWANCE, "output_tokens": OUTPUT_TOKENS,
            "account_binding": self.account_binding})
        with self._connect() as db:
            self._state(db)

    @contextmanager
    def _connect(self):
        if self.path.is_symlink() or not self.path.is_file():
            raise ProviderFailure("CALENDAR_BUDGET_JOURNAL_REQUIRED")
        try:
            with closing(sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5)) as db, db:
                db.execute("PRAGMA foreign_keys=ON")
                yield db
        except sqlite3.Error:
            raise ProviderFailure("CALENDAR_BUDGET_STORAGE_UNAVAILABLE") from None

    @staticmethod
    def _legacy(db):
        binding = db.execute("SELECT corpus FROM binding WHERE id=1").fetchone()
        attempts = db.execute("SELECT id,reserved,prompt_tokens,completion_tokens FROM attempts ORDER BY id LIMIT 51").fetchall()
        dispatches = db.execute("SELECT identity,ticket FROM dispatches ORDER BY ticket LIMIT 51").fetchall()
        if (binding is None or not 1 <= len(attempts) <= 50 or len(attempts) != len(dispatches)
                or {r[0] for r in attempts} != {r[1] for r in dispatches}
                or any(type(r[1]) is not int or r[1] < 1 or r[2] is None or r[3] is None for r in attempts)):
            raise ProviderFailure("CALENDAR_LEGACY_RECONCILIATION_REQUIRED")
        return {"binding": binding[0], "attempts": attempts, "dispatches": dispatches}

    @classmethod
    def inspect_legacy(cls, path: Path):
        path = Path(path).absolute()
        if path.is_symlink() or not path.is_file():
            raise ProviderFailure("CALENDAR_BUDGET_JOURNAL_REQUIRED")
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
            db.execute("BEGIN")
            value = cls._legacy(db)
        return {"snapshot_sha256": _digest(value), "legacy_binding": value["binding"],
                "attempts": len(value["attempts"]), "reserved_micro_usd": sum(r[1] for r in value["attempts"])}

    @classmethod
    def adopt_existing(cls, path: Path, policy: CalendarBudgetPolicy, *, account_binding: str,
                       expected_snapshot_sha256: str, expected_legacy_binding: str, now: datetime):
        # No missing-file creation and no empty replacement for an existing
        # journal. The operator must freeze old dispatchers before adoption.
        policy = CalendarBudgetPolicy(**asdict(policy))
        account_binding = _binding(account_binding)
        expected_snapshot_sha256 = _binding(expected_snapshot_sha256)
        expected_legacy_binding = _binding(expected_legacy_binding)
        stamp, day, month = _period(now)
        path = Path(path).absolute()
        if path.is_symlink() or not path.is_file():
            raise ProviderFailure("CALENDAR_BUDGET_JOURNAL_REQUIRED")
        policy_hash = _digest({"contract": "calendar-provider-budget.v1", **asdict(policy),
            "timezone": "Europe/Madrid", "reserve_micro_usd": RESERVE_MICRO_USD,
            "input_tokens": INPUT_TOKEN_ALLOWANCE, "output_tokens": OUTPUT_TOKENS,
            "account_binding": account_binding})
        with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=5)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            value = cls._legacy(db)
            if value["binding"] != expected_legacy_binding or _digest(value) != expected_snapshot_sha256:
                raise ProviderFailure("CALENDAR_LEGACY_SNAPSHOT_CHANGED")
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='calendar_budget'").fetchone():
                raise ProviderFailure("CALENDAR_BUDGET_ALREADY_ADOPTED")
            db.execute("CREATE TABLE calendar_budget(id INTEGER PRIMARY KEY CHECK(id=1),"
                "policy_hash TEXT NOT NULL, legacy_binding TEXT NOT NULL, legacy_snapshot TEXT NOT NULL,"
                "last_utc TEXT NOT NULL, halted INTEGER NOT NULL CHECK(halted IN (0,1)))")
            db.execute("CREATE TABLE calendar_reservations(ticket INTEGER PRIMARY KEY REFERENCES attempts(id),"
                "day TEXT NOT NULL, month TEXT NOT NULL, legacy INTEGER NOT NULL CHECK(legacy IN (0,1)))")
            db.execute("CREATE INDEX calendar_reservations_day ON calendar_reservations(day)")
            db.execute("CREATE INDEX calendar_reservations_month ON calendar_reservations(month)")
            db.execute("INSERT INTO calendar_budget VALUES(1,?,?,?,?,0)",
                (policy_hash, expected_legacy_binding, expected_snapshot_sha256, stamp))
            db.executemany("INSERT INTO calendar_reservations VALUES(?,?,?,1)",
                [(r[0], day, month) for r in value["attempts"]])
        return cls(path, policy, account_binding=account_binding)

    def _state(self, db):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='calendar_budget'").fetchone():
            raise ProviderFailure("CALENDAR_BUDGET_ADOPTION_REQUIRED")
        state = db.execute("SELECT policy_hash,legacy_binding,last_utc,halted,legacy_snapshot FROM calendar_budget WHERE id=1").fetchone()
        original = db.execute("SELECT corpus FROM binding WHERE id=1").fetchone()
        missing = db.execute("SELECT count(*) FROM attempts a LEFT JOIN calendar_reservations c ON c.ticket=a.id "
            "LEFT JOIN dispatches d ON d.ticket=a.id WHERE c.ticket IS NULL OR d.ticket IS NULL").fetchone()[0]
        orphan = db.execute("SELECT count(*) FROM calendar_reservations c LEFT JOIN attempts a ON a.id=c.ticket "
            "WHERE a.id IS NULL").fetchone()[0]
        orphan += db.execute("SELECT count(*) FROM dispatches d LEFT JOIN attempts a ON a.id=d.ticket "
            "WHERE a.id IS NULL").fetchone()[0]
        if (state is None or state[0] != self.policy_hash or original != (state[1],) or missing or orphan):
            raise ProviderFailure("CALENDAR_BUDGET_JOURNAL_MISMATCH")
        historical = {"binding": state[1], "attempts": db.execute(
            "SELECT a.id,a.reserved,a.prompt_tokens,a.completion_tokens FROM attempts a "
            "JOIN calendar_reservations c ON c.ticket=a.id WHERE c.legacy=1 ORDER BY a.id").fetchall(),
            "dispatches": db.execute("SELECT d.identity,d.ticket FROM dispatches d "
            "JOIN calendar_reservations c ON c.ticket=d.ticket WHERE c.legacy=1 ORDER BY d.ticket").fetchall()}
        if _digest(historical) != state[4]:
            raise ProviderFailure("CALENDAR_BUDGET_LEGACY_CHANGED")
        return state

    @staticmethod
    def _spent(db, column, value):
        queries = {
            "day": "SELECT coalesce(sum(a.reserved),0) FROM attempts a JOIN calendar_reservations c "
                "ON c.ticket=a.id WHERE c.day=?",
            "month": "SELECT coalesce(sum(a.reserved),0) FROM attempts a JOIN calendar_reservations c "
                "ON c.ticket=a.id WHERE c.month=?",
        }
        if column not in queries:
            raise ValueError("CALENDAR_PERIOD_INVALID")
        return db.execute(queries[column], (value,)).fetchone()[0]

    def reserve(self, identity: str):
        identity = _binding(identity)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._state(db)
            stamp, day, month = _period(self.clock())
            if stamp < state[2]:
                raise ProviderFailure("CALENDAR_BUDGET_CLOCK_ROLLBACK")
            if state[3] or db.execute("SELECT 1 FROM attempts WHERE prompt_tokens IS NULL LIMIT 1").fetchone():
                raise ProviderFailure("CALENDAR_BUDGET_USAGE_REVIEW_REQUIRED")
            if db.execute("SELECT 1 FROM dispatches WHERE identity=?", (identity,)).fetchone():
                raise ProviderFailure("CALENDAR_BUDGET_ATTEMPT_ALREADY_RESERVED")
            if (self._spent(db, "day", day) + RESERVE_MICRO_USD > self.policy.daily_micro_usd
                    or self._spent(db, "month", month) + RESERVE_MICRO_USD > self.policy.monthly_micro_usd):
                raise ProviderFailure("PROVIDER_COST_BUDGET_EXHAUSTED")
            # Money approval is not account/privacy/source approval. A caller
            # must supply the separately reviewed synchronous dispatch fence;
            # constructing or adopting this ledger cannot enable dispatch.
            if self.dispatch_guard is None:
                raise ProviderFailure("CALENDAR_PROVIDER_APPROVAL_REQUIRED")
            self.dispatch_guard()
            ticket = db.execute("INSERT INTO attempts(reserved) VALUES(?)", (RESERVE_MICRO_USD,)).lastrowid
            db.execute("INSERT INTO dispatches VALUES(?,?)", (identity, ticket))
            db.execute("INSERT INTO calendar_reservations VALUES(?,?,?,0)", (ticket, day, month))
            db.execute("UPDATE calendar_budget SET last_utc=? WHERE id=1", (stamp,))
            return ticket

    def record_usage(self, ticket: int, data: bytes):
        error = None
        try:
            usage = _strict_json(data)["usage"]
            prompt, completion = usage["prompt_tokens"], usage["completion_tokens"]
            if (type(prompt) is not int or type(completion) is not int or not 1 <= prompt <= INPUT_TOKEN_ALLOWANCE
                    or not 0 <= completion <= OUTPUT_TOKENS or type(usage.get("total_tokens")) is not int
                    or usage["total_tokens"] != prompt + completion):
                raise ValueError("usage")
        except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
            error = "PROVIDER_USAGE_INVALID"
            prompt = completion = None
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._state(db)
            row = db.execute("SELECT prompt_tokens,completion_tokens FROM attempts WHERE id=?", (ticket,)).fetchone()
            if row is None or (row != (None, None) and row != (prompt, completion)):
                error = "PROVIDER_USAGE_RECONCILIATION_REQUIRED"
            if error:
                db.execute("UPDATE calendar_budget SET halted=1 WHERE id=1")
            else:
                db.execute("UPDATE attempts SET prompt_tokens=?,completion_tokens=? WHERE id=?", (prompt, completion, ticket))
        if error:
            raise ProviderFailure(error)

    def status(self):
        with self._connect() as db:
            db.execute("BEGIN")
            state = self._state(db)
            stamp, day, month = _period(self.clock())
            if stamp < state[2]:
                raise ProviderFailure("CALENDAR_BUDGET_CLOCK_ROLLBACK")
            return {"day": day, "month": month, "day_reserved_micro_usd": self._spent(db, "day", day),
                "month_reserved_micro_usd": self._spent(db, "month", month),
                "daily_limit_micro_usd": self.policy.daily_micro_usd, "monthly_limit_micro_usd": self.policy.monthly_micro_usd,
                "attempts": db.execute("SELECT count(*) FROM attempts").fetchone()[0],
                "usage_review_required": bool(state[3] or db.execute(
                    "SELECT 1 FROM attempts WHERE prompt_tokens IS NULL LIMIT 1").fetchone())}
