from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.config import get_settings

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def listing_payload() -> dict:
    return {
        "title": "Habitación luminosa <Centro>",
        "city": "Santa Cruz de Tenerife",
        "area": "Centro",
        "street": "Calle privada 123",
        "postcode": "38001",
        "approximateAddress": "Centro · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 675,
        "nightlyPrice": None,
        "weeklyPrice": None,
        "roomType": "Habitación individual",
        "availableFrom": datetime.now(UTC).date().isoformat(),
        "availableUntil": None,
        "minimumStayMonths": 1,
        "minimumNights": None,
        "depositAmount": 675,
        "billsIncluded": True,
        "bathroom": "Baño compartido",
        "kitchen": "Cocina compartida",
        "furnished": True,
        "roomSizeM2": 14,
        "bedroomCount": 3,
        "currentResidents": 2,
        "roomCapacity": 1,
        "shower": "Ducha compartida",
        "tenantRequirement": "any",
        "smokingAllowed": False,
        "petsAllowed": False,
        "childrenAllowed": False,
        "empadronamientoAllowed": True,
        "restrictions": [],
        "amenities": ["Wifi"],
        "latitude": 28.4636,
        "longitude": -16.2518,
        "exactLatitude": 28.4639,
        "exactLongitude": -16.2514,
        "description": "Habitación tranquila </script><script>alert('x')</script> cerca del tranvía.",
        "homeDescription": "Piso compartido tranquilo.",
        "advertiserType": "Particular",
        "source": "seo-integration-test",
        "expiresAt": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
    }


async def test_canonical_listing_html_sitemap_and_visibility_lifecycle(client: AsyncClient, register_user):
    token, _ = await register_user(client, email="seo-host@example.com", role="host")
    created = await client.post(
        "/api/v1/listings",
        headers=auth(token),
        json=listing_payload(),
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]
    origin = get_settings().frontend_app_url.rstrip("/")

    public = await client.get(f"/habitacion/{listing_id}")
    assert public.status_code == 200, public.text
    assert public.headers["content-type"].startswith("text/html")
    assert public.headers["cache-control"] == "public, max-age=60"
    assert '<meta name="robots" content="index,follow,max-image-preview:large">' in public.text
    assert f'<link rel="canonical" href="{origin}/habitacion/{listing_id}">' in public.text
    assert '<meta property="og:title" content="Habitación luminosa &lt;Centro&gt;">' in public.text
    assert '<script type="application/ld+json">' in public.text
    assert f'href="{origin}/#/habitacion/{listing_id}"' in public.text
    assert "Calle privada 123" not in public.text
    assert "28.4639" not in public.text
    assert "<script>alert('x')</script>" not in public.text
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert('x')" in public.text

    sitemap = await client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert sitemap.headers["content-type"].startswith("application/xml")
    assert f"{origin}/habitacion/{listing_id}" in sitemap.text

    robots = await client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /api/" in robots.text
    assert "Disallow: /perfil" in robots.text
    assert f"Sitemap: {origin}/sitemap.xml" in robots.text

    hidden = await client.patch(
        f"/api/v1/listings/{listing_id}",
        headers=auth(token),
        json={"status": "hidden"},
    )
    assert hidden.status_code == 200, hidden.text
    assert (await client.get(f"/habitacion/{listing_id}")).status_code == 404
    assert listing_id not in (await client.get("/sitemap.xml")).text
