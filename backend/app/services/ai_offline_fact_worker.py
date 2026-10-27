"""Explicit one-job offline runner. No daemon, scheduler, provider or default builder."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.exc import SQLAlchemyError

from ..repositories.ai_fact_pipeline import FactPipeline
from ..repositories.ai_fact_snapshots import CapturedParserSnapshot, FactSnapshotReader
from ..schemas.ai_fact_bridge import BridgeMapping, BridgeRejected, ParserEvidencePacket
from ..schemas.ai_fact_pipeline import FactJobClaim, FactJobReceipt, StaleFactWorker
from ..schemas.ai_listing_facts import Contract, Version
from .ai_fact_bridge import prepare_captured_source


class OfflineFactRun(Contract):
    outcome: Literal["no_claim", "succeeded", "retry_scheduled", "failed", "stale"]
    job_id: UUID | None
    receipt: FactJobReceipt | None
    failure_code: Literal["INVALID_RESULT", "EXTRACTOR_FAILED", "STALE_CLAIM"] | None


class OfflineFactStorageError(RuntimeError):
    """Storage outcome may be unknown. Never retry inference or mark success here."""


class OfflineFactJobRunner:
    def __init__(self, pipeline: FactPipeline, reader: FactSnapshotReader, *,
                 builder: Callable[[CapturedParserSnapshot], ParserEvidencePacket], mapping: BridgeMapping,
                 extractor_version: Version, retry_builder_failures: bool):
        if type(retry_builder_failures) is not bool or not callable(builder):
            raise ValueError("explicit offline builder/retry policy required")
        self.pipeline, self.reader, self.builder = pipeline, reader, builder
        self.mapping = BridgeMapping.model_validate(mapping)
        self.extractor_version = TypeAdapter(Version).validate_python(extractor_version, strict=True)
        self.retry_builder_failures = retry_builder_failures

    @staticmethod
    def _stale(claim: FactJobClaim, receipt: FactJobReceipt | None = None) -> OfflineFactRun:
        return OfflineFactRun(outcome="stale", job_id=claim.job_id, receipt=receipt, failure_code="STALE_CLAIM")

    async def _reject(self, claim: FactJobClaim, *, code: Literal["INVALID_RESULT", "EXTRACTOR_FAILED"],
                      retryable: bool) -> OfflineFactRun:
        # Invalidate a changed/retired source before attempting a guarded failure.
        # Reconcile may already supersede this claim; never overwrite its successor.
        await self.pipeline.reconcile_listing(claim.canonical_listing_id)
        try:
            receipt = await self.pipeline.fail(claim, retryable=retryable, code=code)
        except StaleFactWorker:
            return self._stale(claim)
        return OfflineFactRun(outcome="retry_scheduled" if receipt.status == "pending" else "failed",
                              job_id=claim.job_id, receipt=receipt, failure_code=code)

    async def run_once(self) -> OfflineFactRun:
        """Caller explicitly invokes one bounded attempt. no_claim is not global queue exhaustion."""
        try:
            claim = await self.pipeline.claim(extractor_version=self.extractor_version)
            if claim is None:
                return OfflineFactRun(outcome="no_claim", job_id=None, receipt=None, failure_code=None)
            try:
                ready = await prepare_captured_source(
                    self.reader, claim.source_record_id, builder=self.builder, mapping=self.mapping,
                    vocabulary=self.pipeline.vocabulary, extractor_version=self.extractor_version,
                )
                batch = ready.to_batch(claim, observed_at=datetime.now(UTC))
            except BridgeRejected as error:
                builder_failed = str(error) == "SANITIZED_BUILDER_REJECTED"
                return await self._reject(claim, code="EXTRACTOR_FAILED" if builder_failed else "INVALID_RESULT",
                                          retryable=builder_failed and self.retry_builder_failures)
            except ValueError:
                return await self._reject(claim, code="INVALID_RESULT", retryable=False)
            try:
                receipt = await self.pipeline.complete(claim, batch, ready.sanitized_fields)
            except StaleFactWorker:
                return self._stale(claim)
            except ValueError:
                return await self._reject(claim, code="INVALID_RESULT", retryable=False)
            if receipt.status != "succeeded":
                return self._stale(claim, receipt)
            return OfflineFactRun(outcome="succeeded", job_id=claim.job_id, receipt=receipt, failure_code=None)
        except SQLAlchemyError:
            # Capture/finalize/commit errors cannot be safely called success or
            # converted into a second inference. Leave the durable lease/state
            # for bounded queue recovery and redact SQL parameters/payloads.
            raise OfflineFactStorageError("OFFLINE_FACT_STORAGE_UNAVAILABLE") from None
