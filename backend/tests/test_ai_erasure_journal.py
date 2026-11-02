"""Independent encrypted journal integrity and bounded retention."""
import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.services.ai_erasure_journal import ErasureJournal, configured_journal

KEY = b"k" * 32


def test_missing_file_requires_explicit_initialization(tmp_path):
    path = tmp_path / "events.sqlite"
    with pytest.raises(ValueError, match="MISSING"):
        ErasureJournal(path, KEY)
    assert not path.exists()
    journal = ErasureJournal(path, KEY, initialize=True)
    assert journal.events() == []
    assert ErasureJournal(path, KEY, initialize=True).checkpoint()["journal"] == journal.checkpoint()["journal"]


def test_encrypted_durable_deduplicated_intent_and_wrong_key(tmp_path):
    path, subject = tmp_path / "events.sqlite", uuid4()
    journal = ErasureJournal(path, KEY, initialize=True)
    journal.append(subject)
    journal.append(subject)
    assert len(ErasureJournal(path, KEY).events()) == 1
    assert journal.revoked(subject)
    assert not journal.revoked(uuid4())
    assert str(subject).encode() not in path.read_bytes()
    with pytest.raises(ValueError):
        ErasureJournal(path, b"x" * 32)


@pytest.mark.parametrize("mutation", ["DELETE FROM entries", "UPDATE entries SET cipher=randomblob(50)",
    "UPDATE head SET seq=0,digest='0'", "DELETE FROM head"])
def test_corruption_and_truncation_are_never_empty_success(tmp_path, mutation):
    path = tmp_path / "events.sqlite"
    journal = ErasureJournal(path, KEY, initialize=True)
    journal.append(uuid4())
    with sqlite3.connect(path) as conn:
        conn.execute(mutation)
    with pytest.raises(ValueError, match="JOURNAL_INVALID"):
        journal.events()


def test_checkpoint_rejects_new_events_expiry_forgery_and_replacement(tmp_path):
    journal = ErasureJournal(tmp_path / "events.sqlite", KEY, initialize=True)
    now = datetime.now(UTC)
    checkpoint = journal.checkpoint(now=now)
    journal.verify_checkpoint(checkpoint, now=now)
    with pytest.raises(ValueError):
        journal.verify_checkpoint(checkpoint | {"seq": 100}, now=now)
    with pytest.raises(ValueError, match="STALE"):
        journal.verify_checkpoint(checkpoint, now=now + timedelta(minutes=5))
    other = ErasureJournal(tmp_path / "replacement.sqlite", KEY, initialize=True)
    with pytest.raises(ValueError, match="STALE"):
        other.verify_checkpoint(checkpoint, now=now)
    journal.append(uuid4(), now=now)
    with pytest.raises(ValueError, match="STALE"):
        journal.verify_checkpoint(checkpoint, now=now)


def test_compaction_expires_31_days_but_retains_backup_horizon(tmp_path):
    journal = ErasureJournal(tmp_path / "events.sqlite", KEY, initialize=True)
    now, old, current = datetime.now(UTC), uuid4(), uuid4()
    journal.append(old, now=now - timedelta(days=31))
    journal.append(current, now=now - timedelta(days=30))
    checkpoint = journal.checkpoint(now=now)
    assert journal.compact(now=now) == 1
    assert not journal.revoked(old) and journal.revoked(current)
    assert journal.compact(now=now) == 0
    with pytest.raises(ValueError, match="STALE"):
        journal.verify_checkpoint(checkpoint, now=now)


def test_partial_configuration_is_rejected(monkeypatch, tmp_path):
    monkeypatch.delenv("AI_ERASURE_JOURNAL_KEY", raising=False)
    monkeypatch.setenv("AI_ERASURE_JOURNAL_PATH", str(tmp_path / "events.sqlite"))
    with pytest.raises(ValueError, match="CONFIGURATION"):
        configured_journal()
