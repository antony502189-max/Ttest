"""Owned host reconcile and redacted monitoring; never crawls or spends on AI."""

import argparse
import importlib.util
import json
import os
import subprocess
from pathlib import Path

ROOT = Path("/srv/112233-ai-site-pilot-20261108")
BACKEND = "ttest-ai-site-pilot-20261108-backend-1"
PRIMARY = "ttest-production-postgres-1"


def run(argv, payload=None):
    result = subprocess.run(
        argv,
        input=payload,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=90,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("PILOT_REFRESH_SUBPROCESS_FAILED")
    return result.stdout


def configured_health():
    directory = ROOT / "catalog-refresh"
    spec = importlib.util.spec_from_file_location(
        "pilot_catalog_health", directory / "catalog_health.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    purpose = run(
        [
            "docker",
            "inspect",
            BACKEND,
            "--format",
            '{{index .Config.Labels "es.ttest.purpose"}}',
        ]
    ).strip()
    if purpose != "ai-site-pilot-20261108" or not (
        ROOT / "owner-purpose"
    ).read_text().startswith("ai-site-pilot-20261108;"):
        raise RuntimeError("PILOT_REFRESH_OWNER_MISMATCH")
    mounts = json.loads(
        run(["docker", "inspect", BACKEND, "--format", "{{json .Mounts}}"])
    )
    state = next(m for m in mounts if m["Destination"] == "/demo-state")
    if (
        state["Type"] != "volume"
        or state["Name"] != "ttest-ai-site-pilot-20261108_state"
    ):
        raise RuntimeError("PILOT_REFRESH_OWNER_MISMATCH")
    original = json.loads(
        (ROOT / "deploy/ai-site-pilot/private/catalog.json").read_text()
    )
    return module.CatalogHealth(
        Path(state["Source"]) / "catalog-health.json",
        module.cohort_hash(original),
        uid=999,
    )


def collect(health):
    # This endpoint is loopback-only inside the private backend. No public route.
    available = 1
    try:
        metrics = run(
            [
                "docker",
                "exec",
                BACKEND,
                "python",
                "-c",
                'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:8000/private-metrics",timeout=3).read().decode())',
            ]
        )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        metrics = ""
        available = 0
    safe = (
        "\n".join(
            line for line in metrics.splitlines() if line.startswith("ttest_ai_voice_")
        )
        + "\n"
    )
    directory = ROOT / "catalog-refresh/metrics"
    directory.mkdir(exist_ok=True)
    temporary = directory / "health.prom.tmp"
    temporary.write_text(
        health.metrics() + f"ttest_pilot_voice_metrics_available {available}\n" + safe
    )
    os.chmod(temporary, 0o644)
    os.replace(temporary, directory / "health.prom")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--failure", action="store_true")
    parser.add_argument("--metrics-only", action="store_true")
    args = parser.parse_args(argv)
    health = configured_health()
    # Serialize the host runner/OnFailure callback; the backend also uses a PG
    # advisory lock plus the publication token, so a dead worker cannot publish.
    lock = type(health)(ROOT / "catalog-refresh/runner.json", health.cohort_hash)
    with lock._locked():
        if args.failure:
            health.fail()
            collect(health)
            print("PILOT_CATALOG_REFRESH_FAILED_CATALOG_BLOCKED", flush=True)
            return
        if args.metrics_only:
            collect(health)
            return
        token = health.begin()
        try:
            directory = ROOT / "catalog-refresh"
            exporter = (directory / "export_public.py").read_text()
            updater = (directory / "refresh.py").read_text()
            sql = run(
                [
                    "docker",
                    "exec",
                    "-i",
                    BACKEND,
                    "python",
                    "-c",
                    exporter,
                    "--cohort",
                    "/demo-input/catalog.json",
                    "--sql-only",
                ]
            )
            incoming = run(
                [
                    "docker",
                    "exec",
                    "-i",
                    PRIMARY,
                    "sh",
                    "-c",
                    'exec psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
                ],
                sql,
            )
            value = json.loads(incoming)
            if (
                value.get("schema") != "pilot-cohort.v2"
                or not isinstance(value.get("records"), list)
                or not 0 <= len(value["records"]) <= 20
            ):
                raise ValueError("PILOT_REFRESH_RECEIPT_INVALID")
            summary = run(
                [
                    "docker",
                    "exec",
                    "-i",
                    BACKEND,
                    "python",
                    "-c",
                    updater,
                    "-",
                    "--token",
                    token,
                ],
                incoming,
            )
            collect(health)
            print(summary.strip())
        except BaseException:  # noqa: BLE001 - cancellation must also close publication
            health.fail(token)
            try:
                collect(health)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                print("PILOT_METRICS_EXPORT_FAILED", flush=True)
            print("PILOT_CATALOG_REFRESH_FAILED_CATALOG_BLOCKED", flush=True)
            raise SystemExit(1) from None


if __name__ == "__main__":
    main()
