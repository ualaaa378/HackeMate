from fastapi.testclient import TestClient

from app.main import app


def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["version"]
