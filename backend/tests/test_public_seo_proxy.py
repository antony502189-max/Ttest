from pathlib import Path


def test_nginx_exposes_canonical_seo_documents_and_noindexes_private_routes() -> None:
    root = Path(__file__).resolve().parents[2]
    nginx = (root / "deploy" / "nginx.conf").read_text(encoding="utf-8")

    assert "habitacion/[0-9a-fA-F-]+" in nginx
    assert "sitemap\\.xml" in nginx
    assert "robots\\.txt" in nginx
    assert "proxy_pass http://backend:8000;" in nginx
    assert "add_header X-Robots-Tag $robots_tag always;" in nginx
    for path in ("acceso", "perfil", "mis-anuncios", "publicar", "admin"):
        assert path in nginx
