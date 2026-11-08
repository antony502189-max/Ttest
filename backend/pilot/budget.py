"""Proposed 50 attempts / USD1 reserve ceiling; dispatch additionally needs approval.

Persistent same-input/state dispatch fence; no text stored, no automatic refunds.
Missing/changed journals fail closed. This is not a provider invoice cap.
"""
import hashlib
import os
from contextvars import ContextVar
from pathlib import Path

from app.services.ai_closed_deepseek import RESERVE_MICRO_USD, EvaluationBudget
from app.services.ai_deepseek_intent import ProviderFailure
from demo.budget import DemoBudget

BINDING = hashlib.sha256(b"site-pilot-20261108.v1|50|1000000|positive-rent-grammar.v1").hexdigest()
ATTEMPT = ContextVar("pilot_attempt", default=None)


class PilotBudget(EvaluationBudget):
    _connect = DemoBudget._connect

    def __init__(self, path: Path, *, initialize=False, **_kwargs):
        self.path = Path(path).absolute()
        if self.path.is_symlink():
            raise ProviderFailure("PILOT_JOURNAL_INVALID")
        created = False
        if initialize and not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            created = True
        if not self.path.is_file():
            raise ProviderFailure("PILOT_JOURNAL_REQUIRED")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if created:
                db.execute("CREATE TABLE binding(id INTEGER PRIMARY KEY CHECK(id=1),corpus TEXT NOT NULL)")
                db.execute("INSERT INTO binding VALUES(1,?)", (BINDING,))
                db.execute("CREATE TABLE attempts(id INTEGER PRIMARY KEY,reserved INTEGER NOT NULL,prompt_tokens INTEGER,completion_tokens INTEGER)")
                db.execute("CREATE TABLE dispatches(identity TEXT PRIMARY KEY,ticket INTEGER UNIQUE NOT NULL)")
            if db.execute("SELECT corpus FROM binding WHERE id=1").fetchone() != (BINDING,):
                raise ProviderFailure("PILOT_JOURNAL_MISMATCH")
            if db.execute("SELECT count(*) FROM attempts").fetchone()[0] != db.execute("SELECT count(*) FROM dispatches").fetchone()[0]:
                raise ProviderFailure("PILOT_JOURNAL_INVALID")

    def reserve(self):
        identity = ATTEMPT.get()
        if identity is None:
            raise ProviderFailure("PILOT_DISPATCH_CONTEXT_REQUIRED")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count, spent, missing = db.execute("SELECT count(*),coalesce(sum(reserved),0),count(*)-count(prompt_tokens) FROM attempts").fetchone()
            if count >= 50 or spent + RESERVE_MICRO_USD > 1_000_000:
                raise ProviderFailure("PROVIDER_COST_BUDGET_EXHAUSTED")
            if missing or spent >= 750_000:
                raise ProviderFailure("PILOT_UNCERTAIN_USAGE_REVIEW_REQUIRED")
            if db.execute("SELECT 1 FROM dispatches WHERE identity=?", (identity,)).fetchone():
                raise ProviderFailure("PILOT_ATTEMPT_ALREADY_RESERVED")
            ticket = db.execute("INSERT INTO attempts(reserved) VALUES(?)", (RESERVE_MICRO_USD,)).lastrowid
            db.execute("INSERT INTO dispatches VALUES(?,?)", (identity, ticket))
            return ticket

    def status(self):
        summary = self.summary()
        return {"attempts": summary["attempts"], "maximum": 50,
            "exhausted": summary["attempts"] >= 50 or summary["reserved_micro_usd"] + RESERVE_MICRO_USD > 1_000_000,
            "halted": summary["attempts"] != summary["observed_usage_attempts"] or summary["reserved_micro_usd"] >= 750_000}
