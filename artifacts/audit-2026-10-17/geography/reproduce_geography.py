"""Read-only, isolated geography probes. No database/network/payments/env output."""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy.dialects import postgresql
from app.external_sources import NormalizedListing
from app.models import Listing
from app.repositories.listings import apply_search_filters
from app.schemas.listings import ListingPatch, ListingWrite, ListingSearchRequest
from app.services.external_import import apply_primary_source_snapshot
from app.services.listings import apply_write
from app.services.notifications import _saved_search_payload
from app.spain_provinces import address_province_code
from sqlalchemy import select


async def main():
    result = {}
    madrid = dict(title="Madrid room", city="Madrid", area="Centro", street="Calle Mayor 1",
                  approximateAddress="Centro, Madrid", rentalMode="long", monthlyPrice=500,
                  latitude=40.4168, longitude=-3.7038,
                  exactLatitude=40.4168, exactLongitude=-3.7038)
    for postcode in ("08001", "", "garbage", "28000"):
        payload = ListingWrite(**madrid, postcode=postcode)
        listing = Listing()
        apply_write(listing, payload)
        result[f"create_postcode_{postcode or 'EMPTY'}"] = {
            "accepted_by_schema_and_apply_write": True,
            "stored_city": listing.city,
            "stored_postcode": listing.postcode,
            "derived_province": address_province_code(listing.postcode),
        }
    patch = ListingPatch(postcode="08001")
    result["postcode_only_patch"] = patch.model_dump(exclude_unset=True)

    item = NormalizedListing(source_name="Pisos", external_id="audit",
        source_url="https://www.pisos.com/audit", title="Madrid room", description="Audit fixture",
        city="Madrid", area="Centro", rental_mode="long", source_price_text="500 €/mes",
        price_amount=500, price_currency="EUR", price_period="month", price_is_from=False,
        province="Madrid", country="ES", latitude=40.4168, longitude=-3.7038)
    listing = Listing(id=uuid4(), postcode="", external_image_urls=[])
    session = SimpleNamespace(get=AsyncMock(return_value=None), add=lambda row: None)
    await apply_primary_source_snapshot(session, listing, item)
    result["new_import_snapshot"] = {
        "source_province": item.province, "stored_city": listing.city,
        "stored_postcode": listing.postcode,
        "derived_province": address_province_code(listing.postcode),
    }
    for query in ("Madrid", "España", "Santa Cruz de Tenerife"):
        saved = SimpleNamespace(id=uuid4(), filters={}, query=query, rental_mode="long", polygon=[])
        payload = _saved_search_payload(saved)
        sql = apply_search_filters(select(Listing.id), payload).compile(dialect=postgresql.dialect())
        result[f"saved_alert_{query}"] = {
            "provinceCode": payload.provinceCode,
            "sql": str(sql), "parameters": sql.params,
        }
    payload = ListingSearchRequest(provinceCode="28", query="Madrid")
    sql = apply_search_filters(select(Listing.id), payload).compile(dialect=postgresql.dialect())
    result["interactive_madrid_search"] = {"sql": str(sql), "parameters": sql.params}
    rendered = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    (Path(__file__).parent / "reproduction-output.json").write_text(rendered, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2, default=str))


# Every awaited dependency above is an in-memory AsyncMock; no actual I/O or
# scheduling is needed. Avoid constructing Windows' loopback socketpair in the
# sandbox, where even event-loop initialization can block.
try:
    main().send(None)
except StopIteration:
    pass
