from __future__ import annotations

import pytest

from app.core.config import Settings
from app.db.session import database_server_settings


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
