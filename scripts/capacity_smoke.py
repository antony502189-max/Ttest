#!/usr/bin/env python3
"""Bounded, read-only capacity smoke for one exact production release."""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import fcntl
import http.client
import ipaddress
import json
import math
import os
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

PRODUCTION_HOST = "app.112233.es"
PATHS = (
    "/api/health/live",
    "/api/health/ready",
    "/api/v1/listings?city=capacitysmoke7f3f9cnohit",
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_BYTES = 64 * 1024
MAX_TOTAL = 300
MAX_CONCURRENCY = 8
MAX_RATE = 20.0
MAX_TIMEOUT = 10.0
MAX_LOCK_SECONDS = 300.0


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Sample:
    path: str
    status: int | None
    elapsed_ms: float
    ok: bool
    error: str | None = None


def _run_git(target: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(target), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError(f"could not verify release Git state: {exc}") from exc


def validate_sha(expected: str, confirmation: str) -> str:
    expected = expected.strip()
    if not SHA_RE.fullmatch(expected):
        raise ConfigurationError("expected SHA must be a lowercase 40-character commit SHA")
    if confirmation.strip() != expected:
        raise ConfigurationError("confirmation SHA must exactly match expected SHA")
    return expected


def validate_origin(value: str, allow_host: str, loopback_test: bool = False) -> str:
    parsed = urllib.parse.urlsplit(value)
    host = (parsed.hostname or "").casefold()
    allowed = allow_host.strip().casefold()
    local = loopback_test and parsed.scheme == "http" and host in {"localhost", "127.0.0.1", "::1"}
    if not local and allowed != PRODUCTION_HOST:
        raise ConfigurationError(f"allow-host must be {PRODUCTION_HOST}")
    if host != allowed or parsed.username or parsed.password:
        raise ConfigurationError("origin must use the exact allowed host without credentials")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ConfigurationError("base URL must contain only an origin")
    if parsed.scheme != "https" and not local:
        raise ConfigurationError("HTTPS is required")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ConfigurationError("invalid port") from exc
    if not local and port not in (None, 443):
        raise ConfigurationError("production smoke permits only port 443")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def resolve_addresses(origin: str, loopback_test: bool = False) -> tuple[str, ...]:
    parsed = urllib.parse.urlsplit(origin)
    host = parsed.hostname
    if not host:
        raise ConfigurationError("origin has no hostname")
    try:
        records = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ConfigurationError(f"could not resolve target: {exc}") from exc
    addresses: list[str] = []
    for record in records:
        try:
            address = ipaddress.ip_address(record[4][0])
        except ValueError as exc:
            raise ConfigurationError(f"resolver returned an invalid address: {record[4][0]}") from exc
        if not address.is_global and not (loopback_test and address.is_loopback):
            raise ConfigurationError(f"target resolved to non-public address: {address.compressed}")
        if address.compressed not in addresses:
            addresses.append(address.compressed)
    if not addresses:
        raise ConfigurationError("target resolved to no usable address")
    return tuple(addresses)


@contextlib.contextmanager
def release_lock(root: Path):
    path = root / "shared" / "release.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(descriptor)
        raise ConfigurationError("another release-state operation is running") from exc
    try:
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def verify_release(root: Path, sha: str) -> Path:
    current = root / "current"
    if not current.is_symlink():
        raise ConfigurationError("current must be a release symlink")
    try:
        target = current.resolve(strict=True)
        releases = (root / "releases").resolve(strict=True)
        expected_common = (root / "repo" / ".git").resolve(strict=True)
    except OSError as exc:
        raise ConfigurationError(f"invalid release layout: {exc}") from exc
    if target != releases / sha or not target.is_dir():
        raise ConfigurationError(f"current release is not {sha}")
    if _run_git(target, "rev-parse", "HEAD").lower() != sha:
        raise ConfigurationError("current release HEAD mismatch")
    common = Path(_run_git(target, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = target / common
    try:
        common = common.resolve(strict=True)
    except OSError as exc:
        raise ConfigurationError(f"invalid Git common directory: {exc}") from exc
    if common != expected_common:
        raise ConfigurationError("release belongs to another Git repository")
    if _run_git(target, "status", "--porcelain", "--untracked-files=all"):
        raise ConfigurationError("release worktree is dirty")
    return target


def verify_metadata(root: Path, sha: str) -> None:
    path = root / "releases" / f"{sha}.deploy-info"
    try:
        stat = path.lstat()
    except OSError as exc:
        raise ConfigurationError(f"deployment metadata is unavailable: {exc}") from exc
    if path.is_symlink() or not path.is_file() or stat.st_size > MAX_BYTES or stat.st_mode & 0o077:
        raise ConfigurationError("deployment metadata must be a private regular file no larger than 64 KiB")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    if values.get("new_sha") != sha or values.get("status") != "success":
        raise ConfigurationError("deployment metadata does not confirm this successful release")
    if not values.get("revision_after") or not values.get("image_ids"):
        raise ConfigurationError("deployment metadata lacks migration or image evidence")


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, **kwargs: Any) -> None:
        self.address = address
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        raw = socket.create_connection((self.address, self.port), self.timeout, self.source_address)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, address: str, **kwargs: Any) -> None:
        self.address = address
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        self.sock = socket.create_connection((self.address, self.port), self.timeout, self.source_address)


def validate_payload(path: str, payload: Any) -> None:
    if path.startswith("/api/health/"):
        if not isinstance(payload, dict) or not any(key in payload for key in ("status", "ok")):
            raise ValueError("health response lacks status")
        return
    if path.startswith("/api/v1/listings") and not isinstance(payload, list):
        raise ValueError("public listings response must be a JSON array")


def request_once(origin: str, path: str, sha: str, timeout: float, address: str | None = None) -> Sample:
    if path not in PATHS:
        raise ConfigurationError("request path is not in the fixed read-only allowlist")
    parsed = urllib.parse.urlsplit(origin)
    started = time.perf_counter()
    deadline = started + timeout
    status: int | None = None
    connection: http.client.HTTPConnection | None = None
    try:
        host, port = parsed.hostname or "", parsed.port or (443 if parsed.scheme == "https" else 80)
        if parsed.scheme == "https":
            connection = PinnedHTTPSConnection(host, address, port=port, timeout=timeout, context=ssl.create_default_context()) if address else http.client.HTTPSConnection(host, port=port, timeout=timeout, context=ssl.create_default_context())
        else:
            connection = PinnedHTTPConnection(host, address, port=port, timeout=timeout) if address else http.client.HTTPConnection(host, port=port, timeout=timeout)
        connection.request("GET", path, headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "close",
            "User-Agent": "112233-capacity-smoke/1",
            "X-Capacity-Smoke-Release": sha,
        })
        response = connection.getresponse()
        status = response.status
        body = bytearray()
        while len(body) <= MAX_BYTES:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise TimeoutError("absolute request deadline exceeded")
            if connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = response.read1(min(8192, MAX_BYTES + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        if status != 200:
            raise ValueError(f"unexpected HTTP status {status}; redirects are disabled")
        if response.headers.get_content_type() != "application/json":
            raise ValueError("response is not JSON")
        if len(body) > MAX_BYTES:
            raise ValueError("response exceeds 64 KiB")
        validate_payload(path, json.loads(body))
        return Sample(path, status, (time.perf_counter() - started) * 1000, True)
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError, http.client.HTTPException) as exc:
        return Sample(path, status, (time.perf_counter() - started) * 1000, False, f"{type(exc).__name__}: {exc}")
    finally:
        if connection is not None:
            connection.close()


def validate_budget(requests: int, concurrency: int, rate: float, timeout: float) -> float:
    if not 1 <= requests <= MAX_TOTAL - len(PATHS):
        raise ConfigurationError(f"requests must be between 1 and {MAX_TOTAL - len(PATHS)}")
    if not 1 <= concurrency <= MAX_CONCURRENCY:
        raise ConfigurationError(f"concurrency must be between 1 and {MAX_CONCURRENCY}")
    if not math.isfinite(rate) or not 0.1 <= rate <= MAX_RATE:
        raise ConfigurationError(f"rate must be between 0.1 and {MAX_RATE}")
    if not math.isfinite(timeout) or not 0.1 <= timeout <= MAX_TIMEOUT:
        raise ConfigurationError(f"timeout must be between 0.1 and {MAX_TIMEOUT}")
    upper = len(PATHS) * timeout + max((requests - 1) / rate + timeout, math.ceil(requests / concurrency) * timeout)
    if upper > MAX_LOCK_SECONDS:
        raise ConfigurationError("configuration could hold the release lock for more than five minutes")
    return upper


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def summarize(sha: str, origin: str, samples: Sequence[Sample], duration: float, phase: str, upper: float) -> dict[str, Any]:
    successful = [sample for sample in samples if sample.ok]
    failures = [asdict(sample) for sample in samples if not sample.ok]
    latencies = [sample.elapsed_ms for sample in successful]
    measured = len(samples) if phase == "measured" else 0
    warmup = len(PATHS) if phase == "measured" else len(samples)
    return {
        "schemaVersion": 1,
        "phase": phase,
        "releaseSha": sha,
        "origin": origin,
        "readOnlyPaths": list(PATHS),
        "warmupRequests": warmup,
        "measuredRequests": measured,
        "totalRequests": warmup + measured,
        "successfulRequests": len(successful),
        "failedRequests": len(failures),
        "successRate": round(len(successful) / len(samples), 6) if samples else 0.0,
        "durationSeconds": round(duration, 3),
        "configuredWorstCaseSeconds": round(upper, 3),
        "requestsPerSecond": round(len(samples) / duration, 3) if duration else 0.0,
        "latencyMs": {
            "p50": round(_percentile(latencies, 0.50), 3),
            "p95": round(_percentile(latencies, 0.95), 3),
            "p99": round(_percentile(latencies, 0.99), 3),
            "max": round(max(latencies), 3) if latencies else 0.0,
        },
        "failures": failures[:20],
    }


def run_smoke(origin: str, sha: str, requests: int, concurrency: int, rate: float, timeout: float, addresses: Sequence[str]) -> dict[str, Any]:
    if not addresses:
        raise ConfigurationError("at least one pre-resolved target address is required")
    upper = validate_budget(requests, concurrency, rate, timeout)
    warmup = [request_once(origin, path, sha, timeout, addresses[index % len(addresses)]) for index, path in enumerate(PATHS)]
    if any(not sample.ok for sample in warmup):
        return summarize(sha, origin, warmup, 0.0, "warmup", upper)
    started = time.perf_counter()
    gate = threading.Lock()
    next_start = started

    def scheduled(index: int) -> Sample:
        nonlocal next_start
        with gate:
            at = max(time.perf_counter(), next_start)
            next_start = at + 1 / rate
        time.sleep(max(0.0, at - time.perf_counter()))
        return request_once(origin, PATHS[index % len(PATHS)], sha, timeout, addresses[index % len(addresses)])

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        samples = list(executor.map(scheduled, range(requests)))
    return summarize(sha, origin, samples, time.perf_counter() - started, "measured", upper)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--allow-host", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--confirm-sha", required=True)
    parser.add_argument("--release-root", type=Path, default=Path("/srv/112233.es"))
    parser.add_argument("--requests", type=int, default=60)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--rate", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--min-success-rate", type=float, default=1.0)
    parser.add_argument("--max-p95-ms", type=float)
    parser.add_argument("--allow-http-loopback", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        sha = validate_sha(args.expected_sha, args.confirm_sha)
        origin = validate_origin(args.base_url, args.allow_host, args.allow_http_loopback)
        addresses = resolve_addresses(origin, args.allow_http_loopback)  # Deliberately before release lock.
        if not 0.0 <= args.min_success_rate <= 1.0 or not math.isfinite(args.min_success_rate):
            raise ConfigurationError("minimum success rate must be between 0 and 1")
        if args.max_p95_ms is not None and (not math.isfinite(args.max_p95_ms) or args.max_p95_ms <= 0):
            raise ConfigurationError("maximum p95 must be positive")
        with release_lock(args.release_root):
            verify_release(args.release_root, sha)
            verify_metadata(args.release_root, sha)
            result = run_smoke(origin, sha, args.requests, args.concurrency, args.rate, args.timeout, addresses)
    except ConfigurationError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 64
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["phase"] != "measured" or result["successRate"] < args.min_success_rate:
        return 1
    if args.max_p95_ms is not None and result["latencyMs"]["p95"] > args.max_p95_ms:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
