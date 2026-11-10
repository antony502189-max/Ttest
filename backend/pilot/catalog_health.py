"""Durable private-catalog publication barrier, separate from seed/provider state."""

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4


def cohort_hash(snapshot):
    pairs = [(str(UUID(r["listing"]["id"])), str(UUID(r["source"]["id"]))) for r in snapshot["records"]]
    if (
        not 1 <= len(pairs) <= 20
        or len({p[0] for p in pairs}) != len(pairs)
        or len({p[1] for p in pairs}) != len(pairs)
    ):
        raise ValueError("PILOT_REFRESH_COHORT_INVALID")
    return hashlib.sha256(json.dumps(sorted(pairs), separators=(",", ":")).encode()).hexdigest()


class CatalogHealth:
    def __init__(self, path: Path, cohort_hash: str, *, uid: int | None = None):
        self.path, self.cohort_hash, self.uid = path, cohort_hash, uid

    def _read(self):
        if self.path.is_symlink():
            raise ValueError("PILOT_HEALTH_STATE_INVALID")
        if not self.path.exists():
            return {
                "schema": "pilot-health.v1",
                "cohort_hash": self.cohort_hash,
                "generation": 0,
                "token": None,
                "phase": "failed",
                "last_success": None,
                "snapshot_at": None,
                "consecutive_failures": 0,
                "active": 0,
                "removed": 0,
            }
        raw = self.path.read_bytes()
        if len(raw) > 4096:
            raise ValueError("PILOT_HEALTH_STATE_INVALID")
        value = json.loads(raw)
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "schema",
                "cohort_hash",
                "generation",
                "token",
                "phase",
                "last_success",
                "snapshot_at",
                "consecutive_failures",
                "active",
                "removed",
            }
            or value.get("schema") != "pilot-health.v1"
            or value.get("cohort_hash") != self.cohort_hash
            or value.get("phase") not in {"failed", "refreshing", "ready"}
            or any(
                type(value.get(k)) is not int or value[k] < 0
                for k in ("generation", "consecutive_failures", "active", "removed")
            )
        ):
            raise ValueError("PILOT_HEALTH_STATE_INVALID")
        if value["token"] is not None and (
            not isinstance(value["token"], str) or UUID(value["token"]).hex != value["token"]
        ):
            raise ValueError("PILOT_HEALTH_STATE_INVALID")
        if value["active"] + value["removed"] > 20:
            raise ValueError("PILOT_HEALTH_STATE_INVALID")
        return value

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix(".lock")
        if lock.is_symlink():
            raise ValueError("PILOT_HEALTH_STATE_INVALID")
        with lock.open("a+b") as stream:
            if os.name == "nt":
                import msvcrt

                if stream.tell() == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def _write(self, value):
        temporary = self.path.with_name(".catalog-health-" + uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as stream:
                os.chmod(temporary, 0o600)
                if self.uid is not None and os.name != "nt":
                    os.chown(temporary, self.uid, self.uid)
                stream.write(json.dumps(value, sort_keys=True).encode())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            if os.name != "nt":
                fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            temporary.unlink(missing_ok=True)

    def begin(self):
        with self._locked():
            value = self._read()
            value.update(token=uuid4().hex, generation=value["generation"] + 1, phase="refreshing")
            self._write(value)
            return value["token"]

    def fail(self, token=None):
        with self._locked():
            value = self._read()
            if token is not None and value["token"] != token:
                return
            if value["phase"] != "failed":
                value["consecutive_failures"] += 1
            value["phase"] = "failed"
            self._write(value)

    def publish(self, token, *, snapshot_at, active, removed):
        with self._locked():
            value = self._read()
            if value["token"] != token or value["phase"] != "refreshing":
                raise ValueError("PILOT_REFRESH_FENCED")
            value.update(
                phase="ready",
                snapshot_at=snapshot_at,
                last_success=datetime.now(UTC).isoformat(),
                consecutive_failures=0,
                active=active,
                removed=removed,
            )
            self._write(value)

    def ticket(self):
        value = self._read()
        success = datetime.fromisoformat(value["last_success"]) if value["last_success"] else None
        age = (datetime.now(UTC) - success).total_seconds() if success else -1
        if value["phase"] != "ready" or not 0 <= age <= 4500 or not value["token"]:
            raise ValueError("PILOT_CATALOG_REFRESH_UNAVAILABLE")
        return value["token"]

    def unchanged(self, token):
        if self.ticket() != token:
            raise ValueError("PILOT_CATALOG_REFRESH_CHANGED")

    def metrics(self):
        value = self._read()
        try:
            self.ticket()
            ready = 1
        except (ValueError, TypeError):
            ready = 0
        last = datetime.fromisoformat(value["last_success"]).timestamp() if value["last_success"] else 0
        return (
            f"ttest_pilot_catalog_ready {ready}\n"
            f"ttest_pilot_catalog_last_success_seconds {last}\n"
            f"ttest_pilot_catalog_consecutive_failures {value['consecutive_failures']}\n"
            f"ttest_pilot_catalog_generation {value['generation']}\n"
            f"ttest_pilot_catalog_active_records {value['active']}\n"
            f"ttest_pilot_catalog_removed_records {value['removed']}\n"
        )
