"""Verified facts for an explicitly selected existing import cohort; no crawl.

Uses original source snapshot CAS, timestamps and existing durable fact jobs.
Never edits imported listings/payloads, source timestamps, or a pilot journal.
"""
import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from ..models import ExternalListingSource
from ..models.ai_fact_pipeline import AiFactJob
from ..repositories.ai_fact_snapshots import CapturedParserSnapshot, FactSnapshotReader
from ..repositories.ai_query_proofs import QueryProofs
from ..schemas.ai_fact_bridge import BridgeRejected
from .ai_pisocompartido_housing import minimize_source, prepare_housing

PRICE_FIELDS = frozenset({"source_name", "source_price_text", "rental_mode", "price_currency", "price_period", "price_is_from", "price_amount"})


def prepare_imported_housing(snapshot: CapturedParserSnapshot):
    if snapshot.source_url is None:
        raise BridgeRejected("SOURCE_URL_REQUIRED")
    original = json.loads(snapshot.normalized_json)
    raw = json.loads(snapshot.raw_json)
    if not isinstance(original, dict) or not isinstance(raw, dict):
        raise BridgeRejected("SOURCE_SNAPSHOT_INVALID")
    if original.get("source_url") not in (None, snapshot.source_url):
        raise BridgeRejected("SOURCE_URL_DISAGREEMENT")
    minimized = {key: original.get(key) for key in PRICE_FIELDS}
    minimized["housing_evidence"] = minimize_source({key: original.get(key) for key in ("city", "title", "description")} | {"html": raw.get("html")}, snapshot.source_url)
    # Keep the reference hash of the original stored snapshot. Minimization
    # cannot turn a modified source row into a current proof of the old input.
    return prepare_housing(replace(snapshot, normalized_json=json.dumps(minimized), raw_json="{}"))


async def refresh_saved_catalog(pipeline, source_ids: tuple[UUID, ...], *, include_current_authorities: bool = False) -> dict:
    if not 1 <= len(source_ids) <= 100 or len(set(source_ids)) != len(source_ids):
        raise ValueError("AI_SAVED_EXPLICIT_COHORT_REQUIRED")
    if type(include_current_authorities) is not bool:
        raise TypeError("AI_SAVED_AUTHORITY_POLICY_REQUIRED")
    selected = source_ids
    canonical_count = 0
    if include_current_authorities:
        # The configured source UUIDs remain the explicit cohort anchors. One
        # canonical object can have multiple current imported publisher records;
        # the existing pending barrier requires evidence for every authority.
        # Resolve only already-imported Piso records of these same objects. No
        # new canonical listing, crawl or unsupported publisher is admitted.
        async with pipeline.sessions() as conn:
            anchors = (await conn.execute(select(ExternalListingSource.id,
                ExternalListingSource.canonical_listing_id, ExternalListingSource.source_name).where(
                ExternalListingSource.id.in_(source_ids)))).all()
            if len(anchors) != len(source_ids) or any(row.source_name != "PisoCompartido" for row in anchors):
                raise ValueError("AI_SAVED_COHORT_IDENTITY_MISMATCH")
            canonical = {row.canonical_listing_id for row in anchors}
            authorities = list(await conn.scalars(select(ExternalListingSource.id).where(
                ExternalListingSource.canonical_listing_id.in_(canonical),
                ExternalListingSource.source_name == "PisoCompartido",
                ExternalListingSource.current_status == "active").order_by(ExternalListingSource.id).limit(101)))
        selected = tuple(sorted(set(source_ids) | set(authorities)))
        if len(selected) > 100:
            raise ValueError("AI_SAVED_COHORT_AUTHORITY_BOUND")
        canonical_count = len(canonical)
    reader = FactSnapshotReader(pipeline.sessions, max_payload_bytes=2_097_152)
    proofs = QueryProofs(pipeline)
    ready = rejected = 0
    touched = set()
    for source_id in selected:
        async with pipeline.sessions() as conn:
            row = (await conn.execute(select(ExternalListingSource.canonical_listing_id,
                ExternalListingSource.source_name, ExternalListingSource.current_status).where(
                ExternalListingSource.id == source_id))).first()
        if row is None or row.source_name != "PisoCompartido":
            raise ValueError("AI_SAVED_COHORT_IDENTITY_MISMATCH")
        touched.add(row.canonical_listing_id)
        if row.current_status == "active":
            try:
                prepared = prepare_imported_housing(await reader.capture(source_id))
                job_id = await pipeline.observe(prepared.source)
                async with pipeline.sessions() as conn:
                    job = await conn.get(AiFactJob, job_id) if job_id else None
                if job is not None and job.status not in {"succeeded", "failed", "superseded"}:
                    claim = await pipeline.claim(source_name="PisoCompartido", job_id=job_id)
                    if claim is None:
                        raise ValueError("AI_SAVED_CATALOG_JOB_BUSY")
                    # Re-capture after claiming. Changed inputs fail the existing
                    # to_batch CAS; no obsolete prepared packet is published.
                    prepared = prepare_imported_housing(await reader.capture(source_id))
                    receipt = await pipeline.complete(claim, prepared.to_batch(claim, observed_at=datetime.now(UTC)), prepared.sanitized_fields)
                    if receipt.status != "succeeded":
                        raise ValueError("AI_SAVED_CATALOG_PUBLICATION_FAILED")
            except BridgeRejected:
                rejected += 1
        await pipeline.reconcile_listing(row.canonical_listing_id)
    for listing_id in sorted(touched):
        ready += int(await proofs.prepare(listing_id))
    # Structural preparation is distinct from live source freshness, which the
    # shared saved matcher checks again at every delivery statement.
    result = {"sources": len(source_ids), "proofs_prepared": ready, "rejected": rejected, "provider_calls": 0, "source_updates": 0}
    if include_current_authorities:
        result.update(authority_sources=len(selected), canonical_listings=canonical_count)
    return result
