"""Small synthetic catalogue through observe/claim/complete/projection/prepare."""
import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID, uuid5

from lab.ai_text import pipeline, require_lab, verify_database

NAMESPACE = UUID("295a49e5-0159-4e34-9bb1-b6023aeb902c")
CASES = [
    ("allow-500", 500, True), ("allow-700", 700, True), ("deny-450", 450, False),
    ("unknown-550", 550, None), ("stale-510", 510, True), ("hidden-520", 520, True),
    ("price-changed-530", 530, True),
]


def identifier(name):
    return uuid5(NAMESPACE, name)


async def seed():
    require_lab()
    from sqlalchemy import func, select, update

    from app.core.security import hash_password
    from app.db.session import SessionLocal, engine
    from app.models import ExternalListingSource, Listing, User
    from app.repositories.ai_query_proofs import QueryProofs
    from app.repositories.listings import point
    from app.schemas.ai_fact_pipeline import SourceInput
    from app.schemas.ai_listing_facts import FactBatch, digest

    await verify_database(SessionLocal)
    service = pipeline(SessionLocal)
    # Fail closed on any existing catalogue; never truncate or overwrite data.
    async with SessionLocal() as connection:
        if await connection.scalar(select(func.count()).select_from(Listing)):
            print(json.dumps({"status": "already-seeded", "ids": {n: str(identifier(n)) for n, _, _ in CASES}}))
            await engine.dispose()
            return
    now = datetime.now(UTC)
    async with SessionLocal.begin() as connection:
        host = User(id=identifier("host"), email="host@synthetic.example", password_hash=hash_password("Synthetic-Lab-Only-2026!"),
                    name="Synthetic Host", role="host", initials="SH", email_verified=True)
        guest_user = User(id=identifier("user"), email="user@synthetic.example",
                          password_hash=hash_password("Synthetic-Lab-Only-2026!"),
                          name="Synthetic User", role="tenant", initials="SU", email_verified=True)
        connection.add_all([host, guest_user])
        await connection.flush()
        for index, (name, price, pets) in enumerate(CASES):
            description = f"Rent {price} EUR monthly. " + (
                "Pets allowed." if pets is True else "No pets." if pets is False else "No pet information.")
            connection.add(Listing(id=identifier(name), owner_user_id=host.id,
                title=f"Synthetic {name}", description=description, city="Adeje", area="Synthetic district",
                approximate_address="Synthetic approximate position", rental_mode="long", monthly_price=price,
                location=point(-16.78 + index * .01, 28.08 + index * .005), status="published", published_at=now))
            await connection.flush()
            connection.add(ExternalListingSource(id=identifier("source-" + name), source_name="synthetic-lab",
                external_id=name, source_url=f"https://example.invalid/synthetic/{name}",
                canonical_listing_id=identifier(name), fingerprint=digest(name),
                raw_payload={"description": description}, normalized_payload={"description": description},
                current_status="active", last_success_at=now, content_updated_at=now))
    for name, price, pets in CASES:
        lid, sid = identifier(name), identifier("source-" + name)
        async with SessionLocal() as connection:
            source = await connection.get(ExternalListingSource, sid)
            description = source.raw_payload["description"]
            _, authority = await service._authority(connection, lid, lock=False)
        await service.observe(SourceInput(source_record_id=sid, canonical_listing_id=lid,
            content_hash=digest({"description": description}), snapshot_hash=authority[sid].snapshot_hash,
            schema_version="ai-facts.v1", taxonomy_version="ai-search.v1", extractor_version="synthetic-lab.v1"))
        claim = await service.claim()
        assert claim is not None and claim.source_record_id == sid
        evidence = [{"field": "description", "quote": description, "start": 0, "end": len(description)}]
        facts = [{"fact_id": identifier("price-" + name), "key": "price", "status": "explicit_allow",
                  "typed_value": {"kind": "money", "amount": str(price), "currency": "EUR", "period": "monthly"},
                  "qualifiers": {}, "origin": "source_text", "evidence": evidence}]
        if pets is not None:
            facts.append({"fact_id": identifier("pets-" + name), "key": "pets",
                "status": "explicit_allow" if pets else "explicit_deny", "typed_value": {"kind": "policy", "allowed": pets},
                "qualifiers": {}, "origin": "source_text", "evidence": evidence})
        batch = FactBatch.model_validate({"schema_version": claim.schema_version, "taxonomy_version": claim.taxonomy_version,
            "batch_id": identifier("batch-" + name), "canonical_listing_id": lid, "source_record_id": sid,
            "source_generation": claim.generation, "content_hash": claim.content_hash,
            "extractor_version": claim.extractor_version, "observed_at": now, "source_status": "active",
            "last_successful_check_at": None, "last_content_change_at": None, "last_check_error_at": None, "facts": facts})
        receipt = await service.complete(claim, batch, {"description": description})
        assert receipt.status == "succeeded"
        assert await QueryProofs(service).prepare(lid)
    # Deliberate changes AFTER real preparation exercise live fail-closed guards.
    async with SessionLocal.begin() as connection:
        await connection.execute(update(ExternalListingSource).where(
            ExternalListingSource.id == identifier("source-stale-510")).values(raw_payload={"changed": True}))
        await connection.execute(update(Listing).where(Listing.id == identifier("hidden-520")).values(status="hidden"))
        await connection.execute(update(Listing).where(Listing.id == identifier("price-changed-530")).values(monthly_price=900))
    print(json.dumps({"status": "seeded", "ids": {n: str(identifier(n)) for n, _, _ in CASES},
                      "prepared": 7, "expected_all": 4, "expected_dog": 2, "expected_dog_600": 1}))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
