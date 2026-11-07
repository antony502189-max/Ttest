"""Import <=20 approved public records into a NEW isolated demo database only."""
import asyncio
import json
import secrets
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from demo.entry import pipeline, require_demo


async def seed():
    require_demo()
    from sqlalchemy import func, select, text

    from app.core.security import hash_password
    from app.db.session import SessionLocal, engine
    from app.models import ExternalListingSource, Listing, User
    from app.repositories.ai_fact_snapshots import FactSnapshotReader
    from app.repositories.ai_query_proofs import QueryProofs
    from app.repositories.listings import point
    from app.schemas.ai_listing_facts import digest
    from app.services.ai_erasure_journal import bind_journal, configured_journal
    from app.services.ai_pisocompartido_price import prepare_price
    snapshot = json.loads(Path("/demo-input/catalog.json").read_text())
    records = snapshot["records"]
    if not 1 <= len(records) <= 20:
        raise ValueError("BOUNDED_REAL_SNAPSHOT_REQUIRED")
    async with SessionLocal() as connection:
        if await connection.scalar(text("SELECT current_database()")) != "ai_text_demo_20261108":
            raise ValueError("DEMO_DATABASE_REQUIRED")
        if await connection.scalar(select(func.count()).select_from(Listing)):
            raise ValueError("REFUSING_TO_OVERWRITE_EXISTING_CATALOG")
    state = Path("/demo-state/signing.json")
    if state.exists():
        raise ValueError("DEMO_STATE_ALREADY_EXISTS")
    state.write_text(json.dumps({"guest": secrets.token_hex(32), "cursor": secrets.token_hex(32)}))
    journal = configured_journal(initialize=True)
    await bind_journal(SessionLocal, journal, initialize=True)
    host_id = uuid4()
    async with SessionLocal.begin() as connection:
        connection.add(User(id=host_id, email="catalog@closed-demo.invalid", name="PisoCompartido",
            role="host", initials="PC", email_verified=True, password_hash=hash_password(secrets.token_urlsafe(40))))
        await connection.flush()
        for record in records:
            card, source = record["listing"], record["source"]
            lid, sid = UUID(card.pop("id")), UUID(source.pop("id"))
            # Coordinates are the existing public approximate position, never an exact address.
            lat, lng = card.pop("latitude"), card.pop("longitude")
            if card.get("published_at"):
                card["published_at"] = datetime.fromisoformat(card["published_at"])
            listing = Listing(id=lid, owner_user_id=host_id, **card,
                location=point(lng, lat) if lat is not None and lng is not None else None,
                status="published", description="", approximate_address="")
            connection.add(listing)
            await connection.flush()
            for key in ("last_success_at", "last_checked_at", "content_updated_at", "last_state_check_at"):
                source[key] = datetime.fromisoformat(source[key]) if source[key] else None
            connection.add(ExternalListingSource(id=sid, canonical_listing_id=lid, **source,
                raw_payload={}, fingerprint=digest(source["normalized_payload"])))
    service = pipeline(SessionLocal)
    reader = FactSnapshotReader(SessionLocal, max_payload_bytes=65536)
    proofs = QueryProofs(service)
    prepared = 0
    async with SessionLocal() as connection:
        ids = list(await connection.scalars(select(ExternalListingSource.id)))
    for sid in ids:
        ready = prepare_price(await reader.capture(sid))
        await service.observe(ready.source)
        claim = await service.claim(source_name="PisoCompartido")
        if claim is None or claim.source_record_id != sid:
            raise ValueError("DEMO_CLAIM_MISMATCH")
        async with SessionLocal() as connection:
            now = await connection.scalar(select(func.clock_timestamp()))
        receipt = await service.complete(claim, ready.to_batch(claim, observed_at=now), ready.sanitized_fields)
        if receipt.status != "succeeded" or not await proofs.prepare(claim.canonical_listing_id):
            raise ValueError("DEMO_REAL_PROOF_FAILED")
        prepared += 1
    print(json.dumps({"real_snapshot_records": len(records), "prepared": prepared,
        "snapshot_at": snapshot["snapshot_at"], "model_calls": 0}))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
