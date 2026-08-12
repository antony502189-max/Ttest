from __future__ import annotations

import re
from pathlib import Path

from app.core.config import SUPPORTED_EXTERNAL_IMPORT_SOURCES, Settings


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def test_external_import_source_defaults_stay_aligned() -> None:
    """Keep every versioned production fallback on the same provider roster."""
    root = Path(__file__).resolve().parents[2]

    default_value = Settings.model_fields["external_import_sources"].default
    assert isinstance(default_value, str)
    expected = _csv(default_value)
    assert expected
    assert set(expected) <= SUPPORTED_EXTERNAL_IMPORT_SOURCES

    backend_env = (root / "backend" / ".env.example").read_text(encoding="utf-8")
    env_match = re.search(r"^EXTERNAL_IMPORT_SOURCES=(.+)$", backend_env, re.MULTILINE)
    assert env_match is not None
    assert _csv(env_match.group(1)) == expected

    compose = (root / "docker-compose.production.yml").read_text(encoding="utf-8")
    compose_match = re.search(
        r"EXTERNAL_IMPORT_SOURCES:\s*\$\{EXTERNAL_IMPORT_SOURCES:-([^}]+)\}",
        compose,
    )
    assert compose_match is not None
    assert _csv(compose_match.group(1)) == expected

    monitor = (root / "deploy" / "production-monitor-check.sh").read_text(encoding="utf-8")
    monitor_match = re.search(
        r"configured_sources=\"\$\(env_value EXTERNAL_IMPORT_SOURCES '([^']+)'\)\"",
        monitor,
    )
    assert monitor_match is not None
    assert _csv(monitor_match.group(1)) == expected
