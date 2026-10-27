"""Internal server contracts. HTTP ownership and result visibility belong to AI-09."""

import hashlib
import json
from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictContract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class QuotaSubject(StrictContract):
    kind: Literal["guest", "auth"]
    id: UUID


class QuotaOperation(StrictContract):
    idempotency_key: UUID
    channel: Literal["text", "voice"]
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    session_id: UUID
    expected_session_version: int = Field(ge=0, le=2_147_483_647)
    contract: Literal["ai-search.operation.v1"] = "ai-search.operation.v1"

    def fingerprint(self) -> str:
        # Exact UTF-8 text or final audio bytes must be hashed by the server.
        # Key is an identity, not body content. Channel/session/version are bound.
        body = self.model_dump(mode="json", exclude={"idempotency_key"})
        return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ResultReceipt(StrictContract):
    # Reference to future durable validated response, never arbitrary JSON/PII.
    result_ref: UUID
    count: int = Field(ge=0, le=2_147_483_647)


class LeasePolicy(StrictContract):
    # Explicit internal configuration; these are not approved production budgets.
    reservation_seconds: int = Field(ge=1, le=300)
    running_seconds: int = Field(ge=1, le=300)
    recovery_grace_seconds: int = Field(ge=0, le=300)


class FailureCode(StrEnum):
    ASR_FAILURE = "ASR_FAILURE"
    LLM_FAILURE = "LLM_FAILURE"
    BACKEND_FAILURE = "BACKEND_FAILURE"
    ABUSE_GATE_UNAVAILABLE = "ABUSE_GATE_UNAVAILABLE"
    ATTEMPT_LIMIT = "ATTEMPT_LIMIT"
    SESSION_VERSION_CONFLICT = "SESSION_VERSION_CONFLICT"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_STATE_INVALID = "SESSION_STATE_INVALID"
    LEASE_EXPIRED = "LEASE_EXPIRED"


class OperationState(StrictContract):
    idempotency_key: UUID
    status: Literal["reserved", "running", "succeeded", "failed"]
    madrid_date: date
    fence: int
    lease_until: datetime
    recover_after: datetime
    receipt: ResultReceipt | None
    failure_code: str | None
    used: int
    reserved: int
    limit: int
    remaining: int
    reset_at: datetime


class Reservation(StrictContract):
    action: Literal["created", "inflight", "replay"]
    operation: OperationState


class DailyQuotaView(StrictContract):
    madrid_date: date
    reset_at: datetime
    limit: int = Field(ge=0, le=200)
    used: int = Field(ge=0)
    reserved: int = Field(ge=0)
    remaining: int = Field(ge=0)
