"""Finite source-only detail rehearsal; MockTransport and owned synthetic schemas only.

No legacy importer, discovery, images, notifications, scheduler or automatic ACK.
Successful source CAS, projection barrier and operation receipt commit together.
GETs can repeat after interruption before commit: durable HTTP budgets/leases and
real source/canonical import policy remain prerequisites for any live consumer.
"""

import asyncio
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from time import monotonic
from typing import Any, Literal
from uuid import UUID, uuid4

import httpx
from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    Text,
    cast,
    func,
    insert,
    literal,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models import ExternalListingSource, Listing
from app.repositories.ai_card_values import source_owner_eligible
from app.repositories.ai_fact_quality import source_check_health_predicate
from app.repositories.ai_fact_snapshots import CapturedParserSnapshot, source_snapshot_hash
from app.schemas.ai_fact_bridge import checked_source_name
from app.schemas.ai_listing_facts import Contract, digest
from app.services.ai_fact_bridge import bridge_packet
from lab.ai_fact_supervisor import SyntheticFactSupervisor, bounded

OPERATIONS = Table("synthetic_ai_detail_refresh_receipts", MetaData(),
    Column("operation", String(64), primary_key=True), Column("namespace", String(32), nullable=False),
    Column("source_id", PGUUID(as_uuid=True), nullable=False),
    Column("committed_at", DateTime(timezone=True), nullable=False))


class SyntheticRefreshUnavailable(RuntimeError):
    pass


class _Detail(Contract):
    schema_version: Literal["synthetic-detail.v1"]
    source_id: UUID
    canonical_listing_id: UUID
    source_name: str
    raw: dict[str, Any]
    normalized: dict[str, Any]
    price: str | None


@dataclass(frozen=True)
class SyntheticRefreshPolicy:
    source_name: str
    host: str
    max_requests: int
    max_payload_bytes: int
    timeout_seconds: int
    max_operations: int

    def __post_init__(self) -> None:
        checked_source_name(self.source_name)
        if not self.source_name.startswith("synthetic") or not re.fullmatch(r"[a-z0-9-]+\.invalid", self.host):
            raise ValueError("explicit synthetic source and invalid-domain host required")
        bounded(self.max_requests, 100)
        bounded(self.max_payload_bytes, 131_072)
        bounded(self.timeout_seconds, 30)
        bounded(self.max_operations, 1000)


@dataclass(frozen=True)
class RefreshReceiptResult:
    outcomes: tuple[str, ...]
    # Refresh completion alone must never acknowledge rejected/deferred signals.
    acknowledged: bool = False


@dataclass(frozen=True)
class _Target:
    captured: CapturedParserSnapshot = field(repr=False)
    row: Any = field(repr=False)


class SyntheticDetailRefresh:
    """Trusted dynamic mock behavior, immutable policy/cohort/catalog binding.

    mock_bundle_sha256 is a caller declaration, not a hash of the active Python
    callback or its closure/response bytes. Exact MockTransport instances and
    handlers may be replaced to model faults/recovery. Every response still
    passes identity/packet/size checks and source CAS; real transports may not.
    """

    def __init__(self, supervisor: SyntheticFactSupervisor, *, policy: SyntheticRefreshPolicy,
                 cohort: tuple[tuple[UUID, UUID], ...], transport: httpx.MockTransport,
                 mock_bundle_sha256: str):
        supervisor._binding()
        if type(transport) is not httpx.MockTransport or not re.fullmatch(r"[0-9a-f]{64}", mock_bundle_sha256):
            raise ValueError("explicit trusted MockTransport and declared bundle label required")
        if (type(cohort) is not tuple or not 1 <= len(cohort) <= 100
                or any(type(pair) is not tuple or len(pair) != 2 or any(not isinstance(v, UUID) for v in pair) for pair in cohort)
                or len({pair[0] for pair in cohort}) != len(cohort)):
            raise ValueError("explicit bounded source/canonical cohort required")
        if policy.source_name not in supervisor.coordinator.sources:
            raise ValueError("source policy must belong to supervisor configuration")
        self.supervisor, self.policy, self.transport = supervisor, policy, transport
        self.cohort = dict(cohort)
        self.sessions = supervisor.coordinator.pipeline.sessions
        self.mock_bundle_sha256 = mock_bundle_sha256
        self.binding = self._configuration()

    def _configuration(self) -> str:
        if (type(self.transport) is not httpx.MockTransport
                or self.sessions is not self.supervisor.coordinator.pipeline.sessions):
            raise ValueError("synthetic refresh configuration changed")
        return digest({"supervisor": self.supervisor.journal.binding, "policy": asdict(self.policy),
            "cohort": sorted((str(a), str(b)) for a, b in self.cohort.items()), "mock_bundle": self.mock_bundle_sha256})

    async def _schema(self) -> None:
        self.supervisor._binding()  # Revalidate disposable loopback DB before opening any connection.
        if self._configuration() != self.binding:
            raise ValueError("synthetic refresh configuration changed")
        async with self.sessions() as session:
            schema = await session.scalar(select(func.current_schema()))
        if (not isinstance(schema, str) or not re.fullmatch(r"ai_facts_[0-9a-f]{32}", schema) or
                hashlib.sha256(schema.encode()).hexdigest() != self.supervisor.catalog_identity_sha256):
            raise ValueError("owned synthetic schema binding required")

    async def initialize(self) -> None:
        """Explicit setup, never import/startup DDL; no changes to production migrations."""
        await self._schema()
        with self.supervisor.journal._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS synthetic_refresh_binding "
                       "(id INTEGER PRIMARY KEY CHECK(id=1), binding TEXT NOT NULL, namespace TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO synthetic_refresh_binding VALUES(1,?,?)", (self.binding, uuid4().hex))
            if db.execute("SELECT binding FROM synthetic_refresh_binding").fetchone()[0] != self.binding:
                raise ValueError("synthetic refresh configuration binding mismatch")
        async with self.sessions() as session, session.begin():
            await (await session.connection()).run_sync(lambda connection: OPERATIONS.create(connection, checkfirst=True))

    def _namespace(self) -> str:
        self.supervisor._binding()
        with self.supervisor.journal._transaction() as db:
            row = db.execute("SELECT binding,namespace FROM synthetic_refresh_binding WHERE id=1").fetchone()
            if row is None or row["binding"] != self.binding or self._configuration() != self.binding:
                raise ValueError("synthetic refresh configuration binding mismatch")
            return row["namespace"]

    async def _target(self, source_id: UUID) -> _Target:
        captured = await self.supervisor.coordinator.reader.capture(source_id)
        columns = (ExternalListingSource.id, ExternalListingSource.canonical_listing_id,
            ExternalListingSource.source_name, ExternalListingSource.source_url, ExternalListingSource.fingerprint,
            ExternalListingSource.last_success_at, ExternalListingSource.content_updated_at,
            ExternalListingSource.last_checked_at, ExternalListingSource.last_state_check_at,
            ExternalListingSource.last_state_check_result, source_snapshot_hash().label("snapshot_hash"),
            func.statement_timestamp().label("checked_at"),
            source_check_health_predicate(ExternalListingSource.__table__, func.statement_timestamp()).label("healthy"))
        async with self.sessions() as session:
            row = (await session.execute(select(*columns).join(Listing,
                Listing.id == ExternalListingSource.canonical_listing_id).where(ExternalListingSource.id == source_id,
                ExternalListingSource.current_status == "active", Listing.status == "published",
                Listing.deleted_at.is_(None), source_owner_eligible(),
                func.octet_length(ExternalListingSource.source_url) <= 2048))).first()
        if (row is None or row.canonical_listing_id != self.cohort[source_id]
                or row.canonical_listing_id != captured.reference.canonical_listing_id
                or row.snapshot_hash != captured.reference.snapshot_hash or row.source_name != self.policy.source_name):
            raise ValueError("synthetic refresh source binding changed")
        url = httpx.URL(row.source_url)
        if (url.scheme != "https" or url.host != self.policy.host or url.port not in {None, 443}
                or url.username or url.password or url.query or url.fragment):
            raise ValueError("synthetic refresh URL refused")
        return _Target(captured, row)

    async def _fetch(self, target: _Target) -> tuple[_Detail | None, str]:
        started = monotonic()
        try:
            self._namespace()  # Recheck after prior async work, before constructing any client.
            async with asyncio.timeout(self.policy.timeout_seconds), httpx.AsyncClient(
                transport=self.transport, trust_env=False, follow_redirects=False,
                timeout=self.policy.timeout_seconds) as client, client.stream("GET", target.row.source_url) as response:
                if response.status_code != 200:
                    return None, "blocked" if response.status_code in {403, 429} else "temporary_error"
                if (response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json"
                        or response.headers.get("content-encoding", "identity").strip().lower() != "identity"):
                    return None, "unknown"
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > self.policy.max_payload_bytes:
                        return None, "unknown"
                    data.extend(chunk)
            self._namespace()
            detail = _Detail.model_validate_json(bytes(data))
            if ((detail.source_id, detail.canonical_listing_id, detail.source_name) != (
                    target.row.id, target.row.canonical_listing_id, target.row.source_name)
                    or (detail.price is not None and len(detail.price) > 120)):
                return None, "unknown"
            candidate = CapturedParserSnapshot(target.captured.reference,
                json.dumps(detail.raw), json.dumps(detail.normalized), detail.price)
            source = self.supervisor.coordinator.sources[self.policy.source_name]
            bridge_packet(source.builder(candidate), candidate.reference, source.mapping,
                self.supervisor.coordinator.pipeline.vocabulary, extractor_version=source.extractor_version)
            if monotonic() - started >= self.policy.timeout_seconds:
                return None, "temporary_error"
            return detail, "active"
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 -- source/builder/HTTP payload must not escape.
            return None, "unknown"

    async def _write(self, target: _Target, operation: str, namespace: str,
                     detail: _Detail | None, state: str) -> str:
        pipeline = self.supervisor.coordinator.pipeline
        self._namespace()
        async with self.sessions() as session, session.begin():
            # Capacity must see commits made while waiting for the shared lock,
            # even if the caller's engine default is REPEATABLE READ.
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            # Match existing mutation order. Never hold these locks during HTTP/builder work.
            anchor = await pipeline._anchor(session, target.row.canonical_listing_id)
            visible, authority = await pipeline._authority(session, target.row.canonical_listing_id)
            if await session.scalar(select(OPERATIONS.c.operation).where(OPERATIONS.c.operation == operation)):
                return "already_applied"
            current = authority.get(target.row.id)
            checks = (await session.execute(select(ExternalListingSource.last_checked_at,
                ExternalListingSource.last_state_check_at, ExternalListingSource.last_state_check_result,
                ExternalListingSource.source_name).where(ExternalListingSource.id == target.row.id))).first()
            if (not visible or current is None or current.canonical_listing_id != target.row.canonical_listing_id
                    or current.current_status != "active" or current.snapshot_hash != target.row.snapshot_hash
                    or current.fingerprint != target.row.fingerprint or current.last_success_at != target.row.last_success_at
                    or current.content_updated_at != target.row.content_updated_at or checks is None
                    or tuple(checks) != (target.row.last_checked_at, target.row.last_state_check_at,
                                        target.row.last_state_check_result, target.row.source_name)):
                return "stale"
            now = await session.scalar(select(func.clock_timestamp()))
            values: dict[str, Any] = {"last_checked_at": now, "last_state_check_at": now, "last_state_check_result": state}
            if detail is None:
                await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == target.row.id).values(**values))
                self._namespace()
                return "failed"
            # JSONB::text adds whitespace; a small HTTP document can still
            # exceed the existing reader's exact stored snapshot byte bound.
            size = (func.octet_length(cast(literal(detail.raw, type_=JSONB), Text))
                + func.octet_length(cast(literal(detail.normalized, type_=JSONB), Text))
                + func.coalesce(func.octet_length(literal(detail.price, type_=Text)), 0))
            if int((await session.execute(select(size))).scalar_one()) > min(self.policy.max_payload_bytes,
                    self.supervisor.coordinator.reader.max_payload_bytes):
                values["last_state_check_result"] = "unknown"
                await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == target.row.id).values(**values))
                self._namespace()
                return "failed"
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended("
                                       "current_schema() || '/synthetic_ai_detail_refresh',0))"))
            if int(await session.scalar(select(func.count()).select_from(OPERATIONS)) or 0) >= self.policy.max_operations:
                return "capacity"
            # Python dict equality treats True==1/False==0. Compare locked
            # values with PostgreSQL JSONB semantics so type changes advance
            # fingerprint/content_updated_at; identical JSON stays unchanged.
            changed = (await session.execute(select(or_(
                ExternalListingSource.raw_payload.is_distinct_from(literal(detail.raw, type_=JSONB)),
                ExternalListingSource.normalized_payload.is_distinct_from(literal(detail.normalized, type_=JSONB)),
                ExternalListingSource.source_price_text.is_distinct_from(literal(detail.price, type_=Text)),
            )).where(ExternalListingSource.id == target.row.id))).scalar_one()
            values.update(raw_payload=detail.raw, normalized_payload=detail.normalized, source_price_text=detail.price,
                fingerprint=digest({"raw": detail.raw, "normalized": detail.normalized, "price": detail.price})
                    if changed else target.row.fingerprint,
                # Use the DB observation timestamp from before GET, not a later
                # commit/lock-wait time. Queuing cannot extend content freshness.
                last_success_at=target.row.checked_at,
                content_updated_at=target.row.checked_at if changed else target.row.content_updated_at)
            await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == target.row.id).values(**values))
            _, updated = await pipeline._authority(session, target.row.canonical_listing_id, lock=False)
            await pipeline._publish(session, anchor, visible, updated)
            await session.execute(insert(OPERATIONS).values(operation=operation, namespace=namespace,
                                                          source_id=target.row.id, committed_at=now))
            self._namespace()
            return "refreshed"

    async def run_receipt(self, revision: int, *, expected_digest: str) -> RefreshReceiptResult:
        """One exact retained receipt. Never ACK or delete any supervisor evidence."""
        try:
            await self._schema()
            bounded(revision, 10_000)
            store = self.supervisor.journal
            if store.receipt_digest(revision) != expected_digest:
                raise ValueError("exact synthetic receipt required")
            receipt = store.receipt(revision)
            if receipt is None:
                raise ValueError("exact synthetic receipt required")
            ids = tuple(UUID(value) for value in receipt["content_refresh_due"])
            if len(ids) > self.policy.max_requests or len(set(ids)) != len(ids) or any(v not in self.cohort for v in ids):
                raise ValueError("synthetic refresh receipt exceeds explicit cohort/budget")
            namespace = self._namespace()
            keys = [digest({"namespace": namespace, "revision": revision, "receipt": expected_digest,
                            "source": str(v)}) for v in ids]
            async with self.sessions() as session:
                known = set((await session.scalars(select(OPERATIONS.c.operation).where(
                    OPERATIONS.c.operation.in_(keys)))).all())
                count = int(await session.scalar(select(func.count()).select_from(OPERATIONS)) or 0)
            # Validate every new target before the first mock GET; no partial unauthorized receipt.
            targets = [None if key in known else await self._target(source_id) for source_id, key in zip(ids, keys, strict=True)]
            outcomes = []
            for target, key in zip(targets, keys, strict=True):
                if target is None:
                    outcomes.append("already_applied")
                elif (target.row.healthy and target.row.last_success_at is not None
                        and 0 <= (target.row.checked_at - target.row.last_success_at).total_seconds()
                        <= self.supervisor.coordinator.sources[self.policy.source_name].content_max_age_seconds):
                    outcomes.append("already_fresh")
                elif count >= self.policy.max_operations:
                    outcomes.append("capacity")
                else:
                    detail, state = await self._fetch(target)
                    outcome = await self._write(target, key, namespace, detail, state)
                    outcomes.append(outcome)
                    count += int(outcome == "refreshed")
            return RefreshReceiptResult(tuple(outcomes))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 -- unknown commit outcome must be recovered via PG receipt, not blind retry here.
            raise SyntheticRefreshUnavailable("SYNTHETIC_DETAIL_REFRESH_UNAVAILABLE") from None
