from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_is_live_without_database() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "exprofit-api"}


def test_root_describes_api_endpoints() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["health"] == "/health"
    assert response.json()["docs"] == "/docs"
