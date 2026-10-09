import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.commands.enforce_long_term_price_policy import apply_plan, inventory, verify_manifest
from app.db.session import SessionLocal
from app.models import AuditLog, Favorite, Listing, User
from app.services.rental_policy import listing_eligibility, public_eligibility_clause

pytestmark = pytest.mark.integration


async def seed(session):
    owner = User(email=f"cleanup-{uuid4()}@example.test", password_hash="unused", name="Fixture", role="host", initials="F", email_verified=True)
    session.add(owner)
    await session.flush()
    rows = []
    for amount, mode, bills in [(1000, "long", None), (1001, "long", None), (700, "holiday", None), (950, "long", "Gastos mensuales obligatorios: 50 €/mes"), (950, "long", "Gastos mensuales obligatorios: 51 €/mes"), (700, "long", "unverified fee")]:
        row = Listing(owner_user_id=owner.id, title="Fixture", city="Adeje", area="Adeje", approximate_address="Adeje", rental_mode=mode, monthly_price=amount if mode == "long" else None, nightly_price=55 if mode == "holiday" else None, status="published", bills_included=False, bills_text=bills)
        session.add(row)
        rows.append(row)
    await session.flush()
    session.add(Favorite(user_id=owner.id, listing_id=rows[1].id))
    await session.flush()
    return rows


def receipts(tmp_path, plan):
    result = []
    for kind in ("postgres", "minio"):
        backup = tmp_path / f"{kind}.enc"
        backup.write_bytes(b"local fixture encrypted-backup placeholder; not production recovery evidence")
        path = tmp_path / f"{kind}.json"
        path.write_text(json.dumps({"kind": kind, "restored": True, "verified_at": datetime.now(UTC).isoformat(), "backup": str(backup), "sha256": hashlib.sha256(backup.read_bytes()).hexdigest()}))
        path.chmod(0o600)
        result.append(path)
    return result


async def test_dry_run_and_sql_python_parity_are_read_only():
    async with SessionLocal() as session:
        rows = await seed(session)
        await session.commit()
        plan = await inventory(session, action="purge", plan_limit=2)
        verify_manifest(plan)
        assert plan["summary"]["eligible"] == 2
        assert plan["summary"]["ineligible"] == 4
        assert len(plan["selected_ids"]) == 2
        assert all(row.status == "published" for row in rows)
        protected = next(row for row in plan["candidates"] if row["id"] == str(rows[1].id))
        assert protected["action"] == "withdraw"
        assert "favorites" in protected["hard_delete_exclusions"]
        sql_ids = set((await session.scalars(select(Listing.id).where(public_eligibility_clause()))).all())
        assert sql_ids == {row.id for row in rows if listing_eligibility(row).eligible}
        assert await session.scalar(select(func.count()).select_from(AuditLog)) == 0
        assert "password_hash" not in json.dumps(plan)


async def test_reviewed_purge_preserves_eligible_and_protected_records(tmp_path):
    async with SessionLocal() as session:
        rows = await seed(session)
        ids = [row.id for row in rows]
        await session.commit()
        plan = await inventory(session, action="purge")
        await session.rollback()
        proof = receipts(tmp_path, plan)
        async with session.begin():
            result = await apply_plan(session, plan, confirmation=f"PURGE:{plan['digest']}", recovery_receipts=proof)
        assert result["results"] == {"purged": 3, "withdrawn": 1, "deferred_candidates": 0}
        assert result["media_objects_deleted"] == 0
        assert (await session.get(Listing, ids[0])).monthly_price == 1000
        assert (await session.get(Listing, ids[3])).monthly_price == 950
        assert (await session.get(Listing, ids[1])).status == "closed"
        assert await session.get(Favorite, (rows[1].owner_user_id, ids[1])) is not None
        assert await session.scalar(select(func.count()).select_from(AuditLog)) == 4
        next_plan = await inventory(session, action="purge")
        assert next_plan["selected_ids"] == []


async def test_changed_reference_aborts_before_any_mutation(tmp_path):
    async with SessionLocal() as session:
        rows = await seed(session)
        await session.commit()
        owner_id, listing_id = rows[0].owner_user_id, rows[2].id
        plan = await inventory(session, action="purge")
        await session.rollback()
        session.add(Favorite(user_id=owner_id, listing_id=listing_id))
        await session.commit()
        with pytest.raises(ValueError, match="snapshot changed"):
            async with session.begin():
                await apply_plan(session, plan, confirmation=f"PURGE:{plan['digest']}", recovery_receipts=receipts(tmp_path, plan))
        assert await session.scalar(select(func.count()).select_from(Listing)) == 6
        assert await session.scalar(select(func.count()).select_from(AuditLog)) == 0


async def test_wrong_confirmation_and_tampered_timestamp_fail_closed(tmp_path):
    async with SessionLocal() as session:
        await seed(session)
        await session.commit()
        plan = await inventory(session)
        with pytest.raises(ValueError, match="confirmation"):
            await apply_plan(session, plan, confirmation="WITHDRAW:wrong", recovery_receipts=[])
        plan["generated_at"] = "2000-01-01T00:00:00+00:00"
        with pytest.raises(ValueError, match="altered"):
            verify_manifest(plan)


async def test_apply_rollback_restores_every_listing(tmp_path):
    async with SessionLocal() as session:
        await seed(session)
        await session.commit()
        plan = await inventory(session, action="purge")
        await session.rollback()
        async with session.begin():
            await apply_plan(session, plan, confirmation=f"PURGE:{plan['digest']}", recovery_receipts=receipts(tmp_path, plan))
            await session.rollback()
        assert await session.scalar(select(func.count()).select_from(Listing)) == 6
        assert await session.scalar(select(func.count()).select_from(AuditLog)) == 0


async def test_real_postgresql_backup_restores_pre_purge_snapshot(tmp_path):
    """Opt-in local Docker drill; fixture receipts above only test apply gates."""
    import asyncio
    import os
    import subprocess

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.db.session import engine

    container = os.environ.get("RENTAL_POLICY_TEST_POSTGRES_CONTAINER")
    if not container:
        pytest.skip("Local Docker restore drill requires an explicitly named test container")
    database = f"rental_restore_{uuid4().hex}"
    async with SessionLocal() as session:
        await seed(session)
        await session.commit()
        before = await inventory(session, action="purge")
        await session.rollback()
        backup = (await asyncio.to_thread(subprocess.run, ["docker", "exec", container, "pg_dump", "-U", "ttest", "-Fc", "-d", engine.url.database], check=True, capture_output=True)).stdout
        async with session.begin():
            await apply_plan(session, before, confirmation=f"PURGE:{before['digest']}", recovery_receipts=receipts(tmp_path, before))
    await asyncio.to_thread(subprocess.run, ["docker", "exec", container, "createdb", "-U", "ttest", database], check=True, capture_output=True)
    restored_engine = create_async_engine(engine.url.set(database=database))
    try:
        await asyncio.to_thread(subprocess.run, ["docker", "exec", "-i", container, "pg_restore", "-U", "ttest", "-d", database, "--no-owner", "--exit-on-error", "--single-transaction"], input=backup, check=True, capture_output=True)
        async with async_sessionmaker(restored_engine)() as session:
            restored = await inventory(session, action="purge")
            for key in ("catalog_digest", "relation_digest", "media_digest", "summary", "candidates"):
                assert restored[key] == before[key], key
    finally:
        await restored_engine.dispose()
        await asyncio.to_thread(subprocess.run, ["docker", "exec", container, "dropdb", "-U", "ttest", "--if-exists", "--force", database], check=True, capture_output=True)
