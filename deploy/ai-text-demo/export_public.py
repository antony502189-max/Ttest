"""Owner-approved <=20 public PisoCompartido records, no accounts/contact export."""
import argparse
import json
import subprocess
from pathlib import Path
from uuid import UUID

from sqlalchemy.dialects import postgresql

from app.models import Listing
from app.repositories.ai_fact_quality import source_freshness_predicate
from app.repositories.ai_fact_snapshots import CapturedParserSnapshot
from app.repositories.listings import visible_query
from app.schemas.ai_fact_bridge import BridgeReference
from app.services.ai_fact_quality import FactQualityPolicy
from app.services.ai_hard_matching import HardMatchPlan
from app.services.ai_pisocompartido_price import prepare_price


def consistent_source_join(source_ids=()):
    cohort = " AND x.id IN ("+",".join("'"+str(UUID(str(value)))+"'" for value in source_ids)+") " if source_ids else ""
    return ("LEFT JOIN LATERAL (SELECT * FROM external_listing_sources x "
        "WHERE x.canonical_listing_id=l.id AND x.source_name='PisoCompartido' AND x.current_status='active' "
        "AND x.source_url=l.primary_source_url AND x.source_price_text=l.source_price_text "
        "AND x.normalized_payload->'price_amount'=to_jsonb(l.monthly_price) "
        "AND x.normalized_payload->'price_currency'='\"EUR\"'::jsonb "
        "AND x.normalized_payload->'price_period'='\"month\"'::jsonb "
        "AND x.normalized_payload->'rental_mode'='\"long\"'::jsonb "
        "AND x.normalized_payload->'price_is_from'='false'::jsonb "
        "AND x.last_success_at BETWEEN statement_timestamp()-interval '86400 seconds' AND statement_timestamp() "
        "AND (x.last_checked_at IS NULL OR x.last_checked_at<=x.last_success_at OR "
        "(x.last_state_check_result='active' AND x.last_state_check_at=x.last_checked_at AND x.last_checked_at<=statement_timestamp())) "
        + cohort + "ORDER BY x.last_success_at DESC NULLS LAST,x.id LIMIT 1) s ON true")


def snapshot_statement(cohort=None,limit=21):
    listing_ids = tuple(UUID(r["listing"]["id"]) for r in cohort["records"]) if cohort else ()
    source_ids = tuple(UUID(r["source"]["id"]) for r in cohort["records"]) if cohort else ()
    if cohort and (not 1 <= len(listing_ids) <= 20 or len(set(listing_ids)) != len(listing_ids) or len(set(source_ids)) != len(source_ids)):
        raise ValueError("EXISTING_BOUNDED_COHORT_REQUIRED")
    fresh = source_freshness_predicate(Listing.id, HardMatchPlan(()), FactQualityPolicy(
        price_max_age_seconds=86400, policy_max_age_seconds=86400, evidence_retention_seconds=86400))
    query = visible_query().with_only_columns(Listing.id).where(
        fresh, Listing.primary_source == "PisoCompartido").order_by(Listing.id).limit(limit)
    if cohort:
        query = visible_query().with_only_columns(Listing.id).where(
            fresh, Listing.primary_source == "PisoCompartido", Listing.id.in_(listing_ids)).order_by(Listing.id).limit(20)
    eligible = str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).replace("%%", "%")
    card_fields = ["id", "title", "city", "area", "province_code", "rental_mode", "monthly_price", "room_type", "is_external", "primary_source", "primary_source_url", "source_price_text", "source_price_currency", "source_price_period", "source_price_is_from", "external_image_urls", "furnished", "room_capacity", "room_size_m2", "bills_included", "bathroom", "kitchen", "pets_allowed", "smoking_allowed", "children_allowed", "amenities", "restrictions"]
    source_fields = ["id", "source_name", "external_id", "source_url", "source_price_text", "current_status", "last_success_at", "last_checked_at", "content_updated_at", "last_state_check_at", "last_state_check_result"]
    price_fields = ["source_name", "source_price_text", "rental_mode", "price_currency", "price_period", "price_is_from", "price_amount"]
    card = ",".join(f"'{k}',l.{k}" for k in card_fields) + ", 'latitude',ST_Y(l.location::geometry),'longitude',ST_X(l.location::geometry)"
    card += ",'published_at',coalesce(l.published_at,l.created_at)"
    source = ",".join(f"'{k}',s.{k}" for k in source_fields)
    normalized = ",".join(f"'{k}',s.normalized_payload->'{k}'" for k in price_fields)
    # Existing thirteen IDs only. The refresh consumer minimizes these public
    # source fields into recognized evidence before storage; no card defaults.
    if cohort:
        normalized += ",'housing_source',jsonb_build_object('city',s.normalized_payload->'city','title',s.normalized_payload->'title','description',s.normalized_payload->'description','html',s.raw_payload->'html')"
    statement = (f"WITH eligible AS ({eligible}) SELECT jsonb_build_object('snapshot_at',statement_timestamp(),"
        f"'records',jsonb_agg(jsonb_build_object('listing',jsonb_build_object({card}),"
        f"'source',jsonb_build_object({source},'normalized_payload',jsonb_build_object({normalized}))))) "
        f"FROM eligible e JOIN listings l ON l.id=e.id {consistent_source_join(source_ids)}")
    if not cohort:return statement
    manifest=json.dumps([{'listing_id':str(lid),'source_id':str(sid)} for lid,sid in zip(listing_ids,source_ids,strict=True)])
    return (f"WITH raw_snapshot(payload) AS ({statement}),manifest(items) AS (SELECT '{manifest}'::jsonb),"
        "active_snapshot AS (SELECT payload->'snapshot_at' AS captured,coalesce((SELECT jsonb_agg(r) FROM "
        "jsonb_array_elements(coalesce(nullif(payload->'records','null'::jsonb),'[]'::jsonb)) r "
        "WHERE EXISTS (SELECT 1 FROM jsonb_array_elements(items) m WHERE "
        "r->'listing'->>'id'=m->>'listing_id' AND r->'source'->>'id'=m->>'source_id')),'[]'::jsonb) AS records "
        "FROM raw_snapshot CROSS JOIN manifest) SELECT jsonb_build_object('schema','pilot-cohort.v2',"
        "'snapshot_at',captured,'cohort',items,'records',records,'tombstones',coalesce((SELECT "
        "jsonb_agg(jsonb_build_object('listing_id',m->>'listing_id','source_id',m->>'source_id','reason','ineligible')) "
        "FROM jsonb_array_elements(items) m WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements(records) r "
        "WHERE r->'listing'->>'id'=m->>'listing_id' AND r->'source'->>'id'=m->>'source_id')),'[]'::jsonb)) "
        "FROM active_snapshot CROSS JOIN manifest")


def main():
    options = argparse.ArgumentParser()
    options.add_argument("--output", type=Path, default=Path("output/ai-text-runtime-20261108/private/catalog.json"))
    options.add_argument("--limit", type=int, choices=(20, 21), default=21)
    options.add_argument("--cohort", type=Path, help="Existing immutable pilot snapshot; never expand its IDs")
    options.add_argument("--sql-only", action="store_true", help="Print the read-only query for the local host runner")
    args = options.parse_args()
    cohort = json.loads(args.cohort.read_text()) if args.cohort else None
    sql="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout='5000ms'; "+snapshot_statement(cohort,args.limit)+"; COMMIT;"
    if args.sql_only:
        if not cohort:
            raise ValueError("EXISTING_BOUNDED_COHORT_REQUIRED")
        print(sql)
        return
    remote = """docker exec -i ttest-production-postgres-1 sh -c 'psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' """
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "ConnectTimeout=10", "root@169.58.147.65", remote], input=sql, text=True,
        capture_output=True, encoding="utf-8", timeout=30, check=False)
    if result.returncode:
        raise ValueError("READ_ONLY_PUBLIC_SNAPSHOT_FAILED")
    data = json.loads(result.stdout)
    if cohort:
        from pilot.refresh import receipt
        receipt(cohort,data)
    elif not data["records"] or len(data["records"]) > 20:
        raise ValueError("REAL_COHORT_BOUND_EXCEEDED_OR_EMPTY")
    for row in data["records"]:
        value = row["source"]
        if value["id"] is None:
            raise ValueError("PUBLIC_SNAPSHOT_NO_CONSISTENT_SOURCE")
        sid = UUID(value["id"])
        prepare_price(CapturedParserSnapshot(BridgeReference(source_record_id=sid,
            canonical_listing_id=UUID(row["listing"]["id"]), source_identifier="PisoCompartido:" + sid.hex,
            snapshot_hash="a" * 64), "{}", json.dumps(value["normalized_payload"]), value["source_price_text"]))
    target = args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError("REFUSING_TO_REPLACE_PREPARED_SNAPSHOT")
    target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"real_records_exported": len(data["records"]), "snapshot_at": data["snapshot_at"],
        "contacts_exported": False, "price_mapping_pass": len(data["records"]), "provider_calls": 0}))


if __name__ == "__main__":
    main()
