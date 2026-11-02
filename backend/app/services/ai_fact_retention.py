"""Bounded removal of disposable proofs, old evidence and ineligible AI copies.

Never deletes legacy listings/sources or starts an extractor. Uses the same
anchor -> listing -> source lock order as fact ingestion.
"""
from datetime import timedelta

from sqlalchemy import delete, or_, select, update

from ..models import Listing
from ..models.ai_fact_pipeline import AiFactCatalog, AiFactJob, AiFactRematchEvent, AiFactSource
from ..models.ai_listing_facts import AiListingFact, AiListingFactBatch, AiListingSearchFeatures
from ..models.ai_operating_policy import AiProofAge
from ..models.ai_query_proof import AiQueryProof
from ..repositories.ai_card_values import source_owner_eligible
from ..repositories.ai_fact_pipeline import FactPipeline
from ..repositories.ai_search_quota import _now


class AIFactRetention:
    def __init__(self, pipeline: FactPipeline):
        self.pipeline = pipeline

    async def prune(self, *, batch_size: int = 1000) -> dict[str, int]:
        if type(batch_size) is not int or not 1 <= batch_size <= 1000:
            raise ValueError("bounded fact retention batch required")
        counts = {"proofs": 0, "facts": 0, "batches": 0, "jobs": 0, "events": 0, "sources": 0, "catalogs": 0}
        async with self.pipeline.sessions.begin() as conn:
            now = await _now(conn)
            valid_age = select(1).where(AiProofAge.canonical_listing_id == AiQueryProof.canonical_listing_id,
                AiProofAge.signature == AiQueryProof.signature, AiProofAge.prepared_at <= now,
                AiProofAge.prepared_at > now - timedelta(hours=24)).exists()
            old_proofs = list(await conn.scalars(select(AiQueryProof.canonical_listing_id).where(~valid_age)
                .order_by(AiQueryProof.canonical_listing_id).limit(batch_size).with_for_update(skip_locked=True)))
            counts["proofs"] = len(list(await conn.scalars(delete(AiQueryProof).where(
                AiQueryProof.canonical_listing_id.in_(old_proofs)).returning(AiQueryProof.canonical_listing_id))))
            await conn.execute(delete(AiProofAge).where(AiProofAge.canonical_listing_id.in_(old_proofs)))
            orphan_ages = select(AiProofAge.canonical_listing_id).where(~select(1).where(
                AiQueryProof.canonical_listing_id == AiProofAge.canonical_listing_id).exists()).order_by(
                    AiProofAge.canonical_listing_id).limit(batch_size).with_for_update(skip_locked=True)
            counts["proofs"] += len(list(await conn.scalars(delete(AiProofAge).where(
                AiProofAge.canonical_listing_id.in_(orphan_ages)).returning(AiProofAge.canonical_listing_id))))
        # At most one invalidated canonical subtree per pass. Large histories
        # drain over bounded batches; an expired proof is never usable meanwhile.
        async with self.pipeline.sessions.begin() as conn:
            visible = select(1).where(Listing.id == AiFactCatalog.canonical_listing_id,
                Listing.status == "published", Listing.deleted_at.is_(None), source_owner_eligible()).exists()
            present = select(1).where(AiFactSource.canonical_listing_id == AiFactCatalog.canonical_listing_id).exists()
            active = select(1).where(AiFactSource.canonical_listing_id == AiFactCatalog.canonical_listing_id,
                AiFactSource.source_status == "active").exists()
            listing_id = await conn.scalar(select(AiFactCatalog.canonical_listing_id).where(or_(~visible, present & ~active))
                .order_by(AiFactCatalog.canonical_listing_id).limit(1).with_for_update(skip_locked=True))
            if listing_id is not None:
                still_visible, _ = await self.pipeline._authority(conn, listing_id)
                current_active = await conn.scalar(select(AiFactSource.source_record_id).where(
                    AiFactSource.canonical_listing_id == listing_id, AiFactSource.source_status == "active").limit(1))
                if not still_visible or current_active is None:
                    await conn.execute(delete(AiQueryProof).where(AiQueryProof.canonical_listing_id == listing_id))
                    await conn.execute(delete(AiListingSearchFeatures).where(
                        AiListingSearchFeatures.canonical_listing_id == listing_id))
                    jobs = select(AiFactJob.id).where(AiFactJob.canonical_listing_id == listing_id).order_by(
                        AiFactJob.id).limit(batch_size).with_for_update(skip_locked=True)
                    counts["jobs"] += len(list(await conn.scalars(delete(AiFactJob).where(
                        AiFactJob.id.in_(jobs)).returning(AiFactJob.id))))
                    no_jobs = ~select(1).where(AiFactJob.source_record_id == AiFactSource.source_record_id).exists()
                    sources = list(await conn.scalars(select(AiFactSource.source_record_id).where(
                        AiFactSource.canonical_listing_id == listing_id, no_jobs).order_by(
                        AiFactSource.source_record_id).limit(batch_size).with_for_update(skip_locked=True)))
                    if sources:
                        # Remove FK to evidence before pruning its leaf rows.
                        await conn.execute(update(AiFactSource).where(AiFactSource.source_record_id.in_(sources)).values(batch_id=None))
                        await conn.execute(delete(AiFactSource).where(AiFactSource.source_record_id.in_(sources)))
                        counts["sources"] += len(sources)
                    events = select(AiFactRematchEvent.id).where(
                        AiFactRematchEvent.canonical_listing_id == listing_id).order_by(
                        AiFactRematchEvent.id).limit(batch_size).with_for_update(skip_locked=True)
                    counts["events"] += len(list(await conn.scalars(delete(AiFactRematchEvent).where(
                        AiFactRematchEvent.id.in_(events)).returning(AiFactRematchEvent.id))))
        async with self.pipeline.sessions.begin() as conn:
            now = await _now(conn)
            # A batch referenced by current source state is never history.
            unreferenced = ~select(1).where(AiFactSource.batch_id == AiListingFactBatch.id).exists()
            invisible = ~select(1).where(Listing.id == AiListingFactBatch.canonical_listing_id,
                Listing.status == "published", Listing.deleted_at.is_(None), source_owner_eligible()).exists()
            expired_batches = select(AiListingFactBatch.id).where(unreferenced,
                or_(AiListingFactBatch.observed_at <= now - timedelta(days=7), invisible))
            fact_ids = select(AiListingFact.id).where(AiListingFact.batch_id.in_(expired_batches)).order_by(
                AiListingFact.id).limit(batch_size).with_for_update(skip_locked=True)
            counts["facts"] = len(list(await conn.scalars(delete(AiListingFact).where(
                AiListingFact.id.in_(fact_ids)).returning(AiListingFact.id))))
            no_facts = ~select(1).where(AiListingFact.batch_id == AiListingFactBatch.id).exists()
            batches = expired_batches.where(no_facts).order_by(AiListingFactBatch.id).limit(batch_size).with_for_update(skip_locked=True)
            counts["batches"] = len(list(await conn.scalars(delete(AiListingFactBatch).where(
                AiListingFactBatch.id.in_(batches)).returning(AiListingFactBatch.id))))
        async with self.pipeline.sessions.begin() as conn:
            now = await _now(conn)
            current_job = select(1).where(AiFactSource.source_record_id == AiFactJob.source_record_id,
                AiFactSource.generation == AiFactJob.generation).exists()
            jobs = select(AiFactJob.id).where(AiFactJob.status.in_(("succeeded", "failed", "superseded")),
                AiFactJob.available_at <= now - timedelta(days=7), ~current_job).order_by(
                AiFactJob.id).limit(batch_size).with_for_update(skip_locked=True)
            counts["jobs"] += len(list(await conn.scalars(delete(AiFactJob).where(
                AiFactJob.id.in_(jobs)).returning(AiFactJob.id))))
            events = select(AiFactRematchEvent.id).where(AiFactRematchEvent.created_at <= now - timedelta(days=7)).order_by(
                AiFactRematchEvent.id).limit(batch_size).with_for_update(skip_locked=True)
            counts["events"] += len(list(await conn.scalars(delete(AiFactRematchEvent).where(
                AiFactRematchEvent.id.in_(events)).returning(AiFactRematchEvent.id))))
        if listing_id is not None:
            async with self.pipeline.sessions.begin() as conn:
                # Never reset an active catalog's monotonic revision. Empty
                # deleted-listing anchors can go; otherwise they must not starve
                # later canonical IDs on every retention pass.
                anchor = await conn.scalar(select(AiFactCatalog).where(
                    AiFactCatalog.canonical_listing_id == listing_id).with_for_update(skip_locked=True))
                if anchor is not None:
                    public, _ = await self.pipeline._authority(conn, listing_id)
                    if not public:
                        models = (AiFactSource, AiFactJob, AiFactRematchEvent, AiListingFactBatch)
                        remaining = [await conn.scalar(select(model.canonical_listing_id).where(
                            model.canonical_listing_id == listing_id).limit(1)) for model in models]
                        if not any(remaining):
                            await conn.delete(anchor)
                            counts["catalogs"] = 1
        return counts
