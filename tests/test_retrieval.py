"""Lexical retrieval and rank fusion tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.database.models import Collection, Document, DocumentChunk
from backend.app.database.session import SessionLocal
from backend.app.main import app
from backend.app.retrieval.bm25_retriever import bm25_search
from backend.app.retrieval.hybrid_retriever import reciprocal_rank_fusion
from backend.app.retrieval.models import Evidence, SearchFilters


def test_bm25_finds_terms_and_respects_document_filter() -> None:
    with TestClient(app) as client:
        collection_id = str(uuid4())
        doc_a = str(uuid4())
        doc_b = str(uuid4())
        with SessionLocal() as db:
            db.add(Collection(id=collection_id, name=f"retrieval-{collection_id}"))
            db.flush()
            db.add_all([
                Document(id=doc_a, collection_id=collection_id, name="amyloid.pdf", sha256="a" * 64,
                         file_path="unused-a.pdf", file_size=100, author="Researcher One", status="indexed"),
                Document(id=doc_b, collection_id=collection_id, name="climate.pdf", sha256="b" * 64,
                         file_path="unused-b.pdf", file_size=100, author="Researcher Two", status="indexed"),
            ])
            db.flush()
            db.add_all([
                DocumentChunk(id=str(uuid4()), document_id=doc_a, collection_id=collection_id,
                              chunk_key="retrieval:0", chunk_index=0, level="retrieval", page_number=4,
                              text="amyloid protein associated with elevated clinical risk"),
                DocumentChunk(id=str(uuid4()), document_id=doc_b, collection_id=collection_id,
                              chunk_key="retrieval:0", chunk_index=0, level="retrieval", page_number=1,
                              text="climate temperature measurements and regional change"),
            ])
            db.commit()
            results = bm25_search(db, "amyloid protein risk", SearchFilters(collection_id), top_k=5)
            assert results[0].document_id == doc_a
            assert results[0].page_number == 4
            response = client.post("/api/v1/research/search", json={
                "query": "amyloid protein risk", "collection_id": collection_id,
                "mode": "bm25", "top_k": 5,
            })
            assert response.status_code == 200
            assert response.json()["results"][0]["document_id"] == doc_a
            filtered = bm25_search(db, "amyloid protein risk", SearchFilters(collection_id, [doc_b]), top_k=5)
            assert filtered == []
            db.query(DocumentChunk).filter(DocumentChunk.collection_id == collection_id).delete()
            db.query(Document).filter(Document.collection_id == collection_id).delete()
            db.query(Collection).filter(Collection.id == collection_id).delete()
            db.commit()


def evidence(chunk_id: str, score: float) -> Evidence:
    return Evidence(chunk_id, "doc", "source.pdf", "collection", "evidence", 2,
                    None, None, score)


def test_rrf_merges_ranked_lists_without_raw_score_comparison() -> None:
    dense = [evidence("a", 0.11), evidence("b", 0.99)]
    dense[0].dense_score = 0.11
    dense[1].dense_score = 0.99
    lexical = [evidence("b", 18.0), evidence("c", 12.0)]
    lexical[0].bm25_score = 18.0
    lexical[1].bm25_score = 12.0

    fused = reciprocal_rank_fusion(dense, lexical, limit=3)

    assert fused[0].chunk_id == "b"
    assert fused[0].dense_score == 0.99
    assert fused[0].bm25_score == 18.0
    assert len(fused) == 3
