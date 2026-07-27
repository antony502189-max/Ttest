from fastapi.testclient import TestClient

from app.main import app


def test_live_and_openapi_are_available() -> None:
    client = TestClient(app)
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/api/openapi.json").status_code == 200
