"""Explicit check against the finite synthetic source, never a real crawler.

The authoritative source here is the committed fixture generator. Only an
exact identity AND payload match can advance last_success_at. Changed or
unknown records are left untouched; proof preparation alone cannot refresh it.
"""
import asyncio
import json

from sqlalchemy import func, update

from lab.ai_text import pipeline, require_lab, verify_database


def fixtures():
    from lab.acceptance import CASES as holiday_cases
    from lab.acceptance import description_for
    from lab.acceptance import identifier as holiday_id
    from lab.seed_ai_text import CASES, identifier
    for name, price, pets in CASES:
        description = f"Long-term rental. Rent {price} EUR monthly. " + (
            "Pets allowed." if pets is True else "No pets." if pets is False else "No pet information.")
        yield identifier("source-" + name), identifier(name), "synthetic-lab", name, f"https://example.invalid/synthetic/{name}", description
    for name, *_ in holiday_cases:
        yield holiday_id("source-" + name), holiday_id(name), "synthetic-acceptance", name, f"https://example.invalid/acceptance/{name}", description_for(name)


async def run():
    require_lab()
    from app.db.session import SessionLocal, engine
    from app.models import ExternalListingSource as Source
    from app.repositories.ai_query_proofs import QueryProofs
    await verify_database(SessionLocal)
    checked, prepared = [], 0
    try:
        async with SessionLocal.begin() as conn:
            for sid, lid, provider, external, url, description in fixtures():
                matched = await conn.scalar(update(Source).where(Source.id == sid,
                    Source.canonical_listing_id == lid, Source.source_name == provider,
                    Source.external_id == external, Source.source_url == url,
                    Source.raw_payload == {"description": description},
                    Source.normalized_payload == {"description": description},
                    Source.source_price_text.is_(None), Source.current_status == "active"
                ).values(last_success_at=func.clock_timestamp()).returning(Source.canonical_listing_id))
                if matched is not None:
                    checked.append(matched)
        proofs = QueryProofs(pipeline(SessionLocal))
        for lid in checked:
            prepared += bool(await proofs.prepare(lid))
        print(json.dumps({"synthetic_sources_checked": len(checked), "prepared": prepared}))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
