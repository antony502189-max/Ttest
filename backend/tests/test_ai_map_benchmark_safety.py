"""The optional benchmark must reject other databases before Alembic starts."""
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def benchmark():
    path = Path(__file__).parents[2] / "scripts/benchmark-ai-map.py"
    spec = importlib.util.spec_from_file_location("ai_map_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("field,value", [
    ("R01_DISPOSABLE_LAB", ""),
    ("DATABASE_URL", "postgresql+asyncpg://example:unused@app-db/application"),
    ("APP_ENV", "production"),
])
async def test_initialize_rejects_unsafe_environment_before_migration(benchmark, monkeypatch, field, value):
    monkeypatch.setenv("R01_DISPOSABLE_LAB", "synthetic-only")
    monkeypatch.setenv("DATABASE_URL", benchmark.DSN)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(field, value)
    process = AsyncMock()
    monkeypatch.setattr(benchmark.asyncio, "create_subprocess_exec", process)
    with pytest.raises(RuntimeError):
        await benchmark.initialize(2)
    process.assert_not_called()


def test_only_fixed_lab_database_is_accepted(benchmark, monkeypatch):
    monkeypatch.setenv("R01_DISPOSABLE_LAB", "synthetic-only")
    monkeypatch.setenv("DATABASE_URL", benchmark.DSN)
    monkeypatch.setenv("APP_ENV", "test")
    benchmark.validate_lab_environment()
