#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capacity_smoke

SHA = "a" * 40


class Handler(BaseHTTPRequestHandler):
    mode = "ok"

    def do_GET(self) -> None:  # noqa: N802
        if self.mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "/api/health/live")
            self.end_headers()
            return
        if self.mode == "slow_headers":
            time.sleep(0.5)
        if self.mode == "slow":
            payload = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                for byte in payload:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        if self.mode == "html":
            payload = b"<html>not json</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
        elif self.path.startswith("/api/v1/listings?"):
            payload = b"[]"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            payload = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format: str, *args: object) -> None:
        return


class CapacitySmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        Handler.mode = "ok"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def release_root(self) -> tuple[tempfile.TemporaryDirectory[str], str]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        repo = root / "repo"
        repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Capacity Smoke Test"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "capacity@example.invalid"], check=True)
        (repo / "release.txt").write_text("immutable release\n")
        subprocess.run(["git", "-C", str(repo), "add", "release.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "test release"], check=True)
        sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        release = root / "releases" / sha
        release.parent.mkdir(parents=True)
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "--detach", str(release), sha],
            check=True,
            capture_output=True,
        )
        (root / "shared").mkdir()
        (root / "current").symlink_to(release)
        metadata = root / "releases" / f"{sha}.deploy-info"
        metadata.write_text(
            "old_sha=none\n"
            f"new_sha={sha}\n"
            "status=in_progress\n"
            "revision_after=0032\n"
            "image_ids=sha256:backend,sha256:frontend\n"
            "status=success\n",
        )
        metadata.chmod(0o600)
        self.addCleanup(temporary.cleanup)
        return temporary, sha

    def test_exact_host_and_https_policy(self) -> None:
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.validate_origin("http://app.112233.es", "app.112233.es")
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.validate_origin("https://app.112233.es/path", "app.112233.es")
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.validate_origin("https://app.112233.es", "other.example")
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.validate_origin("https://app.112233.es:8443", "app.112233.es")
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.validate_origin("https://example.com", "example.com")
        self.assertEqual(
            capacity_smoke.validate_origin(
                "https://app.112233.es",
                "app.112233.es",
            ),
            "https://app.112233.es",
        )
        self.assertEqual(
            capacity_smoke.validate_origin(self.base_url, "127.0.0.1", True),
            self.base_url,
        )

    def test_resolution_is_public_and_pinned_before_the_run(self) -> None:
        public_record = [(2, 1, 6, "", ("8.8.8.8", 443))]
        with mock.patch("capacity_smoke.socket.getaddrinfo", return_value=public_record):
            self.assertEqual(
                capacity_smoke.resolve_addresses("https://app.112233.es"),
                ("8.8.8.8",),
            )

        private_record = [(2, 1, 6, "", ("10.0.0.5", 443))]
        with mock.patch("capacity_smoke.socket.getaddrinfo", return_value=private_record):
            with self.assertRaises(capacity_smoke.ConfigurationError):
                capacity_smoke.resolve_addresses("https://app.112233.es")
        invalid_record = [(2, 1, 6, "", ("not-an-ip", 443))]
        with mock.patch("capacity_smoke.socket.getaddrinfo", return_value=invalid_record):
            with self.assertRaises(capacity_smoke.ConfigurationError):
                capacity_smoke.resolve_addresses("https://app.112233.es")

        loopback = capacity_smoke.resolve_addresses(self.base_url, True)
        sample = capacity_smoke.request_once(
            self.base_url,
            "/api/health/live",
            SHA,
            2,
            loopback[0],
        )
        self.assertTrue(sample.ok)

    def test_release_symlink_must_match_confirmed_sha(self) -> None:
        temporary, sha = self.release_root()
        target = capacity_smoke.verify_release(Path(temporary.name), sha)
        self.assertEqual(target.name, sha)
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.verify_release(Path(temporary.name), "b" * 40)

    def test_release_worktree_must_be_clean(self) -> None:
        temporary, sha = self.release_root()
        target = Path(temporary.name) / "releases" / sha
        (target / "untracked.txt").write_text("dirty\n")
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.verify_release(Path(temporary.name), sha)

    def test_release_worktree_must_belong_to_production_repository(self) -> None:
        temporary, sha = self.release_root()
        root = Path(temporary.name)
        target = root / "releases" / sha
        foreign = root / "foreign"
        subprocess.run(
            ["git", "clone", "-q", "--no-hardlinks", str(root / "repo"), str(foreign)],
            check=True,
        )
        shutil.rmtree(target)
        foreign.rename(target)
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.verify_release(root, sha)

    def test_successful_private_deployment_metadata_is_required(self) -> None:
        temporary, sha = self.release_root()
        root = Path(temporary.name)
        capacity_smoke.verify_metadata(root, sha)
        metadata = root / "releases" / f"{sha}.deploy-info"
        metadata.write_text(
            f"new_sha={sha}\nrevision_after=0032\nimage_ids=sha256:x\nstatus=failed\n"
        )
        metadata.chmod(0o600)
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.verify_metadata(root, sha)
        metadata.write_text(
            f"new_sha={sha}\nrevision_after=0032\nimage_ids=sha256:x\nstatus=success\n"
        )
        metadata.chmod(0o644)
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.verify_metadata(root, sha)
        metadata.write_bytes(b"\xff\xfe")
        metadata.chmod(0o600)
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.verify_metadata(root, sha)

    def test_capacity_paths_are_fixed_read_only_cache_bypasses(self) -> None:
        self.assertEqual(len(capacity_smoke.PATHS), 3)
        self.assertTrue(all("%" not in path and "_" not in path for path in capacity_smoke.PATHS))
        sample = capacity_smoke.request_once(
            self.base_url,
            capacity_smoke.PATHS[0],
            SHA,
            2,
        )
        self.assertTrue(sample.ok)

    def test_release_lock_is_non_blocking(self) -> None:
        temporary, _ = self.release_root()
        root = Path(temporary.name)
        with capacity_smoke.release_lock(root):
            with self.assertRaises(capacity_smoke.ConfigurationError):
                with capacity_smoke.release_lock(root):
                    pass

    def test_bounded_json_smoke_succeeds(self) -> None:
        result = capacity_smoke.run_smoke(
            origin=self.base_url,
            sha=SHA,
            requests=12,
            concurrency=2,
            rate=20,
            timeout=2,
            addresses=("127.0.0.1",),
        )
        self.assertEqual(result["phase"], "measured")
        self.assertEqual(result["successfulRequests"], 12)
        self.assertEqual(result["failedRequests"], 0)
        self.assertEqual(result["successRate"], 1.0)

    def test_redirect_is_not_followed(self) -> None:
        Handler.mode = "redirect"
        sample = capacity_smoke.request_once(self.base_url, "/api/health/live", SHA, 2)
        self.assertFalse(sample.ok)
        self.assertEqual(sample.status, 302)
        self.assertIn("redirects are disabled", sample.error or "")

    def test_absolute_deadline_rejects_slow_drip_response(self) -> None:
        Handler.mode = "slow"
        started = time.perf_counter()
        sample = capacity_smoke.request_once(
            self.base_url,
            "/api/health/live",
            SHA,
            0.2,
        )
        elapsed = time.perf_counter() - started
        self.assertFalse(sample.ok)
        self.assertIn("deadline", sample.error or "")
        self.assertLess(elapsed, 0.8)

    def test_absolute_deadline_includes_response_headers(self) -> None:
        Handler.mode = "slow_headers"
        started = time.perf_counter()
        sample = capacity_smoke.request_once(self.base_url, "/api/health/live", SHA, 0.2)
        self.assertFalse(sample.ok)
        self.assertLess(time.perf_counter() - started, 0.8)

    def test_non_json_response_fails_closed(self) -> None:
        Handler.mode = "html"
        sample = capacity_smoke.request_once(self.base_url, "/api/health/live", SHA, 2)
        self.assertFalse(sample.ok)
        self.assertIn("not JSON", sample.error or "")

    def test_hard_limits_reject_excess_load(self) -> None:
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.run_smoke(self.base_url, SHA, 1, 1, 1, 1, ())
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.run_smoke(
                origin=self.base_url,
                sha=SHA,
                requests=(capacity_smoke.MAX_TOTAL - len(capacity_smoke.PATHS)) + 1,
                concurrency=1,
                rate=1,
                timeout=1,
                addresses=("127.0.0.1",),
            )

    def test_worst_case_duration_is_bounded(self) -> None:
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.run_smoke(
                origin=self.base_url,
                sha=SHA,
                requests=(capacity_smoke.MAX_TOTAL - len(capacity_smoke.PATHS)),
                concurrency=1,
                rate=0.1,
                timeout=capacity_smoke.MAX_TIMEOUT,
                addresses=("127.0.0.1",),
            )
        accepted = capacity_smoke.validate_budget(
            requests=120,
            concurrency=4,
            rate=8,
            timeout=5,
        )
        self.assertLessEqual(accepted, capacity_smoke.MAX_LOCK_SECONDS)

    def test_total_request_budget_includes_warmup(self) -> None:
        result = capacity_smoke.run_smoke(
            origin=self.base_url,
            sha=SHA,
            requests=12,
            concurrency=2,
            rate=20,
            timeout=2,
            addresses=("127.0.0.1",),
        )
        self.assertEqual(result["warmupRequests"], len(capacity_smoke.PATHS))
        self.assertEqual(result["measuredRequests"], 12)
        self.assertEqual(result["totalRequests"], 12 + len(capacity_smoke.PATHS))
        self.assertLessEqual((capacity_smoke.MAX_TOTAL - len(capacity_smoke.PATHS)) + len(capacity_smoke.PATHS), capacity_smoke.MAX_TOTAL)

    def test_cli_has_no_loopback_bypass(self) -> None:
        self.assertNotIn("--allow-http-loopback", capacity_smoke.build_parser().format_help())

    def test_release_sha_confirmation_is_exact_and_lowercase(self) -> None:
        self.assertEqual(capacity_smoke.validate_sha(SHA, SHA), SHA)
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.validate_sha(SHA.upper(), SHA.upper())
        with self.assertRaises(capacity_smoke.ConfigurationError):
            capacity_smoke.validate_sha(SHA, "b" * 40)


if __name__ == "__main__":
    unittest.main()
