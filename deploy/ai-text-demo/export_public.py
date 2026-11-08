"""Owner-approved <=20 public PisoCompartido records, no accounts/contact export."""
import argparse
import json
import subprocess
from pathlib import Path
from uuid import UUID

from app.models import Listing
from app.repositories.ai_fact_quality import source_freshness_predicate
from app.repositories.ai_fact_snapshots import CapturedParserSnapshot
from app.repositories.listings import visible_query
from app.schemas.ai_fact_bridge import BridgeReference
from app.services.ai_fact_quality import FactQualityPolicy
from app.services.ai_hard_matching import HardMatchPlan
from app.services.ai_pisocompartido_price import prepare_price
from sqlalchemy.dialects import postgresql


def main():
    options = argparse.ArgumentParser()
    options.add_argument("--output", type=Path, default=Path("output/ai-text-runtime-20261108/private/catalog.json"))
    options.add_argument("--limit", type=int, choices=(20, 21), default=21)
    args = options.parse_args()
    fresh = source_freshness_predicate(Listing.id, HardMatchPlan(()), FactQualityPolicy(
        price_max_age_seconds=86400, policy_max_age_seconds=86400, evidence_retention_seconds=86400))
    query = visible_query().with_only_columns(Listing.id).where(
        fresh, Listing.primary_source == "PisoCompartido").order_by(Listing.id).limit(args.limit)
    eligible = str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).replace("%%", "%")
    card_fields = ["id", "title", "city", "area", "province_code", "rental_mode", "monthly_price", "room_type", "is_external", "primary_source", "primary_source_url", "source_price_text", "source_price_currency", "source_price_period", "source_price_is_from", "external_image_urls", "furnished", "room_capacity", "room_size_m2", "bills_included", "bathroom", "kitchen", "pets_allowed", "smoking_allowed", "children_allowed", "amenities", "restrictions"]
    source_fields = ["id", "source_name", "external_id", "source_url", "source_price_text", "current_status", "last_success_at", "last_checked_at", "content_updated_at", "last_state_check_at", "last_state_check_result"]
    price_fields = ["source_name", "source_price_text", "rental_mode", "price_currency", "price_period", "price_is_from", "price_amount"]
    card = ",".join(f"'{k}',l.{k}" for k in card_fields) + ", 'latitude',ST_Y(l.location::geometry),'longitude',ST_X(l.location::geometry)"
    card += ",'published_at',coalesce(l.published_at,l.created_at)"
    source = ",".join(f"'{k}',s.{k}" for k in source_fields)
    normalized = ",".join(f"'{k}',s.normalized_payload->'{k}'" for k in price_fields)
    sql = ("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout='5000ms'; "
        f"WITH eligible AS ({eligible}) SELECT json_build_object('snapshot_at',statement_timestamp(),"
        f"'records',json_agg(json_build_object('listing',json_build_object({card}),"
        f"'source',json_build_object({source},'normalized_payload',jsonb_build_object({normalized}))))) "
        "FROM eligible e JOIN listings l ON l.id=e.id JOIN LATERAL (SELECT * FROM external_listing_sources x "
        "WHERE x.canonical_listing_id=l.id AND x.source_name='PisoCompartido' AND x.current_status='active' "
        "ORDER BY x.last_success_at DESC NULLS LAST,x.id LIMIT 1) s ON true; COMMIT;")
    remote = """docker exec -i ttest-production-postgres-1 sh -c 'psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' """
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "ConnectTimeout=10", "root@169.58.147.65", remote], input=sql, text=True,
        capture_output=True, encoding="utf-8", timeout=30, check=False)
    if result.returncode:
        raise ValueError("READ_ONLY_PUBLIC_SNAPSHOT_FAILED")
    data = json.loads(result.stdout)
    if not data["records"] or len(data["records"]) > 20:
        raise ValueError("REAL_COHORT_BOUND_EXCEEDED_OR_EMPTY")
    for row in data["records"]:
        value = row["source"]
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
