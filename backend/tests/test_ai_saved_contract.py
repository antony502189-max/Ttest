"""Production release paths cannot silently downgrade the retained AI schema."""
import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize("target,command", [
    ("deploy/deploy-release.sh", "alembic downgrade -1"),
    ("deploy/rollback-release.sh", "alembic -c backend/alembic.ini downgrade 0073_ai_command_seed"),
    ("deploy/rollback-release.sh", "alembic \\\n downgrade -1"),
    ("docker-compose.production.yml", 'command: ["alembic", "downgrade", "-1"]'),
])
def test_production_safety_rejects_schema_downgrade(monkeypatch, target, command):
    root = Path(__file__).parents[2]
    monkeypatch.chdir(root)
    original = Path.read_text
    def altered_read(path, *args, **kwargs):
        source = original(path, *args, **kwargs)
        return source + "\n" + command if path == Path(target) else source
    monkeypatch.setattr(Path, "read_text", altered_read)
    with pytest.raises(SystemExit, match="production must never run Alembic downgrade"):
        runpy.run_path(str(root / "scripts/check-deploy-safety.py"))
