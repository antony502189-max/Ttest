"""Finite synthetic supervision harness. No daemon, production journal or importer.

SQLite is a separate owned checkpoint/receipt store, not the provider budget.
Short FULL-synchronous transactions never span coordinator work. A process may
die anywhere: the next owner replays the previous cursor after the lease expires.
Async deadlines are cooperative; synchronous builders still require an external
process deadline before real deployment. This module installs no startup hook.
"""

import asyncio
import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic, time
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.engine import make_url

from app.models import ExternalListingSource
from app.models.ai_fact_pipeline import AiFactJob
from app.services.ai_fact_coordinator import FactCoordinatorCursor, FactCoordinatorTick, OfflineFactCoordinator


class SupervisorUnavailable(RuntimeError):
    """Redacted storage/tick failure. Read durable state before retrying."""


class StaleSupervisor(RuntimeError):
    pass


def bounded(value: int, maximum: int) -> None:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError("explicit bounded synthetic supervisor policy required")


def configuration_digest(coordinator: OfflineFactCoordinator, *, builder_bundle_sha256: str,
                         catalog_identity_sha256: str) -> str:
    if any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in (builder_bundle_sha256, catalog_identity_sha256)):
        raise ValueError("reviewed synthetic builder and catalog digests required")
    pipeline = coordinator.pipeline
    for policy, worker in zip(coordinator.sources.values(), coordinator.workers, strict=True):
        if (worker.pipeline is not pipeline or worker.reader is not coordinator.reader
                or worker.source_name != policy.source_name or worker.extractor_version != policy.extractor_version
                or worker.mapping != policy.mapping or worker.builder is not policy.builder
                or worker.retry_builder_failures != policy.retry_builder_failures):
            raise ValueError("synthetic worker configuration differs from declared source policy")
    target = make_url(pipeline.sessions.kw["bind"].url)
    if target.host not in {"localhost", "127.0.0.1", "::1"} or not (target.database or "").startswith("ai_facts_test_"):
        raise ValueError("synthetic supervisor requires disposable loopback ai_facts_test_* catalog")
    body: dict[str, Any] = {"builder_bundle": builder_bundle_sha256, "catalog_identity": catalog_identity_sha256,
        "target": {"host": target.host, "port": target.port, "database": target.database},
        "resolver": pipeline.resolver_version,
        "vocabulary": pipeline.vocabulary.model_dump(mode="json"), "queue": pipeline.policy.model_dump(),
        "quality": pipeline.operating_policy.model_dump() if pipeline.operating_policy else None,
        "max_sources": coordinator.max_sources, "max_reconcile": coordinator.max_reconcile,
        "max_payload_bytes": coordinator.reader.max_payload_bytes,
        "sources": [{"source_name": p.source_name, "mapping": p.mapping.model_dump(mode="json"),
            "version": p.extractor_version, "ttl": p.content_max_age_seconds, "jobs": p.max_jobs,
            "retry": p.retry_builder_failures} for p in coordinator.sources.values()]}
    # Pydantic emits frozensets as arrays; canonicalize those recursively.
    # Mapping sets currently occur only as rented_unit_capacity_fields.
    for source in body["sources"]:
        source["mapping"]["rented_unit_capacity_fields"].sort()
    for value in body["vocabulary"].values():
        value.sort()
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class SupervisorPolicy:
    interval_seconds: int
    deadline_seconds: int
    lease_seconds: int
    backoff_seconds: int
    max_backoff_seconds: int
    stale_seconds: int
    max_receipts: int
    max_health_jobs: int

    def __post_init__(self) -> None:
        for value in (self.interval_seconds, self.deadline_seconds, self.lease_seconds,
                      self.backoff_seconds, self.max_backoff_seconds, self.stale_seconds):
            bounded(value, 86_400)
        bounded(self.max_receipts, 10_000)
        bounded(self.max_health_jobs, 1000)
        if self.lease_seconds <= self.deadline_seconds or self.max_backoff_seconds < self.backoff_seconds:
            raise ValueError("lease must exceed deadline; explicit capped backoff required")


@dataclass(frozen=True)
class SupervisorClaim:
    revision: int
    fence: int
    owner: str
    cursor: FactCoordinatorCursor


@dataclass(frozen=True)
class SupervisorState:
    revision: int
    cursor: FactCoordinatorCursor
    failures: int
    next_at: float
    last_success: float | None
    failure_code: str | None
    lease_until: float | None


class SyntheticSupervisorJournal:
    def __init__(self, path: Path, *, configuration_sha256: str, policy: SupervisorPolicy):
        if not re.fullmatch(r"DISPOSABLE-fact-supervisor-[A-Za-z0-9_-]+\.sqlite3", path.name):
            raise ValueError("separate explicitly disposable supervisor journal required")
        if not re.fullmatch(r"[0-9a-f]{64}", configuration_sha256):
            raise ValueError("explicit configuration digest required")
        self.path, self.policy = path.resolve(), policy
        self.configuration_sha256 = configuration_sha256
        # Include supervision limits in the immutable binding as well.
        self.binding = json.dumps({"configuration": configuration_sha256, "policy": asdict(policy)}, sort_keys=True)
        if path.is_symlink() or self.path.name != path.name:
            raise ValueError("synthetic supervisor journal must be an owned regular file")
        with self._transaction(initialize=True) as db:
            db.execute("CREATE TABLE IF NOT EXISTS supervisor (id INTEGER PRIMARY KEY CHECK(id=1), "
                "binding TEXT NOT NULL, revision INTEGER NOT NULL, fence INTEGER NOT NULL, owner TEXT, "
                "lease_until REAL, source_after TEXT, reconcile_after TEXT, failures INTEGER NOT NULL, "
                "next_at REAL NOT NULL, last_success REAL, failure_code TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS receipts (revision INTEGER PRIMARY KEY, receipt TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO supervisor VALUES(1,?,0,0,NULL,NULL,NULL,NULL,0,0,NULL,NULL)", (self.binding,))
            if db.execute("SELECT binding FROM supervisor WHERE id=1").fetchone()[0] != self.binding:
                raise ValueError("synthetic supervisor configuration binding mismatch")

    @contextmanager
    def _transaction(self, *, initialize: bool = False) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path, timeout=1)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA synchronous=FULL")
            with db:
                db.execute("BEGIN IMMEDIATE")
                application_id = db.execute("PRAGMA application_id").fetchone()[0]
                if application_id != 0x41495332:
                    if not initialize or application_id != 0 or db.execute(
                        "SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]:
                        raise ValueError("not an owned synthetic supervisor journal")
                    db.execute("PRAGMA application_id=1095324466")
                yield db

    @staticmethod
    def _cursor(row: sqlite3.Row) -> FactCoordinatorCursor:
        return FactCoordinatorCursor(UUID(row["source_after"]) if row["source_after"] else None,
                                     UUID(row["reconcile_after"]) if row["reconcile_after"] else None)

    def state(self) -> SupervisorState:
        with self._transaction() as db:
            row = db.execute("SELECT * FROM supervisor WHERE id=1").fetchone()
            return SupervisorState(row["revision"], self._cursor(row), row["failures"], row["next_at"],
                                   row["last_success"], row["failure_code"], row["lease_until"])

    def claim(self, now: float) -> SupervisorClaim | None:
        with self._transaction() as db:
            row = db.execute("SELECT * FROM supervisor WHERE id=1").fetchone()
            if row["next_at"] > now or (row["lease_until"] is not None and row["lease_until"] > now):
                return None
            # Never advance a checkpoint if its receipt cannot be retained.
            if db.execute("SELECT count(*) FROM receipts").fetchone()[0] >= self.policy.max_receipts:
                raise SupervisorUnavailable("SYNTHETIC_SUPERVISOR_RECEIPTS_FULL")
            owner, fence = uuid4().hex, row["fence"] + 1
            db.execute("UPDATE supervisor SET owner=?,fence=?,lease_until=? WHERE id=1",
                       (owner, fence, now + self.policy.lease_seconds))
            return SupervisorClaim(row["revision"], fence, owner, self._cursor(row))

    @staticmethod
    def _guard(db: sqlite3.Connection, claim: SupervisorClaim, now: float) -> sqlite3.Row:
        row = db.execute("SELECT * FROM supervisor WHERE id=1").fetchone()
        if (row["revision"] != claim.revision or row["fence"] != claim.fence or row["owner"] != claim.owner
                or row["lease_until"] is None or row["lease_until"] <= now):
            raise StaleSupervisor("SYNTHETIC_SUPERVISOR_STALE")
        return row

    def complete(self, claim: SupervisorClaim, tick: FactCoordinatorTick, now: float) -> None:
        receipt = json.dumps(asdict(tick), default=str, sort_keys=True)
        if len(receipt.encode()) > 65_536:
            raise ValueError("bounded supervisor receipt required")
        with self._transaction() as db:
            self._guard(db, claim, now)
            db.execute("INSERT INTO receipts VALUES (?,?)", (claim.revision + 1, receipt))
            db.execute("UPDATE supervisor SET revision=revision+1,source_after=?,reconcile_after=?, "
                "failures=0,next_at=?,last_success=?,failure_code=NULL,owner=NULL,lease_until=NULL WHERE id=1",
                (str(tick.cursor.source_after) if tick.cursor.source_after else None,
                 str(tick.cursor.reconcile_after) if tick.cursor.reconcile_after else None,
                 now + self.policy.interval_seconds, now))

    def fail(self, claim: SupervisorClaim, now: float, *, timeout: bool) -> None:
        with self._transaction() as db:
            row = self._guard(db, claim, now)
            failures = row["failures"] + 1
            delay = min(self.policy.max_backoff_seconds, self.policy.backoff_seconds * 2 ** min(failures - 1, 20))
            db.execute("UPDATE supervisor SET failures=?,next_at=?,failure_code=?,owner=NULL,lease_until=NULL WHERE id=1",
                (failures, now + delay, "TICK_DEADLINE" if timeout else "TICK_FAILED"))

    def receipt(self, revision: int) -> dict | None:
        with self._transaction() as db:
            row = db.execute("SELECT receipt FROM receipts WHERE revision=?", (revision,)).fetchone()
            return json.loads(row[0]) if row else None

    def receipt_count(self) -> int:
        with self._transaction() as db:
            return db.execute("SELECT count(*) FROM receipts").fetchone()[0]


@dataclass(frozen=True)
class SupervisorHealth:
    revision: int
    stale: bool
    consecutive_failures: int
    terminal_jobs: int
    expired_leases: int
    retry_jobs: int
    pending_jobs: int
    sample_truncated: bool
    rejected_sources: int
    deferred_proofs: int
    content_refresh_due: int
    receipt_capacity_reached: bool
    attention: bool


class SyntheticFactSupervisor:
    def __init__(self, coordinator: OfflineFactCoordinator, journal: SyntheticSupervisorJournal, *,
                 builder_bundle_sha256: str, catalog_identity_sha256: str, clock: Callable[[], float] = time):
        self.builder_bundle_sha256, self.catalog_identity_sha256 = builder_bundle_sha256, catalog_identity_sha256
        self.coordinator, self.journal, self.clock = coordinator, journal, clock
        self._binding()

    def _binding(self) -> None:
        if configuration_digest(self.coordinator, builder_bundle_sha256=self.builder_bundle_sha256,
                                catalog_identity_sha256=self.catalog_identity_sha256) != self.journal.configuration_sha256:
            raise ValueError("coordinator configuration does not match supervisor journal")

    async def run_once(self) -> str:
        claim = None
        try:
            self._binding()
            claim = self.journal.claim(self.clock())
            if claim is None:
                return "deferred"
            started = monotonic()
            async with asyncio.timeout(self.journal.policy.deadline_seconds):
                tick = await self.coordinator.run_once(claim.cursor)
            # A synchronous builder can block the event loop long enough that
            # asyncio's cancellation callback never runs. Do not acknowledge
            # such an overrun as a timely successful tick after it returns.
            if monotonic() - started > self.journal.policy.deadline_seconds:
                raise TimeoutError
            self.journal.complete(claim, tick, self.clock())
            return "committed"
        except asyncio.CancelledError:
            # Process shutdown must not acknowledge/advance the checkpoint.
            # Leave the lease for restart, just as a hard process death does.
            raise
        except Exception as error:  # noqa: BLE001 -- redact all source/storage failure details at harness boundary.
            if claim is not None:
                try:
                    self.journal.fail(claim, self.clock(), timeout=isinstance(error, TimeoutError))
                except (StaleSupervisor, sqlite3.Error, ValueError):
                    # A lost ACK may already have committed the receipt; never
                    # overwrite that success or a newer owner's checkpoint.
                    pass
            raise SupervisorUnavailable("SYNTHETIC_SUPERVISOR_UNAVAILABLE") from None

    async def run_steps(self, *, steps: int) -> tuple[str, ...]:
        """Finite poll harness; external scheduler owns sleep and process lifetime."""
        bounded(steps, 100)
        return tuple([await self.run_once() for _ in range(steps)])

    async def health(self) -> SupervisorHealth:
        try:
            self._binding()
            return await self._health()
        except Exception:  # noqa: BLE001 -- health must not expose storage parameters or source details.
            raise SupervisorUnavailable("SYNTHETIC_SUPERVISOR_HEALTH_UNAVAILABLE") from None

    async def _health(self) -> SupervisorHealth:
        state, now = self.journal.state(), self.clock()
        service = self.coordinator.pipeline
        sources = self.coordinator.sources.values()
        scope = or_(*(and_(AiFactJob.extractor_version == p.extractor_version,
            AiFactJob.source_record_id.in_(select(ExternalListingSource.id).where(
                ExternalListingSource.source_name == p.source_name))) for p in sources))
        async with service.sessions() as session:
            rows = (await session.execute(select(AiFactJob.status, AiFactJob.attempts, AiFactJob.lease_until)
                .where(scope, AiFactJob.status.in_(["pending", "running", "failed"]))
                .order_by(AiFactJob.id).limit(self.journal.policy.max_health_jobs + 1))).all()
        truncated = len(rows) > self.journal.policy.max_health_jobs
        rows = rows[:self.journal.policy.max_health_jobs]
        terminal = sum(r.status == "failed" for r in rows)
        expired = sum(r.status == "running" and r.lease_until.timestamp() <= now for r in rows)
        retry = sum(r.status == "pending" and r.attempts > 0 for r in rows)
        pending = sum(r.status == "pending" for r in rows)
        stale = (state.last_success is None or now < state.last_success
                 or now - state.last_success > self.journal.policy.stale_seconds)
        receipt = self.journal.receipt(state.revision)
        if state.revision > 0 and receipt is None:
            raise SupervisorUnavailable("SYNTHETIC_SUPERVISOR_RECEIPT_MISSING")
        rejected = receipt["rejected"] if receipt else 0
        deferred = receipt["proofs_deferred"] if receipt else 0
        refresh = len(receipt["content_refresh_due"]) if receipt else 0
        capacity = self.journal.receipt_count() >= self.journal.policy.max_receipts
        return SupervisorHealth(state.revision, stale, state.failures, terminal, expired, retry, pending, truncated,
            rejected, deferred, refresh, capacity,
            stale or state.failures > 0 or terminal > 0 or expired > 0 or retry > 0 or truncated
            or pending > 0 or rejected > 0 or deferred > 0 or refresh > 0 or capacity)
