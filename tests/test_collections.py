"""Collection and document ingestion endpoint tests."""

from io import BytesIO
from uuid import uuid4
import zipfile

import fitz
from fastapi.testclient import TestClient

from backend.app.main import app


def make_pdf(text: str = "research evidence") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    payload = doc.tobytes()
    doc.close()
    return payload


def test_collection_upload_duplicate_and_delete_document() -> None:
    with TestClient(app) as client:
        created = client.post("/api/v1/collections", json={"name": f"test-{uuid4()}"})
        assert created.status_code == 201
        collection_id = created.json()["id"]
        body = {"collection_id": (None, collection_id), "files": ("study.pdf", make_pdf(), "application/pdf")}
        first = client.post("/api/v1/documents/upload", files=body)
        assert first.status_code == 201
        uploaded = first.json()["results"][0]
        assert uploaded["document"]["page_count"] == 1
        assert uploaded["duplicate"] is False

        second = client.post("/api/v1/documents/upload", files=body)
        assert second.json()["results"][0]["duplicate"] is True

        document_id = uploaded["document"]["id"]
        assert client.delete(f"/api/v1/documents/{document_id}").status_code == 204
        assert client.get(f"/api/v1/documents/{document_id}").status_code == 404
        assert client.delete(f"/api/v1/collections/{collection_id}").status_code == 204


def test_zip_upload_rejects_path_traversal() -> None:
    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("../escape.pdf", make_pdf())
        archive.writestr("safe.pdf", make_pdf("safe"))
    with TestClient(app) as client:
        collection = client.post("/api/v1/collections", json={"name": f"zip-{uuid4()}"}).json()
        response = client.post("/api/v1/documents/upload-zip", data={"collection_id": collection["id"]},
                               files={"file": ("batch.zip", archive_buffer.getvalue(), "application/zip")})
        assert response.status_code == 201
        results = response.json()["results"]
        assert results[0]["error"] == "Unsafe archive path"
        assert results[1]["document"]["name"] == "safe.pdf"
        client.delete(f"/api/v1/collections/{collection['id']}")
