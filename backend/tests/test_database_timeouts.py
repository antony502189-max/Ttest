from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.db.session import database_server_settings

ROOT = Path(__file__).resolve().parents[2]


def test_database_server_settings_use_explicit_millisecond_values() -> None:
    settings = Settings(
        database_statement_timeout_ms=45_000,
        database_lock_timeout_ms=7_500,
    )

    assert database_server_settings(settings) == {
        "statement_timeout": "45000ms",
        "lock_timeout": "7500ms",
    }


def test_database_lock_timeout_must_be_shorter_than_statement_timeout() -> None:
    settings = Settings(
        app_env="test",
        database_statement_timeout_ms=10_000,
        database_lock_timeout_ms=10_000,
    )

    with pytest.raises(RuntimeError, match="lock timeout must be shorter than statement timeout"):
        settings.validate_runtime()


def test_production_files_wire_database_execution_budgets() -> None:
    compose = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")
    example = (ROOT / "deploy" / "production.env.example").read_text(encoding="utf-8")

    assert "DATABASE_STATEMENT_TIMEOUT_MS: ${DATABASE_STATEMENT_TIMEOUT_MS:-60000}" in compose
    assert "DATABASE_LOCK_TIMEOUT_MS: ${DATABASE_LOCK_TIMEOUT_MS:-10000}" in compose
    assert "DATABASE_STATEMENT_TIMEOUT_MS=60000" in example
    assert "DATABASE_LOCK_TIMEOUT_MS=10000" in example
