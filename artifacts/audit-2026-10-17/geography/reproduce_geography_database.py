"""Real ASGI + isolated PostGIS geography repro; never uses application env files."""
import asyncio
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "backend"))
# Explicit known audit-only settings: no inherited database/provider identity.
os.environ.update(DATABASE_URL="postgresql+asyncpg://audit:audit@127.0.0.1:55439/audit_geo_extra",
    APP_ENV="test", JWT_SECRET="audit-geography-only-test-secret-1234567890", REDIS_URL="",
    STORAGE_BACKEND="local", MEDIA_ROOT=str(OUT / "media"), AUTO_PUBLISH_LISTINGS="true",
    FRONTEND_ORIGINS="http://testserver", EXTERNAL_IMPORT_DOWNLOAD_IMAGES="false",
    STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="", SMTP_HOST="", SENTRY_DSN="")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from app.core.security import create_access_token
from app.db.session import SessionLocal, engine
from app.external_sources import NormalizedListing
from app.main import app
from app.models import AuthSession, ExternalListingSource, Listing, MediaAsset, Notification, User
from app.services.external_import import upsert
from app.spain_provinces import province_code_expression


async def identity(role):
    async with SessionLocal() as session:
        user = User(email=f"geo-{role}-{uuid4()}@example.test", name=f"Audit {role}",
                    role=role, email_verified=True)
        session.add(user)
        await session.flush()
        login = AuthSession(user_id=user.id, token_hash=uuid4().hex * 2,
                            expires_at=datetime.now(UTC) + timedelta(hours=1))
        session.add(login)
        await session.commit()
        token = create_access_token(str(user.id), user.role, session_id=str(login.id))
        return user.id, {"Authorization": f"Bearer {token}"}


async def images(owner):
    async with SessionLocal() as session:
        ids = []
        for _ in range(5):
            unique = uuid4().hex
            asset = MediaAsset(owner_id=owner, storage_key=f"audit/{unique}.webp",
                mime_type="image/webp", size_bytes=1024, width=1200, height=800,
                checksum=hashlib.sha256(unique.encode()).hexdigest(), kind="listing_image")
            session.add(asset)
            await session.flush()
            ids.append(str(asset.id))
        await session.commit()
        return ids


async def main():
    result = {}
    async with SessionLocal() as session:
        db = await session.scalar(text("SELECT current_database()"))
        assert db == "audit_geo_extra", f"Wrong database: {db}"
        result["database"] = db
    host, host_headers = await identity("host")
    tenant, tenant_headers = await identity("tenant")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver",
                           headers={"Origin": "http://testserver"}) as client:
        item = NormalizedListing(source_name="Pisos", external_id=f"geo-{uuid4()}",
            source_url=f"https://www.pisos.com/alquilar/audit-{uuid4()}/",
            title="Imported Madrid audit room", description="Isolated geography fixture",
            city="Madrid", area="Centro", rental_mode="long", source_price_text="500 €/mes",
            price_amount=500, price_currency="EUR", price_period="month", price_is_from=False,
            province="Madrid", country="ES", latitude=40.4168, longitude=-3.7038)
        async with SessionLocal() as session:
            action = await upsert(session, item, scope_key="province:Madrid")
            source = await session.scalar(select(ExternalListingSource).where(
                ExternalListingSource.external_id == item.external_id))
            listing = await session.get(Listing, source.canonical_listing_id)
            derived = await session.scalar(select(province_code_expression()).where(Listing.id == listing.id))
            imported_id = str(listing.id)
            result["GEO01_import"] = {"action": action, "id": imported_id,
                "stored_postcode": listing.postcode, "sql_province": derived,
                "source_snapshot_province": source.normalized_payload.get("province")}
        for key, payload in (("all", {}), ("madrid", {"provinceCode": "28"})):
            response = await client.post("/api/v1/listings/search/cards", json=payload)
            assert response.status_code == 200, response.text
            data = response.json()
            result[f"GEO01_search_{key}"] = {"http": response.status_code,
                "total": data["total"], "contains_import": any(x["id"] == imported_id for x in data["items"])}
        counts = await client.post("/api/v1/listings/provinces/counts", json={})
        assert counts.status_code == 200, counts.text
        result["GEO01_province_count_madrid"] = next(x for x in counts.json()["items"] if x["id"] == "28")

        payload = dict(title="Madrid address forged Barcelona postcode", city="Madrid", area="Centro",
            street="Calle Mayor 1", postcode="08001", approximateAddress="Centro Madrid",
            rentalMode="long", monthlyPrice=500, latitude=40.4168, longitude=-3.7038,
            exactLatitude=40.4168, exactLongitude=-3.7038, assetIds=await images(host))
        response = await client.post("/api/v1/listings", headers=host_headers, json=payload)
        assert response.status_code == 201, response.text
        spoof = response.json()
        result["GEO02_create"] = {key: spoof[key] for key in ("id", "city", "postcode", "provinceCode", "latitude", "longitude", "status")}
        result["GEO02_create"]["http"] = response.status_code
        availability = await client.get(f"/api/v1/payments/listings/{spoof['id']}/top/availability?days=10", headers=host_headers)
        assert availability.status_code == 200, availability.text
        result["GEO02_top_availability"] = availability.json()
        patch = await client.patch(f"/api/v1/listings/{spoof['id']}", headers=host_headers,
                                   json={"postcode": "29001"})
        assert patch.status_code == 200, patch.text
        result["GEO02_postcode_only_patch"] = {"http": patch.status_code,
            **{key: patch.json()[key] for key in ("city", "postcode", "provinceCode", "latitude", "longitude")}}

        saved = await client.post("/api/v1/saved-searches", headers=tenant_headers,
            json={"query": "Madrid", "name": "Madrid province", "rentalMode": "long", "filters": {}, "alertsEnabled": True})
        assert saved.status_code == 201, saved.text
        created_ids = {}
        for label, city, area, postcode, lat, lng in (("getafe", "Getafe", "Centro", "28901", 40.3083, -3.7327),
                ("capital_control", "Madrid", "Centro", "28013", 40.4168, -3.7038)):
            data = {**payload, "title": f"Audit {label} provincial search room", "city": city,
                "area": area, "postcode": postcode, "latitude": lat, "longitude": lng,
                "exactLatitude": lat, "exactLongitude": lng, "assetIds": await images(host)}
            response = await client.post("/api/v1/listings", headers=host_headers, json=data)
            assert response.status_code == 201, response.text
            created_ids[label] = response.json()["id"]
        search = await client.post("/api/v1/listings/search/cards", json={"provinceCode": "28"})
        assert search.status_code == 200, search.text
        ids = {x["id"] for x in search.json()["items"]}
        notices = await client.get("/api/v1/notifications", headers=tenant_headers)
        assert notices.status_code == 200, notices.text
        alert_ids = {x["entityListingId"] for x in notices.json()["items"] if x["type"] == "saved_search_match"}
        result["GEO03_saved_province_alert"] = {"save_http": saved.status_code,
            "getafe_in_province_search": created_ids["getafe"] in ids,
            "capital_in_province_search": created_ids["capital_control"] in ids,
            "getafe_triggered_alert": created_ids["getafe"] in alert_ids,
            "capital_triggered_control_alert": created_ids["capital_control"] in alert_ids}
    (OUT / "database-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2, default=str))
    await engine.dispose()


asyncio.run(main())
