"""Local CLI controls for synthetic acceptance only; no HTTP control endpoint."""
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4, uuid5

from sqlalchemy import delete, func, select, update

from lab.ai_text import REDIS, pipeline, require_lab, verify_database

NS = UUID("cb3f58c8-d7c1-47a4-8d91-25c4d9e028a5")
CASES = [("a", 50, True, True), ("b", 55, True, True), ("c", 60, True, False),
         ("d", 45, False, True), ("e", 50, None, None), ("f", 70, True, True), ("g", 80, True, None)]


def identifier(name):
    return uuid5(NS, name)


class ObservedParser:
    """Observe calls and inject bounded faults ONLY at the synthetic model boundary."""
    total_budget_seconds = 10

    def __init__(self, inner, redis):
        self.inner, self.redis = inner, redis

    async def parse(self, message, current):
        key = f"lab-acceptance:{current.session_id}:{current.version}"
        await self.redis.incr(key + ":calls")
        await self.redis.expire(key + ":calls", 7200)
        fault = await self.redis.getdel(key + ":fault")
        if fault == "delay":
            await asyncio.sleep(3)
        elif fault == "failure":
            raise ValueError("synthetic parser failure")
        elif fault == "cancel":
            raise asyncio.CancelledError
        return await self.inner.parse(message, current)


async def seed():
    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models import ExternalListingSource, Listing, User
    from app.repositories.listings import point
    async with SessionLocal.begin() as conn:
        if await conn.get(User, identifier("user")) is None:
            conn.add(User(id=identifier("user"), email="acceptance-user@synthetic.example",
                password_hash=hash_password("Synthetic-Lab-Only-2026!"), name="Acceptance User",
                role="tenant", initials="AU", email_verified=True))
        actual = set(await conn.scalars(select(Listing.id).where(Listing.owner_user_id == identifier("host"))))
        if actual:
            if actual != {identifier(name) for name, *_ in CASES}:
                raise RuntimeError("incomplete acceptance catalogue; refusing to overwrite")
            return {name: str(identifier(name)) for name, *_ in CASES}
        host = User(id=identifier("host"), email="acceptance-host@synthetic.example",
                    password_hash=hash_password("Synthetic-Lab-Only-2026!"), name="Acceptance Host",
                    role="host", initials="AH", email_verified=True)
        conn.add(host)
        await conn.flush()
        now = datetime.now(UTC)
        for index, (name, price, pets, balcony) in enumerate(CASES):
            description = description_for(name)
            conn.add(Listing(id=identifier(name), owner_user_id=host.id, title=f"Acceptance {name}",
                description=description, city="Adeje", area="Synthetic acceptance", approximate_address="Synthetic only",
                rental_mode="holiday", nightly_price=price, location=point(-16.78 + index * .005, 28.08 + index * .004),
                status="published", published_at=now - timedelta(minutes=index)))
            await conn.flush()
            conn.add(ExternalListingSource(id=identifier("source-" + name), source_name="synthetic-acceptance",
                external_id=name, source_url=f"https://example.invalid/acceptance/{name}",
                canonical_listing_id=identifier(name), fingerprint=str(identifier(name)).replace("-", "").ljust(64, "0"),
                raw_payload={"description": description}, normalized_payload={"description": description},
                current_status="active", last_success_at=now, content_updated_at=now))
    for name, *_ in CASES:
        await prepare(name)
    return {name: str(identifier(name)) for name, *_ in CASES}


def description_for(name):
    _, price, pets, balcony = next(item for item in CASES if item[0] == name)
    return f"Holiday rental. Rent {price} EUR nightly. " + (
        "Pets allowed. " if pets is True else "No pets. " if pets is False else "Pets unknown. ") + (
        "Balcony yes." if balcony is True else "Balcony no." if balcony is False else "Balcony unknown.")


async def prepare(name):
    from app.db.session import SessionLocal
    from app.repositories.ai_query_proofs import QueryProofs
    from app.schemas.ai_fact_pipeline import SourceInput
    from app.schemas.ai_listing_facts import FactBatch, digest
    service = pipeline(SessionLocal)
    lid, sid = identifier(name), identifier("source-" + name)
    description = description_for(name)
    _, price, pets, balcony = next(item for item in CASES if item[0] == name)
    async with SessionLocal() as conn:
        _, authority = await service._authority(conn, lid, lock=False)
    await service.observe(SourceInput(source_record_id=sid, canonical_listing_id=lid,
        content_hash=digest({"description": description}), snapshot_hash=authority[sid].snapshot_hash,
        schema_version="ai-facts.v1", taxonomy_version="ai-search.v1", extractor_version="synthetic-acceptance.v1"))
    claim = await service.claim(extractor_version="synthetic-acceptance.v1")
    if claim is not None:
        assert claim.source_record_id == sid
        values = [("rental_mode", {"kind": "category", "value": "holiday"}, True),
                  ("price", {"kind": "money", "amount": str(price), "currency": "EUR", "period": "nightly"}, True)]
        if pets is not None:
            values.append(("pets", {"kind": "policy", "allowed": pets}, pets))
        if balcony is not None:
            values.append(("balcony", {"kind": "boolean", "value": balcony}, True))
        facts = [{"fact_id": uuid4(), "key": key, "status": "explicit_allow" if allow else "explicit_deny",
                  "typed_value": value, "qualifiers": {}, "origin": "source_text",
                  "evidence": [{"field": "description", "quote": description, "start": 0, "end": len(description)}]}
                 for key, value, allow in values]
        batch = FactBatch.model_validate({"schema_version": claim.schema_version, "taxonomy_version": claim.taxonomy_version,
            "batch_id": uuid4(), "canonical_listing_id": lid, "source_record_id": sid,
            "source_generation": claim.generation, "content_hash": claim.content_hash,
            "extractor_version": claim.extractor_version, "observed_at": datetime.now(UTC), "source_status": "active",
            "last_successful_check_at": None, "last_content_change_at": None, "last_check_error_at": None, "facts": facts})
        assert (await service.complete(claim, batch, {"description": description})).status == "succeeded"
    assert await QueryProofs(service).prepare(lid)


async def command(payload):
    require_lab()
    from redis.asyncio import from_url

    from app.db.session import SessionLocal, engine
    from app.models import ExternalListingSource, Listing
    from app.models.ai_search_quota import AISearchRequest
    from app.models.ai_search_session import AISearchSession
    from app.models.moderation import ListingRestriction
    from app.repositories.ai_query_proofs import QueryProofs
    await verify_database(SessionLocal)
    redis = from_url(REDIS, decode_responses=True)
    try:
        action = payload["action"]
        if action == "seed":
            return {"ids": await seed()}
        if action == "change":
            name, kind = payload["name"], payload["kind"]
            if name not in {item[0] for item in CASES} or kind not in {"source", "price", "moderation", "hidden", "restore", "proof", "missing"}:
                raise ValueError("bounded acceptance fixture change required")
            lid, sid = identifier(name), identifier("source-" + name)
            async with SessionLocal.begin() as conn:
                listing = await conn.get(Listing, lid)
                if listing is None or listing.owner_user_id != identifier("host"):
                    raise ValueError("not an acceptance fixture")
                if kind == "source":
                    await conn.execute(update(ExternalListingSource).where(ExternalListingSource.id == sid)
                                       .values(raw_payload={"synthetic_changed": True}))
                elif kind == "price":
                    listing.nightly_price = 999
                elif kind == "hidden":
                    listing.status = "hidden"
                elif kind == "moderation":
                    conn.add(ListingRestriction(id=identifier("restriction-" + name), listing_id=lid, reason="Synthetic acceptance"))
                elif kind == "restore":
                    listing.status = "published"
                    listing.nightly_price = next(item[1] for item in CASES if item[0] == name)
                    await conn.execute(delete(ListingRestriction).where(ListingRestriction.id == identifier("restriction-" + name)))
                    await conn.execute(update(ExternalListingSource).where(ExternalListingSource.id == sid)
                                       .values(raw_payload={"description": description_for(name)}))
                elif kind == "missing":
                    from app.models.ai_query_proof import AiQueryProof
                    await conn.execute(delete(AiQueryProof).where(AiQueryProof.canonical_listing_id == lid))
            if kind == "proof":
                return {"prepared": await QueryProofs(pipeline(SessionLocal)).prepare(lid)}
            if kind == "restore":
                await prepare(name)
            return {"changed": str(lid), "kind": kind}
        sid = UUID(payload["session_id"])
        async with SessionLocal() as conn:
            owned = await conn.get(AISearchSession, sid)
            if owned is None:
                raise ValueError("session missing")
            version = payload.get("version", owned.version)
            if type(version) is not int or version < 0:
                raise ValueError("invalid version")
            key = f"lab-acceptance:{sid}:{version}"
            if action == "arm":
                if payload["fault"] not in {"delay", "failure", "cancel"}:
                    raise ValueError("unsupported parser fault")
                await redis.set(key + ":fault", payload["fault"], ex=60)
                return {"armed": True}
            if action == "expire":
                await conn.execute(update(AISearchSession).where(AISearchSession.id == sid)
                                   .values(expires_at=func.clock_timestamp() - timedelta(seconds=1)))
                await conn.commit()
                return {"expired": str(sid)}
            if action == "inspect":
                requests = list(await conn.scalars(select(AISearchRequest).where(AISearchRequest.session_id == sid)))
                return {"version": owned.version, "calls": int(await redis.get(key + ":calls") or 0),
                        "requests": [{"key": str(row.idempotency_key), "status": row.status,
                                      "failure": row.failure_code, "result_ref": str(row.result_ref) if row.result_ref else None}
                                     for row in requests]}
        raise ValueError("unknown bounded acceptance command")
    finally:
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(command(json.loads(sys.argv[1])))))
