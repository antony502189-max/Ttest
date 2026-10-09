from pathlib import Path
from types import SimpleNamespace

import pytest

import app.commands.enforce_long_term_price_policy as cleanup
from app.commands.enforce_long_term_price_policy import save_private_text


def test_private_cleanup_artifacts_do_not_overwrite_existing_reports(tmp_path: Path):
    directory = tmp_path / "reports"
    directory.mkdir()
    directory.chmod(0o755)
    existing = directory / "manifest.json"
    existing.write_text("keep exact original manifest", encoding="utf-8")

    with pytest.raises(FileExistsError):
        save_private_text(existing, "new contents")

    assert existing.read_text(encoding="utf-8") == "keep exact original manifest"
    assert directory.stat().st_mode & 0o777 == 0o755


def test_private_cleanup_reports_are_created_with_restricted_permissions(tmp_path: Path):
    target = tmp_path / "new-private-report.json"
    save_private_text(target, '{"readOnly": true}')
    assert target.read_text(encoding="utf-8") == '{"readOnly": true}'
    assert target.stat().st_mode & 0o077 == 0


@pytest.mark.asyncio
async def test_existing_apply_output_blocks_mutation_before_opening_database(monkeypatch, tmp_path: Path):
    manifest = tmp_path / "existing-apply.json"
    manifest.write_text('{"preserve":"old receipt"}', encoding="utf-8")

    def forbidden_session_factory():
        raise AssertionError("A pre-existing report must reject apply before opening the database")

    monkeypatch.setattr(cleanup, "SessionLocal", forbidden_session_factory)
    with pytest.raises(FileExistsError):
        await cleanup.execute(SimpleNamespace(output=manifest, apply=True))
    assert manifest.read_text(encoding="utf-8") == '{"preserve":"old receipt"}'
