"""Synthetic admin query benchmark; only accepts the dedicated local test DB."""
import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from uuid import UUID

from geoalchemy2 import WKTElement
from sqlalchemy import delete, event, insert, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.db.session import SessionLocal, engine
from app.models import Listing, User
from app.services.admin_listings import list_listings


async def main():
    phase = os.environ.get("ADMIN_BENCHMARK_PHASE", "before")
    measurements = []
    async with SessionLocal() as session:
        database = await session.scalar(text("select current_database()"))
        if database != "ttest_adminperf_test" or engine.url.host not in {"127.0.0.1", "localhost"}:
            raise RuntimeError("Benchmark requires local ttest_adminperf_test")
        owner_id = UUID("00000000-0000-4000-8000-000000000001")
        if not await session.get(User, owner_id):
            await session.execute(insert(User), [{"id": owner_id, "email": "benchmark@example.test", "name": "Ana García", "role": "host"}])
        for count in [100, 1000, 5000, 10000]:
            await session.execute(delete(Listing).where(Listing.owner_user_id == owner_id))
            await session.execute(insert(Listing), [{
                "id": UUID(f"10000000-0000-4000-8000-{i:012}"), "owner_user_id": owner_id,
                "title": f"Habitación {i:05}", "area": "Centro", "city": "Santa Cruz", "approximate_address": "Centro",
                "rental_mode": "long" if i % 2 == 0 else "holiday", "status": "published",
                "monthly_price": 500 if i % 2 == 0 else None, "nightly_price": 50 if i % 2 else None,
                "location": WKTElement("POINT(-16.25 28.46)", srid=4326),
                "created_at": datetime(2026, 9, 30, tzinfo=UTC) - timedelta(seconds=i),
            } for i in range(count)])
            await session.commit()
            await session.execute(text("ANALYZE listings"))
            for visit in ["initial", "repeated"]:
                sql_times = []
                statements = []
                starts = []
                def before(conn, cursor, statement, parameters, context, executemany):
                    starts.append(perf_counter())
                    if context.compiled is not None:
                        statements.append(context.compiled.statement)
                def after(conn, cursor, statement, parameters, context, executemany):
                    sql_times.append((perf_counter() - starts.pop()) * 1000)
                event.listen(engine.sync_engine, "before_cursor_execute", before)
                event.listen(engine.sync_engine, "after_cursor_execute", after)
                started = perf_counter()
                requests = 0
                cursor = None
                collected = []
                while True:
                    rows = await list_listings(session, None, None, limit=200 if phase == "before" else 50, offset=0,
                        after_created_at=cursor.createdAt if cursor else None, after_id=cursor.id if cursor else None)
                    requests += 1
                    collected.extend(rows)
                    if phase == "after" or len(rows) < 200:
                        break
                    cursor = rows[-1]
                elapsed = (perf_counter() - started) * 1000
                event.remove(engine.sync_engine, "before_cursor_execute", before)
                event.remove(engine.sync_engine, "after_cursor_execute", after)
                plan = await session.scalar(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + str(statements[0].compile(
                    dialect=engine.sync_engine.dialect, compile_kwargs={"literal_binds": True}))))
                measurements.append({"count": count, "visit": visit, "apiCollectionMs": elapsed, "requests": requests,
                    "sqlCount": len(sql_times), "sqlTotalMs": sum(sql_times), "firstQueryMs": sql_times[0],
                    "explainExecutionMs": plan[0]["Execution Time"], "payloadBytes": len(json.dumps([r.model_dump(mode="json") for r in collected]).encode())})
    target = Path("output/admin-performance") / phase / "database.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(measurements, indent=2), encoding="utf-8")
    print(json.dumps(measurements, indent=2))
    await engine.dispose()


asyncio.run(main())
