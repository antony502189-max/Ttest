"""One session-bound, non-retryable three-step demo. Never resets a lost journal."""
import os
import sqlite3
from contextlib import closing, contextmanager
from contextvars import ContextVar
from pathlib import Path

from app.services.ai_closed_deepseek import RESERVE_MICRO_USD, EvaluationBudget
from app.services.ai_deepseek_intent import ProviderFailure

ATTEMPT: ContextVar[tuple[str, int, int] | None] = ContextVar("private_demo_attempt", default=None)
TICKET: ContextVar[int | None] = ContextVar("private_demo_ticket", default=None)


class DemoBudget(EvaluationBudget):
    def __init__(self, path: Path, *, corpus_sha256: str, initialize: bool = False):
        self.path = Path(path).absolute()
        if self.path.is_symlink():
            raise ProviderFailure("DEMO_JOURNAL_INVALID")
        created = False
        if initialize and not self.path.exists():
            # An incomplete initialization remains recognizable on restart;
            # normal application startup never creates a missing journal.
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            created = True
        if not self.path.is_file():
            raise ProviderFailure("DEMO_JOURNAL_REQUIRED")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not tables and initialize:
                db.execute("CREATE TABLE binding(id INTEGER PRIMARY KEY CHECK(id=1),corpus TEXT NOT NULL)")
                db.execute("INSERT INTO binding VALUES(1,?)", (corpus_sha256,))
                db.execute("CREATE TABLE attempts(id INTEGER PRIMARY KEY,reserved INTEGER NOT NULL,"
                           "prompt_tokens INTEGER,completion_tokens INTEGER)")
                db.execute("CREATE TABLE demo_sequence(id INTEGER PRIMARY KEY CHECK(id=1),"
                           "session TEXT,next_step INTEGER NOT NULL CHECK(next_step BETWEEN 0 AND 3),"
                           "halted INTEGER NOT NULL CHECK(halted IN (0,1)))")
                db.execute("INSERT INTO demo_sequence VALUES(1,NULL,0,0)")
                db.execute("CREATE TABLE demo_steps(step INTEGER PRIMARY KEY CHECK(step BETWEEN 0 AND 2),"
                           "session TEXT NOT NULL,version INTEGER NOT NULL,ticket INTEGER UNIQUE NOT NULL,"
                           "outcome TEXT NOT NULL CHECK(outcome IN ('pending','accepted','uncertain')))")
            elif created or not {"binding", "attempts"} <= tables:
                raise ProviderFailure("DEMO_JOURNAL_INVALID")
            if db.execute("SELECT corpus FROM binding WHERE id=1").fetchone() != (corpus_sha256,):
                raise ProviderFailure("EVALUATION_JOURNAL_MISMATCH")
            calls = db.execute("SELECT count(*) FROM attempts").fetchone()[0]
            if "demo_sequence" not in tables and tables and calls != 3:
                # The old completed 3/3 demo remains readable only. Never adopt
                # partially spent historical attempts into a new sequence.
                raise ProviderFailure("DEMO_SEQUENCE_RECONCILIATION_REQUIRED")

    @contextmanager
    def _connect(self):
        if self.path.is_symlink():
            raise ProviderFailure("DEMO_JOURNAL_INVALID")
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=2)) as db, db:
            yield db

    def reserve(self):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            calls, spent = db.execute("SELECT count(*),coalesce(sum(reserved),0) FROM attempts").fetchone()
            if calls >= 3 or spent + RESERVE_MICRO_USD > 100000:
                raise ProviderFailure("PROVIDER_COST_BUDGET_EXHAUSTED")
            attempt = ATTEMPT.get()
            if attempt is None:
                raise ProviderFailure("DEMO_SEQUENCE_CONTEXT_REQUIRED")
            session, version, step = attempt
            owner, expected, halted = db.execute("SELECT session,next_step,halted FROM demo_sequence WHERE id=1").fetchone()
            if halted or owner not in (None, session) or step != expected or version != step:
                raise ProviderFailure("DEMO_SEQUENCE_REJECTED")
            if db.execute("SELECT 1 FROM demo_steps WHERE step=?", (step,)).fetchone():
                raise ProviderFailure("DEMO_ATTEMPT_ALREADY_RESERVED")
            ticket = db.execute("INSERT INTO attempts(reserved) VALUES(?)", (RESERVE_MICRO_USD,)).lastrowid
            db.execute("INSERT INTO demo_steps VALUES(?,?,?,?,?)", (step, session, version, ticket, "pending"))
            db.execute("UPDATE demo_sequence SET session=? WHERE id=1", (session,))
        TICKET.set(ticket)
        return ticket

    def accept(self, ticket: int):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT session,version,step,outcome FROM demo_steps WHERE ticket=?", (ticket,)).fetchone()
            if row is None or row[:3] != ATTEMPT.get() or row[3] != "pending":
                raise ProviderFailure("DEMO_SEQUENCE_REJECTED")
            if db.execute("SELECT prompt_tokens FROM attempts WHERE id=?", (ticket,)).fetchone()[0] is None:
                raise ProviderFailure("PROVIDER_USAGE_INVALID")
            db.execute("UPDATE demo_steps SET outcome='accepted' WHERE ticket=?", (ticket,))
            db.execute("UPDATE demo_sequence SET next_step=? WHERE id=1", (row[2] + 1,))

    def uncertain(self, ticket: int):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE demo_steps SET outcome='uncertain' WHERE ticket=? AND outcome='pending'", (ticket,))
            db.execute("UPDATE demo_sequence SET halted=1 WHERE id=1")

    def status(self):
        summary = self.summary()
        with self._connect() as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='demo_sequence'").fetchone()
            row = db.execute("SELECT next_step,halted FROM demo_sequence WHERE id=1").fetchone() if exists else None
            pending = db.execute("SELECT 1 FROM demo_steps WHERE outcome='pending' LIMIT 1").fetchone() if exists else None
        return {"attempts": summary["attempts"], "maximum": 3,
            "exhausted": summary["attempts"] >= 3, "halted": bool(pending or (row and row[1])),
            "next_step": row[0] if row else None}
