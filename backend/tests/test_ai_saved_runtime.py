import base64
import runpy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services import ai_saved_runtime
from app.services.ai_erasure_journal import configured_journal


def test_rollback_requires_real_total_party_readers_not_comments(tmp_path):
    root = Path(__file__).parents[2]
    checker = runpy.run_path(str(root / "deploy/check-ai-saved-runtime.py"))["supports_party_total"]
    assert checker(root)
    assert not checker(tmp_path)
    files = ["backend/app/schemas/ai_search_intent.py", "backend/app/services/ai_hard_matching.py", "src/api/ai-intent.ts"]
    for name in files:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((root / name).read_text(encoding="utf-8"), encoding="utf-8")
    assert checker(tmp_path)
    schema = tmp_path / files[0]
    original = schema.read_text(encoding="utf-8")
    schema.write_text(original.replace("PartyTotal", "LegacyParty") + "\n# class PartyTotal: persons: int\n", encoding="utf-8")
    assert not checker(tmp_path)
    schema.write_text(original, encoding="utf-8")
    (tmp_path / files[1]).write_text("# value.headcount\n", encoding="utf-8")
    assert not checker(tmp_path)


def test_primary_key_file_opens_same_journal_without_reinitializing(monkeypatch, tmp_path):
    path, key = tmp_path / "events.sqlite", tmp_path / "journal.key"
    key.write_bytes(base64.b64encode(b"k" * 32))
    monkeypatch.setenv("AI_ERASURE_JOURNAL_PATH", str(path))
    monkeypatch.setenv("AI_ERASURE_JOURNAL_KEY_FILE", str(key))
    monkeypatch.delenv("AI_ERASURE_JOURNAL_KEY", raising=False)
    journal = configured_journal(initialize=True)
    identity = journal.checkpoint()["journal"]
    assert configured_journal().checkpoint()["journal"] == identity
    monkeypatch.setenv("AI_ERASURE_JOURNAL_KEY", base64.b64encode(b"k" * 32).decode())
    with pytest.raises(ValueError, match="CONFIGURATION"):
        configured_journal()  # Two possible key authorities are ambiguous.


@pytest.mark.parametrize("failure", [False, True])
def test_disabling_new_saves_keeps_restore_and_deletion_replay(monkeypatch, failure):
    app, factory, journal = FastAPI(), object(), object()
    monkeypatch.setenv("AI_ERASURE_JOURNAL_PATH", "/synthetic/primary-journal")
    monkeypatch.setattr(ai_saved_runtime, "configured_saved_runtime", lambda factory: None)
    monkeypatch.setattr(ai_saved_runtime, "configured_journal", lambda: journal)
    replay = AsyncMock(side_effect=ValueError("JOURNAL_BINDING_INVALID") if failure else None)
    monkeypatch.setattr(ai_saved_runtime, "replay_erasure", replay)
    ai_saved_runtime.install_saved_runtime(app, factory)
    if failure:
        with pytest.raises(ValueError, match="JOURNAL_BINDING_INVALID"), TestClient(app):
            pass
    else:
        with TestClient(app):
            assert not hasattr(app.state, "ai_saved_runtime")
    replay.assert_awaited_once_with(factory, journal)


def test_rollback_refuses_old_binary_before_retained_journal_can_be_lost(tmp_path):
    root = Path(__file__).parents[2]
    checker = runpy.run_path(str(root / "deploy/check-ai-saved-runtime.py"))["supports_saved_journal"]
    assert checker(root)
    assert not checker(tmp_path)
    app = tmp_path / "backend/app"
    (app / "services").mkdir(parents=True)
    (app / "services/ai_saved_runtime.py").write_text((root / "backend/app/services/ai_saved_runtime.py").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "docker-compose.production.yml").write_text((root / "docker-compose.production.yml").read_text(encoding="utf-8"), encoding="utf-8")
    (app / "main.py").write_text("# install_saved_runtime(app, SessionLocal)\n", encoding="utf-8")
    assert not checker(tmp_path)
    (app / "main.py").write_text("install_saved_runtime(app, SessionLocal)\n", encoding="utf-8")
    assert checker(tmp_path)
