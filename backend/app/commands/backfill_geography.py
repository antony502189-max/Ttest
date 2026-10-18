"""Dry-run geography remediation; never infer an owner's address from a listing.

python -m app.commands.backfill_geography --expected-database NAME
Add --apply for canonical imported province fields, --bind-top for explicitly
reviewed owner municipality associations. Unknown/overbooked TOP blocks binding.
No geocoder requests, payments, deletions or service-period changes are made.
"""
import argparse
import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import select, text

from ..db.session import SessionLocal
from ..models import ExternalListingSource, Listing, User
from ..models.moderation import ListingPromotion
from ..models.payment_order import PaymentOrder
from ..services.address_geography import MUNICIPALITIES
from ..services.catalog import touch_catalog
from ..services.commercial_advertisements import lock_advertising_capacity
from ..services.external_import import listing_from_snapshot
from ..spain_provinces import imported_province_code


async def backfill(session, *, apply=False, bind_top=False):
    await lock_advertising_capacity(session)
    now = datetime.now(UTC)
    report = {"mode": "apply" if apply else "dry-run", "provinces": [], "topBindings": [],
              "unknown": [], "capacityConflicts": [], "ownerAddressesInferred": 0,
              "topBindingsApplied": bool(apply and bind_top), "localAddressVerificationRequired": []}
    listings = list((await session.scalars(select(Listing).order_by(Listing.id).with_for_update())).all())
    owners = {row.id: row for row in (await session.scalars(select(User))).all()}
    by_id = {row.id: row for row in listings}
    source_rows = (await session.scalars(select(ExternalListingSource).where(
        ExternalListingSource.current_status == "active"))).all()
    sources = {(row.canonical_listing_id, row.source_name): row for row in source_rows}
    province_changes = []
    for listing in listings:
        if not listing.is_external and not listing.address_verified_at:
            report["localAddressVerificationRequired"].append(str(listing.id))
        if listing.province_code or not listing.is_external:
            continue
        source = sources.get((listing.id, listing.primary_source))
        try:
            code = imported_province_code(listing_from_snapshot(source.normalized_payload)) if source else None
        except (ValueError, TypeError, KeyError):
            code = None
        if code:
            report["provinces"].append({"listingId": str(listing.id), "provinceCode": code})
            province_changes.append((listing, code))
        else:
            report["unknown"].append({"kind": "listing", "id": str(listing.id), "reason": "No consistent primary-source evidence"})

    promotions = list((await session.scalars(select(ListingPromotion).where(
        (ListingPromotion.ends_at.is_(None)) | (ListingPromotion.ends_at > now)).with_for_update())).all())
    orders = list((await session.scalars(select(PaymentOrder).where(
        PaymentOrder.kind == "listing_top",
        (PaymentOrder.status.in_(["creating", "pending"])) | (
            (PaymentOrder.status == "paid") & PaymentOrder.financial_status.notin_(["refunded", "dispute_lost"])
            & ((PaymentOrder.service_ends_at.is_(None)) | (PaymentOrder.service_ends_at > now))
        ),
    ).with_for_update())).all())
    bindings, windows = [], {}
    unknown_top = False
    for row in [*promotions, *orders]:
        is_order = isinstance(row, PaymentOrder)
        listing_id = row.target_id if is_order else row.listing_id
        listing = by_id.get(listing_id)
        owner = owners.get(listing.owner_user_id) if listing else None
        code = row.top_municipality_code
        if not code and owner and owner.address_verified_at and owner.municipality_code in MUNICIPALITIES:
            code = owner.municipality_code
            bindings.append((row, code))
            report["topBindings"].append({"kind": "order" if is_order else "promotion",
                                          "id": str(row.id if is_order else listing_id), "municipalityCode": code})
        if code not in MUNICIPALITIES:
            unknown_top = True
            report["unknown"].append({"kind": "top", "id": str(listing_id), "reason": "Owner must verify their own address; never copy property address"})
            continue
        start = (row.service_starts_at or now) if is_order else row.starts_at
        end = row.service_ends_at if is_order else row.ends_at
        if is_order and row.status in {"creating", "pending"}:
            start, end = now, None
        windows.setdefault(code, []).append((listing_id, start, end))
    for code, intervals in windows.items():
        for checkpoint in {now, *(start for _, start, _ in intervals if start > now)}:
            count = len({key for key, start, end in intervals if start <= checkpoint and (end is None or end > checkpoint)})
            if count > 3:
                report["capacityConflicts"].append({"municipalityCode": code, "at": checkpoint.isoformat(), "occupied": count})
    if apply and bind_top and (unknown_top or report["capacityConflicts"]):
        raise ValueError("TOP binding refused: resolve unknown owners/overbooked periods in the dry-run report first")
    if apply:
        for listing, code in province_changes:
            listing.province_code = code
        if bind_top:
            for row, code in bindings:
                row.top_municipality_code = code
        await touch_catalog(session)
        await session.commit()
    else:
        await session.rollback()
    return report


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--bind-top", action="store_true")
    parser.add_argument("--expected-database", required=True)
    args = parser.parse_args()
    async with SessionLocal() as session:
        database = await session.scalar(text("SELECT current_database()"))
        if database != args.expected_database:
            raise SystemExit("Database name does not match --expected-database; no changes made")
        print(json.dumps(await backfill(session, apply=args.apply, bind_top=args.bind_top), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
