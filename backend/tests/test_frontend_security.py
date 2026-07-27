from pathlib import Path


def test_frontend_does_not_ship_demo_passwords_or_persist_passwords():
    source_root = Path(__file__).resolve().parents[2] / "src"
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_root.rglob("*.ts*"))

    assert "demo112233" not in source
    assert "localStorage.setItem('password'" not in source
    assert 'localStorage.setItem("password"' not in source
