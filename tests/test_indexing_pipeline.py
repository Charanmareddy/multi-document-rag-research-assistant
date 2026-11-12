"""Indexing pipeline tests with external embeddings and Qdrant replaced by fakes."""

from uuid import uuid4

import pymupdf
from fastapi.testclient import TestClient

from backend.app.database.models import Document, DocumentChunk, IndexingJob
from backend.app.database.session import SessionLocal
from backend.app.main import app
from backend.app.services import indexing
from backend.app.api.routes import collections as collection_routes


class FakeEmbeddingProvider:
    identity = "test:three-dimensional"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0, 0.5] for text in texts]


class FakeVectorClient:
    def close(self) -> None:
        pass


def test_indexing_persists_chunks_and_page_provenance(monkeypatch) -> None:
    monkeypatch.setattr(indexing, "get_embedding_provider", lambda: FakeEmbeddingProvider())
    monkeypatch.setattr(indexing, "create_client", lambda: FakeVectorClient())
    monkeypatch.setattr(indexing, "ensure_collection", lambda client, dimension: None)
    monkeypatch.setattr(indexing, "delete_document_points", lambda client, document_id: None)
    upserted: list[dict] = []
    monkeypatch.setattr(indexing, "upsert_chunks", lambda client, records, vectors: upserted.extend(records))
    monkeypatch.setattr(collection_routes, "delete_document_vectors", lambda document_id: None)

    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "RESEARCH FINDINGS\n" + "verified source evidence " * 45)
    payload = pdf.tobytes()
    pdf.close()

    with TestClient(app) as client:
        collection = client.post("/api/v1/collections", json={"name": f"index-{uuid4()}"}).json()
        upload = client.post("/api/v1/documents/upload", files={
            "collection_id": (None, collection["id"]),
            "files": ("evidence.pdf", payload, "application/pdf"),
        }).json()["results"][0]["document"]

        job_id = str(uuid4())
        with SessionLocal() as db:
            db.add(IndexingJob(id=job_id, collection_id=collection["id"], status="queued", total_documents=1))
            db.commit()

        indexing.run_index_job(job_id, [upload["id"]])

        with SessionLocal() as db:
            indexed = db.get(Document, upload["id"])
            job = db.get(IndexingJob, job_id)
            chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == upload["id"]).all()
            assert indexed.status == "indexed"
            assert indexed.page_count == 1
            assert indexed.chunk_count > 0
            assert job.status == "completed"
            assert job.elapsed_ms is not None
            assert job.embedding_ms >= 0
            assert len(chunks) == len(upserted)
            retrieval_chunks = [chunk for chunk in chunks if chunk.level == "retrieval"]
            assert retrieval_chunks
            assert all(chunk.page_number == 1 for chunk in retrieval_chunks)
            client.delete(f"/api/v1/collections/{collection['id']}")
