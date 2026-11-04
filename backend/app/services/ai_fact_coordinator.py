"""Explicit finite offline ticks over stored sources; no network or app startup hook.

A supervisor owns scheduling, exclusivity and durable checkpoint/receipt storage.
Only a successful tick advances its cursors. Replaying an interrupted tick uses
the existing snapshot CAS, durable job leases/fences and idempotent publication.
Content refresh is reported, never simulated by recapturing stored payloads.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from ..models import ExternalListingSource
from ..repositories.ai_fact_pipeline import FactPipeline
from ..repositories.ai_fact_snapshots import CapturedParserSnapshot, FactSnapshotReader
from ..repositories.ai_query_proofs import QueryProofs
from ..schemas.ai_fact_bridge import BridgeMapping, BridgeRejected, ParserEvidencePacket, checked_source_name
from ..schemas.ai_fact_pipeline import SourceIdentityConflict
from ..schemas.ai_listing_facts import Version
from .ai_fact_bridge import prepare_captured_source
from .ai_offline_fact_worker import OfflineFactJobRunner


def _bound(value: int, maximum: int) -> None:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError("explicit bounded coordinator policy required")


@dataclass(frozen=True)
class SourceFactPolicy:
    source_name: str
    mapping: BridgeMapping = field(repr=False)
    builder: Callable[[CapturedParserSnapshot], ParserEvidencePacket] = field(repr=False)
    extractor_version: Version
    content_max_age_seconds: int
    max_jobs: int
    retry_builder_failures: bool


@dataclass(frozen=True)
class FactCoordinatorCursor:
    source_after: UUID | None = None
    reconcile_after: UUID | None = None


@dataclass(frozen=True)
class FactCoordinatorTick:
    cursor: FactCoordinatorCursor
    sources_scanned: int
    observed: int
    rejected: int
    content_refresh_due: tuple[UUID, ...]
    job_outcomes: tuple[str, ...]
    reconciled: int
    proofs_prepared: int
    proofs_deferred: int


class FactCoordinatorUnavailable(RuntimeError):
    """No checkpoint acknowledgement; supervisor must retry the previous cursor."""


class OfflineFactCoordinator:
    def __init__(self, pipeline: FactPipeline, *, sources: tuple[SourceFactPolicy, ...],
                 max_sources: int, max_reconcile: int, max_payload_bytes: int):
        _bound(len(sources), 16)
        _bound(max_sources, 100)
        _bound(max_reconcile, 100)
        if pipeline.operating_policy is None:
            raise ValueError("explicit operating freshness policy required")
        self.pipeline = pipeline
        self.reader = FactSnapshotReader(pipeline.sessions, max_payload_bytes=max_payload_bytes)
        self.proofs = QueryProofs(pipeline)
        self.max_sources, self.max_reconcile = max_sources, max_reconcile
        self.sources: dict[str, SourceFactPolicy] = {}
        self.workers: list[OfflineFactJobRunner] = []
        for policy in sources:
            checked_source_name(policy.source_name)
            if policy.source_name in self.sources:
                raise ValueError("unique explicit source names required")
            _bound(policy.content_max_age_seconds, min(pipeline.operating_policy.price_max_age_seconds,
                                                       pipeline.operating_policy.policy_max_age_seconds))
            _bound(policy.max_jobs, 100)
            # Own the mapping snapshot: caller mutations cannot switch authority mid-tick.
            mapping = BridgeMapping.model_validate(policy.mapping.model_dump()).model_copy(deep=True)
            owned = SourceFactPolicy(policy.source_name, mapping, policy.builder, policy.extractor_version,
                                    policy.content_max_age_seconds, policy.max_jobs, policy.retry_builder_failures)
            self.sources[policy.source_name] = owned
            self.workers.append(OfflineFactJobRunner(pipeline, self.reader, builder=owned.builder,
                mapping=mapping, extractor_version=owned.extractor_version,
                retry_builder_failures=owned.retry_builder_failures, source_name=owned.source_name))
        _bound(sum(p.max_jobs for p in self.sources.values()), 100)

    async def run_once(self, cursor: FactCoordinatorCursor) -> FactCoordinatorTick:
        """One bounded tick; cancellation propagates, errors disclose no source payload.

        A full page preserves its last key; a short page resets for the next
        sweep. New/changed keys behind a cursor are revisited on that sweep.
        no_claim ends only this worker's attempts, never signals queue exhaustion.
        """
        try:
            return await self._tick(cursor)
        except Exception:  # noqa: BLE001 -- supervisor boundary must redact builder/storage payloads.
            # Includes unknown commit outcomes. Do not run a second attempt here.
            raise FactCoordinatorUnavailable("OFFLINE_FACT_COORDINATOR_UNAVAILABLE") from None

    async def _tick(self, cursor: FactCoordinatorCursor) -> FactCoordinatorTick:
        async with self.pipeline.sessions() as session:
            query = select(ExternalListingSource.id, ExternalListingSource.source_name,
                ExternalListingSource.canonical_listing_id, ExternalListingSource.last_success_at,
                ExternalListingSource.current_status).where(
                    ExternalListingSource.source_name.in_(self.sources)).order_by(ExternalListingSource.id).limit(self.max_sources)
            if cursor.source_after is not None:
                query = query.where(ExternalListingSource.id > cursor.source_after)
            rows = (await session.execute(query)).all()
        observed = rejected = 0
        refresh_due: list[UUID] = []
        touched: set[UUID] = set()
        now = datetime.now(UTC)
        for row in rows:
            policy = self.sources[row.source_name]
            touched.add(row.canonical_listing_id)
            if row.current_status != "active":
                continue
            if row.last_success_at is None or row.last_success_at > now or (
                now - row.last_success_at > timedelta(seconds=policy.content_max_age_seconds)
            ):
                refresh_due.append(row.id)
            try:
                ready = await prepare_captured_source(self.reader, row.id, builder=policy.builder,
                    mapping=policy.mapping, vocabulary=self.pipeline.vocabulary, extractor_version=policy.extractor_version,
                    source_name=policy.source_name)
                await self.pipeline.observe(ready.source)
                observed += 1
            except (BridgeRejected, SourceIdentityConflict):
                # Hidden/deleted/racing/remapped sources are not successful captures.
                # Reconcile below invalidates their old projection; next sweep retries.
                rejected += 1
        outcomes: list[str] = []
        for policy, worker in zip(self.sources.values(), self.workers, strict=True):
            for _ in range(policy.max_jobs):
                outcome = (await worker.run_once()).outcome
                outcomes.append(outcome)
                if outcome == "no_claim":
                    break
        reconciled = await self.pipeline.reconcile(limit=self.max_reconcile, after=cursor.reconcile_after)
        # Repair the selected source page as well, even when outside the catalog page.
        for listing_id in sorted(touched - set(reconciled)):
            await self.pipeline.reconcile_listing(listing_id)
        prepared = deferred = 0
        for listing_id in sorted(touched | set(reconciled)):
            if await self.proofs.prepare(listing_id):
                prepared += 1
            else:
                deferred += 1
        return FactCoordinatorTick(
            cursor=FactCoordinatorCursor(rows[-1].id if len(rows) == self.max_sources else None,
                reconciled[-1] if len(reconciled) == self.max_reconcile else None),
            sources_scanned=len(rows), observed=observed, rejected=rejected,
            content_refresh_due=tuple(refresh_due), job_outcomes=tuple(outcomes),
            reconciled=len(touched | set(reconciled)), proofs_prepared=prepared, proofs_deferred=deferred)
