"""Basic health endpoint tests."""

from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_endpoint_reports_ready() -> None:
    """The initial API exposes a stable health contract."""

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "service" in response.json()


def test_settings_status_does_not_expose_secrets() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/settings")

    assert response.status_code == 200
    assert "api_key" not in response.text.lower()
    assert "configured" in response.json()["llm"]
