"""Incremental refresh from an owned, minimized public-import receipt. No reseed."""
import argparse
import asyncio
import json
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import text

from app.models import ExternalListingSource, Listing
from app.models.ai_fact_pipeline import AiFactJob
from app.repositories.ai_fact_snapshots import FactSnapshotReader
from app.repositories.ai_query_proofs import QueryProofs
from app.schemas.ai_listing_facts import digest
from app.services.ai_pisocompartido_price import prepare_price
from demo.entry import pipeline
from demo.seed_state import timestamp, validated_snapshot


async def refresh(factory, original, incoming):
    cohort = validated_snapshot(original)
    records = validated_snapshot(incoming)
    expected = {(r['lid'],r['sid']) for r in cohort}
    if {(r['lid'],r['sid']) for r in records} != expected:
        raise ValueError('PILOT_REFRESH_COHORT_MISMATCH')
    captured = timestamp(incoming['snapshot_at'])
    facts = pipeline(factory)
    async with factory() as lock:
        locked = await lock.scalar(text("SELECT pg_try_advisory_lock(hashtextextended(current_database() || '/pilot-refresh.v1',0))"))
        if not locked:
            raise ValueError('PILOT_REFRESH_ALREADY_RUNNING')
        try:
            async with factory.begin() as session:
                now = await session.scalar(text('SELECT clock_timestamp()'))
                if not now-timedelta(minutes=10) <= captured <= now:
                    raise ValueError('PILOT_REFRESH_RECEIPT_EXPIRED')
                for record in records:
                    source = record['source']
                    observed = source['last_success_at']
                    checked = source.get('last_checked_at')
                    if (not now-timedelta(seconds=86400) <= observed <= captured
                            or (checked and checked > observed and (
                                source.get('last_state_check_result') != 'active'
                                or source.get('last_state_check_at') != checked or checked > captured))):
                        raise ValueError('PILOT_REFRESH_SOURCE_NOT_FRESH')
                    row = await session.get(ExternalListingSource, record['sid'], with_for_update=True)
                    card = await session.get(Listing, record['lid'], with_for_update=True)
                    if (row is None or card is None or row.canonical_listing_id != record['lid']
                            or row.source_url != source['source_url'] or row.source_name != 'PisoCompartido'
                            or card.deleted_at is not None or card.status != 'published'):
                        raise ValueError('PILOT_REFRESH_IDENTITY_MISMATCH')
                    if row.last_success_at and row.last_success_at > observed:
                        raise ValueError('PILOT_REFRESH_OBSERVATION_ROLLBACK')
                    for key in ('title','city','area','province_code','monthly_price','rental_mode',
                                'source_price_text','source_price_currency','source_price_period','source_price_is_from'):
                        if key in record['listing']:
                            setattr(card,key,record['listing'][key])
                    for key,value in source.items():
                        setattr(row,key,value)
                    row.raw_payload = {'pilot_import_observation.v1':{
                        'observed_at':observed.isoformat(),'public_payload_sha256':digest(source['normalized_payload'])}}
                    row.fingerprint = digest(source['normalized_payload'])
            reader = FactSnapshotReader(factory,max_payload_bytes=65536)
            proofs = QueryProofs(facts)
            for record in records:
                prepared = prepare_price(await reader.capture(record['sid']))
                job_id = await facts.observe(prepared.source)
                async with factory() as session:
                    job = await session.get(AiFactJob,job_id)
                if job is None:
                    raise ValueError('PILOT_REFRESH_JOB_MISSING')
                if job.status != 'succeeded':
                    claim = await facts.claim(source_name='PisoCompartido')
                    if claim is None or claim.job_id != job_id:
                        raise ValueError('PILOT_REFRESH_JOB_RECONCILIATION_REQUIRED')
                    result = await facts.complete(claim,prepared.to_batch(claim,
                        observed_at=record['source']['last_success_at']),prepared.sanitized_fields)
                    if result.status != 'succeeded':
                        raise ValueError('PILOT_REFRESH_FACTS_FAILED')
                if not await proofs.prepare(record['lid']):
                    raise ValueError('PILOT_REFRESH_PROOF_FAILED')
            return {'refreshed':len(records),'snapshot_at':incoming['snapshot_at'],'provider_calls':0,'reseed':False}
        finally:
            await lock.execute(text("SELECT pg_advisory_unlock(hashtextextended(current_database() || '/pilot-refresh.v1',0))"))
            await lock.commit()


async def main():
    from app.db.session import SessionLocal
    from pilot.entry import require_pilot
    require_pilot()
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', help="Receipt path, or - for stdin; no audio/provider calls")
    args = parser.parse_args()
    incoming = json.loads(sys.stdin.read() if args.receipt == '-' else Path(args.receipt).read_text())
    result = await refresh(SessionLocal,json.loads(Path('/demo-input/catalog.json').read_text()),incoming)
    print(json.dumps(result))


if __name__ == '__main__':
    asyncio.run(main())
