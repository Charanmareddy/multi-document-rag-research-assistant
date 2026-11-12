"""Basic health endpoint tests."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from backend.app.database.migrations import initialize_schema
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


def test_schema_bootstrap_adds_index_timing_columns_to_older_db() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("""CREATE TABLE indexing_jobs (
            id VARCHAR(36) PRIMARY KEY, collection_id VARCHAR(36), status VARCHAR(30),
            total_documents INTEGER, processed_documents INTEGER, failed_documents INTEGER,
            error TEXT, created_at DATETIME, updated_at DATETIME
        )""")

    initialize_schema(engine)

    columns = {item["name"] for item in inspect(engine).get_columns("indexing_jobs")}
    assert {"started_at", "finished_at", "elapsed_ms", "extraction_ms", "embedding_ms", "vector_store_ms"} <= columns
    engine.dispose()
