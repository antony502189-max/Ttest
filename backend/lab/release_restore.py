"""Real pg_dump/restore drill confined to new disposable loopback test databases.

No application DSN fallback. Independent encrypted journal stays outside both
database backups. Keeps the disposable databases/artifacts for inspection.
"""
import asyncio
import base64
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def command(args, *, env=None, success=True):
    result = subprocess.run(args, env=env, capture_output=True, text=True, check=False)
    if (result.returncode == 0) != success:
        # Never echo SQL/DSNs/provider data from a child process.
        raise RuntimeError("AI_RESTORE_DRILL_COMMAND_FAILED")
    return result


async def drill():
    from app.models import User
    from app.models.ai_search_session import AISearchSession
    from app.repositories.ai_search_quota import QuotaLedger
    from app.repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
    from app.schemas.ai_search_quota import LeasePolicy, QuotaSubject
    from app.services.ai_erasure_journal import ErasureJournal, bind_journal, replay_erasure

    value = os.environ.get("AI_RELEASE_TEST_DATABASE_URL", "")
    from sqlalchemy.engine import make_url
    url = make_url(value)
    if url.host not in {"127.0.0.1", "localhost"} or url.port != 55479 or url.database != "ttest_test":
        raise ValueError("EXPLICIT_DISPOSABLE_AUDIT_DATABASE_REQUIRED")
    suffix = uuid4().hex[:12]
    names = ["ai_quota_test_release_" + suffix + tail for tail in ("_source", "_restore")]
    root = Path(__file__).resolve().parents[2]
    directory = root / "output" / "ai-release" / ("restore-" + suffix)
    directory.mkdir(parents=True)
    docker = "docker"
    container = "ttest-pr397-400-audit-db"
    for name in names:
        command([docker, "exec", container, "createdb", "-U", url.username, name])
    dsns = [url.set(database=name).render_as_string(hide_password=False) for name in names]
    env = dict(os.environ, APP_ENV="test", DATABASE_URL=dsns[0], JWT_SECRET="synthetic-restore-drill-only-32-characters")
    command([sys.executable, "-m", "alembic", "upgrade", "head"], env=env)
    engines = [create_async_engine(dsn, pool_size=1, max_overflow=0) for dsn in dsns]
    factories = [async_sessionmaker(engine, expire_on_commit=False) for engine in engines]
    key = os.urandom(32)
    journal = ErasureJournal(directory / "independent.sqlite", key, initialize=True)
    report = {"source": command(["git", "rev-parse", "HEAD"]).stdout.strip(), "databases": names, "cases": []}
    def passed(name):
        report["cases"].append({"name": name, "passed": True})
        print("PASS " + name, flush=True)
    try:
        await bind_journal(factories[0], journal, initialize=True)
        subject = uuid4()
        async with factories[0].begin() as conn:
            conn.add(User(id=subject, email=f"restore-{suffix}@synthetic.example", name="Synthetic restore",
                password_hash="unused", role="tenant", initials="SR", email_verified=True))
        store = SearchSessions(QuotaLedger(factories[0], LeasePolicy(reservation_seconds=10, running_seconds=30,
            recovery_grace_seconds=10)), SessionPolicy(inactivity_seconds=86400),
            IntentVocabulary(frozenset(), frozenset(), frozenset()), require_auth_owner=True)
        await store.create(QuotaSubject(kind="auth", id=subject), idempotency_key=uuid4())
        manifest = {"created_at": datetime.now(UTC).isoformat(), "schema": "0079_ai_operating_policy"}
        dump = f"/tmp/ai-release-{suffix}.dump"
        command([docker, "exec", container, "pg_dump", "-U", url.username, "-Fc", "-f", dump, names[0]])
        backup = directory / "backup.dump"
        command([docker, "cp", container + ":" + dump, str(backup)])
        manifest["sha256"] = hashlib.sha256(backup.read_bytes()).hexdigest()
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        passed("fresh full migration chain to 0079 and real pg_dump manifest")
        # Accepted deletion occurs AFTER the backup; only the independent journal
        # knows it. Simulate restoring this earlier backup in a separate DB.
        journal.append(subject)
        await replay_erasure(factories[0], journal)
        command([docker, "exec", container, "pg_restore", "-U", url.username, "--exit-on-error", "-d", names[1], dump])
        async with factories[1]() as conn:
            assert (await conn.get(User, subject)).deleted_at is None
            assert await conn.scalar(select(func.count()).select_from(AISearchSession)) == 1
        passed("real pg_restore reproduces pre-deletion account and private session in isolated DB")
        checkpoint = directory / "checkpoint.json"
        checkpoint.write_text(json.dumps(journal.checkpoint()), encoding="utf-8")
        restore_env = dict(env, AI_RESTORE_DATABASE_URL=dsns[1], AI_ERASURE_JOURNAL_PATH=str(journal.path),
                           AI_ERASURE_JOURNAL_KEY=base64.b64encode(key).decode())
        args = [sys.executable, "-m", "app.commands.ai_erasure_journal", "restore", "--checkpoint", str(checkpoint),
                "--backup-created-at", manifest["created_at"]]
        command(args, env=dict(restore_env, AI_ERASURE_JOURNAL_PATH=str(directory / "missing.sqlite")), success=False)
        passed("missing independent journal blocks restore barrier")
        replacement = ErasureJournal(directory / "replacement.sqlite", key, initialize=True)
        replacement_checkpoint = directory / "replacement.json"
        replacement_checkpoint.write_text(json.dumps(replacement.checkpoint()), encoding="utf-8")
        replacement_args = args.copy()
        replacement_args[replacement_args.index("--checkpoint") + 1] = str(replacement_checkpoint)
        command(replacement_args, env=dict(restore_env, AI_ERASURE_JOURNAL_PATH=str(replacement.path)), success=False)
        passed("valid blank replacement journal rejected by restored DB UUID binding")
        old_args = args.copy()
        old_args[-1] = (datetime.now(UTC) - timedelta(days=31)).isoformat()
        command(old_args, env=restore_env, success=False)
        passed("backup beyond 30-day horizon rejected")
        # Durable accepted deletion changes the head: previous checkpoint fails.
        journal.append(uuid4())
        command(args, env=restore_env, success=False)
        passed("checkpoint changed after issue blocks restore")
        checkpoint.write_text(json.dumps(journal.checkpoint()), encoding="utf-8")
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == manifest["sha256"]
        command(args, env=restore_env)
        command(args, env=restore_env)
        async with factories[1]() as conn:
            assert (await conn.get(User, subject)).deleted_at is not None
            assert await conn.scalar(select(func.count()).select_from(AISearchSession)) == 0
            assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == manifest["schema"]
        passed("fresh authoritative checkpoint: replay erases restored private state; second replay idempotent")
        report["status"] = "PASS"
        report["backup_sha256"] = manifest["sha256"]
    finally:
        for engine in engines:
            await engine.dispose()
        (directory / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "artifact": str(directory / "result.json")}))


if __name__ == "__main__":
    asyncio.run(drill())
