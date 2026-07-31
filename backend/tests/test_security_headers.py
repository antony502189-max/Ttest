from app.main import SECURITY_HEADERS


def test_production_security_headers_do_not_allow_cross_origin_resources():
    assert SECURITY_HEADERS["Cross-Origin-Resource-Policy"] == "same-origin"
