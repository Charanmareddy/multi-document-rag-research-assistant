"""Report export and collection analytics tests."""

from io import BytesIO
from uuid import uuid4

from docx import Document as DocxDocument
from fastapi.testclient import TestClient

from backend.app.api.routes import reports as report_routes
from backend.app.database.models import Collection, Document, DocumentChunk, QueryCitation, QueryHistory, ResearchReport
from backend.app.database.session import SessionLocal
from backend.app.main import app


def test_report_history_docx_download_and_analytics(monkeypatch) -> None:
    with TestClient(app) as client:
        collection_id = str(uuid4())
        document_id = str(uuid4())
        with SessionLocal() as db:
            db.add(Collection(id=collection_id, name=f"report-{collection_id}"))
            db.flush()
            db.add(Document(id=document_id, collection_id=collection_id, name="study.pdf",
                            sha256="c" * 64, file_path="unused.pdf", file_size=300,
                            page_count=3, author="Researcher", status="indexed", chunk_count=1))
            db.flush()
            db.add(DocumentChunk(id=str(uuid4()), document_id=document_id, collection_id=collection_id,
                                 chunk_key="retrieval:0", chunk_index=0, level="retrieval", page_number=2,
                                 text="Neural networks improve research model predictions."))
            db.commit()

        monkeypatch.setattr(report_routes, "answer_question", lambda *args, **kwargs: {
            "answer": "The study reports improved model predictions [S1].",
            "citations": [{"source_id": "S1", "document_id": document_id,
                           "document_name": "study.pdf", "page_number": 2,
                           "section_title": "Results", "excerpt": "Neural networks improve research model predictions."}],
            "agreements": [], "contradictions": [], "caveats": [],
            "retrieval_mode": "bm25", "timings_ms": {"retrieval": 1.0},
        })
        generated = client.post("/api/v1/reports/generate", json={
            "query": "What did the study find?", "collection_id": collection_id,
            "mode": "bm25", "title": "Study findings", "rerank": False,
        })
        assert generated.status_code == 201
        report = generated.json()
        assert report["content"]["references"][0]["page_number"] == 2
        report_id = report["id"]

        history = client.get("/api/v1/reports", params={"collection_id": collection_id})
        assert history.status_code == 200
        assert history.json()[0]["id"] == report_id
        detail = client.get(f"/api/v1/reports/{report_id}")
        assert detail.status_code == 200
        download = client.get(f"/api/v1/reports/{report_id}/download")
        assert download.status_code == 200
        docx = DocxDocument(BytesIO(download.content))
        assert any("Study findings" in paragraph.text for paragraph in docx.paragraphs)
        assert any("page 2" in paragraph.text for paragraph in docx.paragraphs)

        overview = client.get("/api/v1/analytics/overview", params={"collection_id": collection_id}).json()
        assert overview["documents"] == 1
        assert overview["indexed_pages"] == 3
        assert overview["chunks"] == 1
        assert overview["recent_reports"][0]["id"] == report_id
        relevance = client.get("/api/v1/analytics/document-relevance", params={"collection_id": collection_id}).json()
        assert relevance["documents"][0]["query_citation_count"] == 1
        topics = client.get("/api/v1/analytics/topics", params={"collection_id": collection_id}).json()
        assert topics["topics"]
        gaps = client.get("/api/v1/analytics/research-gaps", params={"collection_id": collection_id}).json()
        assert gaps["indexing_gaps"] == []

        with SessionLocal() as db:
            row = db.get(ResearchReport, report_id)
            path = row.docx_path
            query_ids = [item.id for item in db.query(QueryHistory).filter(QueryHistory.collection_id == collection_id).all()]
            for query_id in query_ids:
                db.query(QueryCitation).filter(QueryCitation.query_id == query_id).delete()
            db.query(QueryHistory).filter(QueryHistory.collection_id == collection_id).delete()
            db.delete(row)
            db.query(DocumentChunk).filter(DocumentChunk.collection_id == collection_id).delete()
            db.query(Document).filter(Document.collection_id == collection_id).delete()
            db.query(Collection).filter(Collection.id == collection_id).delete()
            db.commit()
        from pathlib import Path
        Path(path).unlink(missing_ok=True)
