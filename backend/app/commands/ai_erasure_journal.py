"""Explicit encrypted journal setup/checkpoint and pre-traffic restore barrier."""
import argparse
import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ..services.ai_erasure_journal import configured_journal, replay_erasure


async def run(args):
    journal = configured_journal(initialize=args.action == "initialize")
    if journal is None:
        raise ValueError("AI_ERASURE_JOURNAL_REQUIRED")
    if args.action == "initialize":
        print("AI_ERASURE_JOURNAL_READY")
        return
    if args.action == "checkpoint":
        if not args.output:
            raise ValueError("AI_ERASURE_CHECKPOINT_OUTPUT_REQUIRED")
        target = Path(args.output)
        target.write_text(json.dumps(journal.checkpoint()), encoding="utf-8")
        os.chmod(target, 0o600)
        print("AI_ERASURE_CHECKPOINT_READY")
        return
    checkpoint = json.loads(Path(args.checkpoint).read_text(encoding="utf-8"))
    journal.verify_checkpoint(checkpoint)
    instant = datetime.fromisoformat(args.backup_created_at)
    now = datetime.now(UTC)
    if instant.tzinfo is None or not now - timedelta(days=30) <= instant <= now + timedelta(seconds=30):
        raise ValueError("AI_RESTORE_BACKUP_AGE_INVALID")
    dsn = os.environ.get("AI_RESTORE_DATABASE_URL")
    if not dsn:
        raise ValueError("AI_RESTORE_DATABASE_REQUIRED")
    # No application DSN fallback and no server start. The caller keeps the
    # restored DB isolated until this command and all other restore checks pass.
    engine = create_async_engine(dsn, pool_size=1, max_overflow=0,
        connect_args={"server_settings": {"statement_timeout": "5000", "lock_timeout": "2000"}})
    try:
        count = await replay_erasure(async_sessionmaker(engine, expire_on_commit=False), journal)
        journal.verify_checkpoint(checkpoint)  # New intents during replay require another pass.
        print(json.dumps({"erasure_intents_applied": count, "restore_barrier": "passed"}))
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "checkpoint", "restore"))
    parser.add_argument("--output")
    parser.add_argument("--checkpoint")
    parser.add_argument("--backup-created-at")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except Exception:  # noqa: BLE001 - do not expose journal content, key or DSN
        raise SystemExit("AI_ERASURE_OPERATION_FAILED") from None


if __name__ == "__main__":
    main()
