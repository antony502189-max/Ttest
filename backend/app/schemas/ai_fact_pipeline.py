"""Internal queue receipts and explicit offline configuration. No provider settings."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from .ai_listing_facts import Contract, Digest, Version


class FactQueuePolicy(Contract):
    lease_seconds: Annotated[int, Field(ge=1, le=3600)]
    max_attempts: Annotated[int, Field(ge=1, le=10)]
    retry_delay_seconds: Annotated[int, Field(ge=1, le=3600)]


class SourceInput(Contract):
    source_record_id: UUID
    canonical_listing_id: UUID
    content_hash: Digest
    snapshot_hash: Digest
    schema_version: Literal["ai-facts.v1"]
    taxonomy_version: Literal["ai-search.v1"]
    extractor_version: Version


class FactJobClaim(SourceInput):
    job_id: UUID
    generation: Annotated[int, Field(ge=1)]
    fence: Annotated[int, Field(ge=1)]
    lease_until: datetime


class FactJobReceipt(Contract):
    job_id: UUID
    status: Literal["pending", "running", "succeeded", "failed", "superseded"]
    result_revision: int | None


class StaleFactWorker(RuntimeError):
    pass


class SourceIdentityConflict(RuntimeError):
    pass


class FactResultConflict(RuntimeError):
    pass
