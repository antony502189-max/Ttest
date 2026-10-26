"""Explicitly invoked offline primitives. No importer hook, scheduler or provider.

Mutation lock order: AI canonical anchor -> existing listing -> existing sources
ordered by UUID -> AI sources -> jobs. Claim/failure lock only one job. Integration
must review this against importer transactions before enabling concurrent live use.
"""

from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4, uuid5

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models import ExternalListingSource, Listing
from ..models.ai_fact_pipeline import AiFactCatalog, AiFactJob, AiFactRematchEvent, AiFactSource
from ..models.ai_listing_facts import AiListingFact, AiListingFactBatch, AiListingSearchFeatures
from ..schemas.ai_fact_pipeline import (
    FactJobClaim,
    FactJobReceipt,
    FactQueuePolicy,
    FactResultConflict,
    SourceIdentityConflict,
    SourceInput,
    StaleFactWorker,
)
from ..schemas.ai_listing_facts import FactBatch, FactVocabulary, Version, digest
from ..services.ai_fact_resolver import MAX_SOURCE_OBSERVATIONS, resolve_sources
from .ai_fact_snapshots import source_snapshot_hash


async def _now(session: AsyncSession) -> datetime:
    return (await session.execute(select(func.clock_timestamp()))).scalar_one()


def _status(value: str) -> str:
    return value if value in {"active", "unknown", "unavailable"} else "retired"


class FactPipeline:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], policy: FactQueuePolicy,
                 vocabulary: FactVocabulary, *, resolver_version: Version):
        # Validate configuration without selecting silent production defaults.
        self.sessions = sessions
        self.policy = FactQueuePolicy.model_validate(policy)
        self.vocabulary = FactVocabulary.model_validate(vocabulary)
        self.resolver_version = TypeAdapter(Version).validate_python(resolver_version, strict=True)
        self.vocabulary_hash = digest({k: sorted(v) for k, v in self.vocabulary.model_dump().items()})

    async def _anchor(self, session: AsyncSession, listing_id: UUID) -> AiFactCatalog:
        await session.execute(insert(AiFactCatalog).values(canonical_listing_id=listing_id, revision=0)
                              .on_conflict_do_nothing(index_elements=[AiFactCatalog.canonical_listing_id]))
        return (await session.execute(select(AiFactCatalog).where(
            AiFactCatalog.canonical_listing_id == listing_id).with_for_update())).scalar_one()

    async def _authority(self, session: AsyncSession, listing_id: UUID):
        listing = (await session.execute(select(Listing.id, Listing.status, Listing.deleted_at)
                   .where(Listing.id == listing_id).with_for_update())).first()
        known = select(AiFactSource.source_record_id).where(AiFactSource.canonical_listing_id == listing_id)
        # Coarse CAS token only. PostgreSQL returns the digest, not payload/URL/
        # identity text. This is distinct from sanitized extraction input hash.
        snapshot = source_snapshot_hash().label("snapshot_hash")
        rows = (await session.execute(select(
            ExternalListingSource.id, ExternalListingSource.canonical_listing_id,
            ExternalListingSource.fingerprint, ExternalListingSource.current_status,
            ExternalListingSource.last_success_at, ExternalListingSource.content_updated_at, snapshot,
        ).where(or_(ExternalListingSource.canonical_listing_id == listing_id, ExternalListingSource.id.in_(known)))
            .order_by(ExternalListingSource.id).limit(129).with_for_update())).all()
        if len(rows) > 128:
            raise ValueError("canonical source bound exceeded")
        visible = listing is not None and listing.status == "published" and listing.deleted_at is None
        return visible, {row.id: row for row in rows}

    @staticmethod
    def _receipt(job: AiFactJob) -> FactJobReceipt:
        return FactJobReceipt.model_validate({"job_id": job.id, "status": job.status,
                                              "result_revision": job.result_revision})

    @staticmethod
    def _identity(job: AiFactJob, claim: FactJobClaim) -> bool:
        return all(getattr(job, field) == getattr(claim, field) for field in (
            "source_record_id", "canonical_listing_id", "generation", "content_hash", "schema_version",
            "taxonomy_version", "extractor_version", "snapshot_hash", "fence",
        ))

    async def _guard(self, session: AsyncSession, job: AiFactJob, claim: FactJobClaim) -> None:
        if not self._identity(job, claim) or job.status != "running" or job.lease_until is None or (
            job.lease_until <= await _now(session)
        ):
            raise StaleFactWorker("fact job lease/fence is no longer current")

    async def _enqueue(self, session: AsyncSession, source: AiFactSource) -> UUID | None:
        if source.source_status != "active":
            return None
        key = (AiFactJob.source_record_id == source.source_record_id, AiFactJob.generation == source.generation)
        old = await session.scalar(select(AiFactJob.id).where(*key))
        if old is not None:
            return old
        job = AiFactJob(id=uuid4(), source_record_id=source.source_record_id,
                        canonical_listing_id=source.canonical_listing_id, generation=source.generation,
                        content_hash=source.content_hash, schema_version=source.schema_version,
                        snapshot_hash=source.snapshot_hash,
                        taxonomy_version=source.taxonomy_version, extractor_version=source.extractor_version,
                        status="pending", fence=0, attempts=0, available_at=await _now(session))
        session.add(job)
        await session.flush()
        return job.id

    async def observe(self, item: SourceInput) -> UUID | None:
        item = SourceInput.model_validate(item)
        async with self.sessions() as session, session.begin():
            anchor = await self._anchor(session, item.canonical_listing_id)
            visible, authority = await self._authority(session, item.canonical_listing_id)
            current = authority.get(item.source_record_id)
            if current is None or current.canonical_listing_id != item.canonical_listing_id:
                raise SourceIdentityConflict("source does not belong to canonical listing")
            if current.snapshot_hash != item.snapshot_hash:
                raise SourceIdentityConflict("source snapshot changed before observe")
            source = await session.get(AiFactSource, item.source_record_id, with_for_update=True)
            if source is not None and source.canonical_listing_id != item.canonical_listing_id:
                raise SourceIdentityConflict("canonical remap requires separate reviewed reconciliation")
            status = _status(current.current_status)
            desired = item.model_dump(exclude={"source_record_id", "canonical_listing_id"}) | {
                "source_fingerprint": current.fingerprint, "snapshot_hash": current.snapshot_hash, "source_status": status,
            }
            changed = source is None or any(getattr(source, k) != v for k, v in desired.items())
            if source is None:
                source = AiFactSource(source_record_id=item.source_record_id,
                                      canonical_listing_id=item.canonical_listing_id, generation=1, **desired)
                session.add(source)
            elif changed:
                source.generation += 1
                source.batch_id = None
                for key, value in desired.items():
                    setattr(source, key, value)
            if changed:
                await session.execute(update(AiFactJob).where(
                    AiFactJob.source_record_id == item.source_record_id,
                    AiFactJob.status.in_(["pending", "running"]),
                ).values(status="superseded", lease_until=None))
            await session.flush()
            job_id = await self._enqueue(session, source)
            await self._publish(session, anchor, visible, authority)
            return job_id

    async def claim(self) -> FactJobClaim | None:
        async with self.sessions() as session, session.begin():
            now = await _now(session)
            job = await session.scalar(select(AiFactJob).where(or_(
                and_(AiFactJob.status == "pending", AiFactJob.available_at <= now),
                and_(AiFactJob.status == "running", AiFactJob.lease_until <= now),
            )).order_by(AiFactJob.available_at, AiFactJob.id).limit(1).with_for_update(skip_locked=True))
            if job is None:
                return None
            source = await session.get(AiFactSource, job.source_record_id)
            if source is None or source.generation != job.generation or source.source_status != "active":
                job.status, job.lease_until = "superseded", None
                return None
            if job.attempts >= self.policy.max_attempts:
                job.status, job.lease_until, job.failure_code = "failed", None, "ATTEMPTS_EXHAUSTED"
                return None
            job.status, job.fence, job.attempts = "running", job.fence + 1, job.attempts + 1
            job.lease_until = await _now(session) + timedelta(seconds=self.policy.lease_seconds)
            job.failure_code = None
            return FactJobClaim.model_validate({
                **{field: getattr(job, field) for field in SourceInput.model_fields},
                "job_id": job.id, "generation": job.generation, "fence": job.fence, "lease_until": job.lease_until,
            })

    async def fail(self, claim: FactJobClaim, *, retryable: bool,
                   code: Literal["EXTRACTOR_FAILED", "INVALID_RESULT"]) -> FactJobReceipt:
        async with self.sessions() as session, session.begin():
            job = await session.get(AiFactJob, claim.job_id, with_for_update=True)
            if job is None:
                raise StaleFactWorker("unknown fact job")
            await self._guard(session, job, claim)
            job.status = "pending" if retryable and job.attempts < self.policy.max_attempts else "failed"
            job.lease_until, job.failure_code = None, code
            job.available_at = await _now(session) + timedelta(seconds=self.policy.retry_delay_seconds)
            await session.flush()
            return self._receipt(job)

    async def complete(self, claim: FactJobClaim, batch: FactBatch,
                       sanitized_fields: dict[str, str]) -> FactJobReceipt:
        # Snapshot caller-owned containers before the first await. No raw input
        # survives this call; only bounded validated evidence is persisted.
        batch = FactBatch.model_validate(batch.model_dump())
        fields = dict(sanitized_fields)
        if len(fields) > 256 or any(type(k) is not str or type(v) is not str for k, v in fields.items()) or (
            sum(len(k.encode()) + len(v.encode()) for k, v in fields.items()) > 1_048_576
        ):
            raise ValueError("sanitized evidence mapping exceeds supported bound")
        batch.validate_evidence_against(fields)
        for fact in batch.facts:
            self.vocabulary.validate_fact(fact)
        expected = {"source_record_id": claim.source_record_id, "canonical_listing_id": claim.canonical_listing_id,
                    "source_generation": claim.generation, "content_hash": claim.content_hash,
                    "schema_version": claim.schema_version, "taxonomy_version": claim.taxonomy_version,
                    "extractor_version": claim.extractor_version}
        if any(getattr(batch, k) != v for k, v in expected.items()) or batch.source_status != "active":
            raise ValueError("batch does not belong to claimed input")
        result_hash = digest(sorted([f.model_dump(mode="json", exclude={"fact_id"}) for f in batch.facts],
                                    key=lambda f: digest(f)))
        async with self.sessions() as session, session.begin():
            anchor = await self._anchor(session, claim.canonical_listing_id)
            visible, authority = await self._authority(session, claim.canonical_listing_id)
            source = await session.get(AiFactSource, claim.source_record_id, with_for_update=True)
            job = await session.get(AiFactJob, claim.job_id, with_for_update=True)
            if job is None or not self._identity(job, claim):
                raise StaleFactWorker("fact job identity/fence mismatch")
            if job.status == "succeeded":
                if job.result_hash != result_hash:
                    raise FactResultConflict("terminal fact result differs")
                return self._receipt(job)
            if job.status == "superseded":
                return self._receipt(job)
            await self._guard(session, job, claim)
            lease_deadline = job.lease_until
            current = authority.get(claim.source_record_id)
            if not visible or source is None or current is None or (
                source.generation != claim.generation or source.content_hash != claim.content_hash
                or source.canonical_listing_id != claim.canonical_listing_id
                or current.canonical_listing_id != claim.canonical_listing_id
                or current.fingerprint != source.source_fingerprint or current.snapshot_hash != source.snapshot_hash
                or _status(current.current_status) != "active"
            ):
                job.status, job.lease_until = "superseded", None
                await self._publish(session, anchor, visible, authority)
                return self._receipt(job)
            now = await _now(session)
            stored = batch.model_dump()
            stored.update(batch_id=job.id, observed_at=now, last_successful_check_at=current.last_success_at,
                          last_content_change_at=current.content_updated_at, last_check_error_at=None)
            for fact in stored["facts"]:
                fact["fact_id"] = uuid5(job.id, digest({k: v for k, v in fact.items() if k != "fact_id"}))
            # digest needs JSON UUID-free fact payload; all fact values are primitives.
            persisted = FactBatch.model_validate(stored)
            session.add(AiListingFactBatch(id=job.id, **persisted.model_dump(exclude={"batch_id", "facts"})))
            await session.flush()
            for fact in persisted.facts:
                session.add(AiListingFact(id=fact.fact_id, batch_id=job.id, scope_hash=fact.scope_hash,
                                         **fact.model_dump(mode="json", exclude={"fact_id"})))
            source.batch_id = job.id
            await session.flush()
            revision = await self._publish(session, anchor, visible, authority)
            job.status, job.lease_until = "succeeded", None
            job.result_revision, job.result_hash = revision, result_hash
            await session.flush()
            if lease_deadline is None or await _now(session) >= lease_deadline:
                raise StaleFactWorker("lease expired during publication")
            return self._receipt(job)

    async def _load_batch(self, session: AsyncSession, source: AiFactSource, budget: int) -> FactBatch | None:
        row = await session.get(AiListingFactBatch, source.batch_id) if source.batch_id is not None else None
        if row is None or row.source_record_id != source.source_record_id or (
            row.canonical_listing_id != source.canonical_listing_id or row.source_generation != source.generation
            or row.content_hash != source.content_hash or row.extractor_version != source.extractor_version
            or row.schema_version != source.schema_version or row.taxonomy_version != source.taxonomy_version
        ):
            return None
        facts = (await session.scalars(select(AiListingFact).where(AiListingFact.batch_id == row.id)
                                      .limit(min(129, budget + 1)))).all()
        if len(facts) > budget:
            return None
        data = {column.name: getattr(row, column.name) for column in row.__table__.columns if column.name != "id"}
        data["batch_id"] = row.id
        data["facts"] = [{"fact_id": f.id, "key": f.key, "status": f.status, "typed_value": f.typed_value,
                          "qualifiers": f.qualifiers, "origin": f.origin, "evidence": f.evidence} for f in facts]
        try:
            batch = FactBatch.model_validate(data)
            for fact in batch.facts:
                self.vocabulary.validate_fact(fact)
            return batch
        except (ValidationError, ValueError):
            # A corrupt/unsupported current batch is not a verified match.
            # The pending barrier invalidates the old projection; repair needs
            # a reviewed fresh extraction input/version, not a broad fallback.
            return None

    async def _publish(self, session: AsyncSession, anchor: AiFactCatalog, visible: bool, authority) -> int:
        sources = (await session.scalars(select(AiFactSource).where(
            AiFactSource.canonical_listing_id == anchor.canonical_listing_id)
            .order_by(AiFactSource.source_record_id).limit(129))).all()
        if len(sources) > 128:
            raise ValueError("canonical source bound exceeded")
        by_id = {s.source_record_id: s for s in sources}
        inputs: list[dict] = []
        batches: list[FactBatch] = []
        pending = False
        for source_id in sorted(set(by_id) | set(authority), key=str):
            source, current = by_id.get(source_id), authority.get(source_id)
            active = current is not None and current.canonical_listing_id == anchor.canonical_listing_id and (
                _status(current.current_status) == "active"
            )
            ready = source is not None and active and source.source_status == "active" and (
                current.fingerprint == source.source_fingerprint and current.snapshot_hash == source.snapshot_hash
            )
            remaining = MAX_SOURCE_OBSERVATIONS - sum(len(b.facts) for b in batches)
            batch = await self._load_batch(session, source, remaining) if ready and source is not None else None
            if active and batch is None:
                pending = True
            if batch is not None:
                batches.append(batch)
            inputs.append({"source": str(source_id), "active": active,
                           "fingerprint": current.fingerprint if current is not None else None,
                           "snapshot": current.snapshot_hash if current is not None else None,
                           "canonical": str(current.canonical_listing_id) if current is not None else None,
                           "generation": source.generation if source is not None else None,
                           "hash": source.content_hash if source is not None else None,
                           "batch": str(source.batch_id) if source is not None and source.batch_id is not None else None,
                           "schema": source.schema_version if source is not None else None,
                           "taxonomy": source.taxonomy_version if source is not None else None,
                           "extractor": source.extractor_version if source is not None else None})
        input_hash = digest({"inputs": inputs, "visible": visible, "pending": pending,
                             "resolver": self.resolver_version, "vocabulary": self.vocabulary_hash})
        old = await session.get(AiListingSearchFeatures, anchor.canonical_listing_id)
        if old is not None and old.input_hash == input_hash and old.resolver_version == self.resolver_version:
            return old.feature_revision
        revision = max(anchor.revision, old.feature_revision if old is not None else 0) + 1
        projection = resolve_sources(canonical_listing_id=anchor.canonical_listing_id,
                                     batches=batches if visible and not pending else [], input_hash=input_hash,
                                     feature_revision=revision, resolver_version=self.resolver_version,
                                     computed_at=await _now(session))
        values = projection.model_dump(exclude={"features"}) | {
            "features": projection.model_dump(mode="json")["features"],
        }
        await session.execute(insert(AiListingSearchFeatures).values(**values).on_conflict_do_update(
            index_elements=[AiListingSearchFeatures.canonical_listing_id],
            set_={k: v for k, v in values.items() if k != "canonical_listing_id"},
        ))
        anchor.revision = revision
        session.add(AiFactRematchEvent(id=uuid4(), canonical_listing_id=anchor.canonical_listing_id,
                                      feature_revision=revision, input_hash=input_hash, created_at=await _now(session)))
        await session.flush()
        return revision

    async def reconcile_listing(self, listing_id: UUID) -> int:
        async with self.sessions() as session, session.begin():
            anchor = await self._anchor(session, listing_id)
            visible, authority = await self._authority(session, listing_id)
            sources = (await session.scalars(select(AiFactSource).where(
                AiFactSource.canonical_listing_id == listing_id).limit(129))).all()
            if len(sources) > 128:
                raise ValueError("canonical source bound exceeded")
            for source in sources:
                current = authority.get(source.source_record_id)
                if current is not None and current.canonical_listing_id == listing_id and (
                    current.fingerprint == source.source_fingerprint and _status(current.current_status) == "active"
                    and current.snapshot_hash == source.snapshot_hash
                    and source.source_status == "active"
                ):
                    await self._enqueue(session, source)
                else:
                    await session.execute(update(AiFactJob).where(
                        AiFactJob.source_record_id == source.source_record_id,
                        AiFactJob.status.in_(["pending", "running"]),
                    ).values(status="superseded", lease_until=None))
            return await self._publish(session, anchor, visible, authority)

    async def reconcile(self, *, limit: int, after: UUID | None = None) -> list[UUID]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("bounded reconcile limit required")
        async with self.sessions() as session:
            query = select(AiFactCatalog.canonical_listing_id).order_by(AiFactCatalog.canonical_listing_id).limit(limit)
            if after is not None:
                query = query.where(AiFactCatalog.canonical_listing_id > after)
            ids = (await session.scalars(query)).all()
        for listing_id in ids:
            await self.reconcile_listing(listing_id)
        return list(ids)
