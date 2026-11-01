"""Independent encrypted deletion intents. Never put this file in a DB dump.

An accepted intent survives transaction rollback/ack loss and is retried until
erasure completes. Restores require an authenticated fresh checkpoint from this
independent journal before exposing the restored database to traffic.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import closing
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REPLAYING: ContextVar[bool] = ContextVar("ai_erasure_replay", default=False)
ZERO = "0" * 64
MAX_ENTRIES = 10000


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class ErasureJournal:
    def __init__(self, path: Path, key: bytes, *, initialize: bool = False):
        self.path = Path(path)
        if not self.path.is_absolute() or self.path.is_symlink() or type(key) is not bytes or len(key) != 32:
            raise ValueError("AI_ERASURE_CONFIGURATION_INVALID")
        self.cipher = AESGCM(hashlib.sha256(key + b"ai-erasure.encryption.v1").digest())
        self.auth = hashlib.sha256(key + b"ai-erasure.authentication.v1").digest()
        if not self.path.exists():
            if not initialize:
                raise ValueError("AI_ERASURE_JOURNAL_MISSING")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=1)) as conn, conn:
                conn.execute("PRAGMA synchronous=FULL")
                conn.execute("CREATE TABLE entries(seq INTEGER PRIMARY KEY, nonce BLOB NOT NULL, cipher BLOB NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL)")
                conn.execute("CREATE TABLE head(id INTEGER PRIMARY KEY CHECK(id=1), journal TEXT NOT NULL, seq INTEGER NOT NULL, digest TEXT NOT NULL, mac TEXT NOT NULL)")
                journal = str(uuid4())
                conn.execute("INSERT INTO head VALUES (1,?,0,?,?)", (journal, ZERO, self._mac([journal, 0, ZERO])))
            os.chmod(self.path, 0o600)
        self.events()  # Missing/corrupt journal is never treated as empty.

    def _mac(self, value) -> str:
        return hmac.new(self.auth, canonical(value), hashlib.sha256).hexdigest()

    def _read(self, conn):
        header = conn.execute("SELECT journal,seq,digest,mac FROM head WHERE id=1").fetchone()
        if header is None or not hmac.compare_digest(header[3], self._mac(list(header[:3]))):
            raise ValueError("AI_ERASURE_JOURNAL_INVALID")
        rows = conn.execute("SELECT seq,nonce,cipher,previous,digest FROM entries ORDER BY seq LIMIT ?", (MAX_ENTRIES + 1,)).fetchall()
        if len(rows) > MAX_ENTRIES:
            raise ValueError("AI_ERASURE_JOURNAL_LIMIT")
        previous, events = ZERO, []
        for expected, (seq, nonce, encrypted, prior, digest) in enumerate(rows, 1):
            aad = canonical(["ai-erasure.v1", header[0], seq, prior])
            if seq != expected or prior != previous or hashlib.sha256(aad + nonce + encrypted).hexdigest() != digest:
                raise ValueError("AI_ERASURE_JOURNAL_INVALID")
            value = json.loads(self.cipher.decrypt(nonce, encrypted, aad))
            if set(value) != {"subject", "at", "v"} or value["v"] != 1:
                raise ValueError("AI_ERASURE_JOURNAL_INVALID")
            UUID(value["subject"])
            instant = datetime.fromisoformat(value["at"])
            if instant.tzinfo is None:
                raise ValueError("AI_ERASURE_JOURNAL_INVALID")
            events.append(value)
            previous = digest
        if header[1] != len(rows) or header[2] != previous:
            raise ValueError("AI_ERASURE_JOURNAL_INVALID")
        return events, header[1], previous, header[0]

    def events(self):
        with closing(sqlite3.connect(self.path, timeout=1)) as conn, conn:
            return self._read(conn)[0]

    def append(self, subject: UUID, *, now: datetime | None = None) -> None:
        instant = now or datetime.now(UTC)
        if instant.tzinfo is None:
            raise ValueError("AI_ERASURE_TIME_INVALID")
        with closing(sqlite3.connect(self.path, timeout=1)) as conn, conn:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            events, seq, previous, journal = self._read(conn)
            if any(e["subject"] == str(subject) for e in events):
                return
            if seq >= MAX_ENTRIES:
                raise ValueError("AI_ERASURE_JOURNAL_LIMIT")
            nonce = os.urandom(12)
            aad = canonical(["ai-erasure.v1", journal, seq + 1, previous])
            encrypted = self.cipher.encrypt(nonce, canonical({"v": 1, "subject": str(subject), "at": instant.isoformat()}), aad)
            digest = hashlib.sha256(aad + nonce + encrypted).hexdigest()
            conn.execute("INSERT INTO entries VALUES (?,?,?,?,?)", (seq + 1, nonce, encrypted, previous, digest))
            conn.execute("UPDATE head SET seq=?,digest=?,mac=? WHERE id=1", (seq + 1, digest, self._mac([journal, seq + 1, digest])))

    def revoked(self, subject: UUID) -> bool:
        return any(e["subject"] == str(subject) for e in self.events())

    def checkpoint(self, *, now: datetime | None = None) -> dict:
        instant = now or datetime.now(UTC)
        with closing(sqlite3.connect(self.path, timeout=1)) as conn, conn:
            _, seq, head, journal = self._read(conn)
        value = {"v": 1, "journal": journal, "seq": seq, "head": head, "issued": instant.timestamp(),
                 "expires": (instant + timedelta(minutes=5)).timestamp()}
        return value | {"mac": self._mac(value)}

    def verify_checkpoint(self, checkpoint: dict, *, now: datetime | None = None) -> None:
        if set(checkpoint) != {"v", "journal", "seq", "head", "issued", "expires", "mac"}:
            raise ValueError("AI_ERASURE_CHECKPOINT_INVALID")
        body = {key: value for key, value in checkpoint.items() if key != "mac"}
        if not hmac.compare_digest(str(checkpoint["mac"]), self._mac(body)):
            raise ValueError("AI_ERASURE_CHECKPOINT_INVALID")
        instant = (now or datetime.now(UTC)).timestamp()
        current = self.checkpoint(now=now)
        if (checkpoint["v"] != 1 or checkpoint["issued"] > instant + 30 or checkpoint["expires"] <= instant
                or checkpoint["expires"] - checkpoint["issued"] != 300
                or (checkpoint["journal"], checkpoint["seq"], checkpoint["head"]) != (current["journal"], current["seq"], current["head"])):
            raise ValueError("AI_ERASURE_CHECKPOINT_STALE")

    def compact(self, *, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now(UTC)) - timedelta(days=31)
        with closing(sqlite3.connect(self.path, timeout=1)) as conn, conn:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA secure_delete=ON")
            conn.execute("BEGIN IMMEDIATE")
            events, _, _, journal = self._read(conn)
            retained = [event for event in events if datetime.fromisoformat(event["at"]) > cutoff]
            if len(retained) == len(events):
                return 0
            conn.execute("DELETE FROM entries")
            previous = ZERO
            for seq, event in enumerate(retained, 1):
                nonce = os.urandom(12)
                aad = canonical(["ai-erasure.v1", journal, seq, previous])
                encrypted = self.cipher.encrypt(nonce, canonical(event), aad)
                digest = hashlib.sha256(aad + nonce + encrypted).hexdigest()
                conn.execute("INSERT INTO entries VALUES (?,?,?,?,?)", (seq, nonce, encrypted, previous, digest))
                previous = digest
            conn.execute("UPDATE head SET seq=?,digest=?,mac=? WHERE id=1",
                (len(retained), previous, self._mac([journal, len(retained), previous])))
            return len(events) - len(retained)


async def bind_journal(factory, journal: ErasureJournal, *, initialize: bool = False) -> None:
    from sqlalchemy import select, text

    from ..models.ai_operating_policy import AiErasureBinding
    identity = UUID(journal.checkpoint()["journal"])
    async with factory.begin() as conn:
        await conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('ai-erasure-binding.v1',0))"))
        binding = await conn.scalar(select(AiErasureBinding).where(AiErasureBinding.id == 1))
        if binding is None and initialize:
            conn.add(AiErasureBinding(id=1, journal_id=identity))
        elif binding is None or binding.journal_id != identity:
            raise ValueError("AI_ERASURE_JOURNAL_BINDING_INVALID")


def configured_journal(*, initialize: bool = False) -> ErasureJournal | None:
    path, encoded = os.environ.get("AI_ERASURE_JOURNAL_PATH"), os.environ.get("AI_ERASURE_JOURNAL_KEY")
    if not path and not encoded:
        return None
    if not path or not encoded:
        raise ValueError("AI_ERASURE_CONFIGURATION_INVALID")
    return ErasureJournal(Path(path), base64.b64decode(encoded, validate=True), initialize=initialize)


async def replay_erasure(factory, journal: ErasureJournal) -> int:
    from sqlalchemy import select

    from ..models import User
    from ..repositories.ai_subject_state import erase_account, lock_subject
    from ..schemas.ai_search_quota import QuotaSubject
    from .search_state import lock_saved_searches
    from .users import delete_account
    await bind_journal(factory, journal)
    events = await asyncio.to_thread(journal.events)
    token = REPLAYING.set(True)
    try:
        for event in events:
            subject = UUID(event["subject"])
            async with factory() as conn:
                user = await conn.scalar(select(User).where(User.id == subject))
                if user is not None and user.deleted_at is None:
                    await delete_account(user, conn)
                else:
                    await lock_saved_searches(subject, conn)
                    await lock_subject(conn, QuotaSubject(kind="auth", id=subject))
                    await erase_account(conn, subject)
                    await conn.commit()
        return len(events)
    finally:
        REPLAYING.reset(token)
