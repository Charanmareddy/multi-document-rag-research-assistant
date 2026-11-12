"""Overview, topic, relevance, and research-gap analytics."""

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.analytics.topic_analysis import topic_candidates
from backend.app.database.models import (
    Collection, Document, DocumentChunk, QueryCitation, QueryHistory, ResearchReport,
)
from backend.app.database.session import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _validate_collection(db: Session, collection_id: str) -> None:
    if db.get(Collection, collection_id) is None:
        raise HTTPException(404, "Collection not found")


@router.get("/overview")
def overview(collection_id: str | None = None, db: Session = Depends(get_db)) -> dict:
    if collection_id:
        _validate_collection(db, collection_id)
    document_query = select(Document)
    chunk_query = select(func.count(DocumentChunk.id)).select_from(DocumentChunk)
    collection_query = select(func.count(Collection.id))
    query_query = select(QueryHistory).order_by(QueryHistory.created_at.desc())
    report_query = select(ResearchReport).order_by(ResearchReport.created_at.desc())
    if collection_id:
        document_query = document_query.where(Document.collection_id == collection_id)
        chunk_query = chunk_query.where(DocumentChunk.collection_id == collection_id)
        collection_query = collection_query.where(Collection.id == collection_id)
        query_query = query_query.where(QueryHistory.collection_id == collection_id)
        report_query = report_query.where(ResearchReport.collection_id == collection_id)
    query_count_query = select(func.count(QueryHistory.id))
    report_count_query = select(func.count(ResearchReport.id))
    if collection_id:
        query_count_query = query_count_query.where(QueryHistory.collection_id == collection_id)
        report_count_query = report_count_query.where(ResearchReport.collection_id == collection_id)
    documents = db.scalars(document_query).all()
    status_counts = Counter(item.status for item in documents)
    return {
        "collections": db.scalar(collection_query) or 0,
        "documents": len(documents),
        "indexed_pages": sum(item.page_count or 0 for item in documents if item.status == "indexed"),
        "chunks": db.scalar(chunk_query) or 0,
        "query_count": db.scalar(query_count_query) or 0,
        "report_count": db.scalar(report_count_query) or 0,
        "processing_status": dict(status_counts),
        "recent_queries": [{"id": item.id, "question": item.question, "created_at": item.created_at}
                           for item in db.scalars(query_query.limit(10)).all()],
        "recent_reports": [{"id": item.id, "title": item.title, "created_at": item.created_at}
                           for item in db.scalars(report_query.limit(10)).all()],
    }


@router.get("/topics")
def topics(collection_id: str, limit: int = 20, db: Session = Depends(get_db)) -> dict:
    _validate_collection(db, collection_id)
    return {"collection_id": collection_id, "method": "distinctive TF-IDF terms over indexed retrieval chunks",
            "topics": topic_candidates(db, collection_id, min(max(limit, 1), 100)),
            "note": "Exploratory vocabulary candidates; human review is needed before treating these as research topics."}


@router.get("/document-relevance")
def document_relevance(collection_id: str, db: Session = Depends(get_db)) -> dict:
    _validate_collection(db, collection_id)
    documents = db.scalars(select(Document).where(Document.collection_id == collection_id)).all()
    counts = dict(db.execute(
        select(QueryCitation.document_id, func.count(QueryCitation.id))
        .join(Document, Document.id == QueryCitation.document_id)
        .where(Document.collection_id == collection_id)
        .group_by(QueryCitation.document_id)
    ).all())
    return {"collection_id": collection_id, "documents": [
        {"document_id": item.id, "document_name": item.name, "status": item.status,
         "query_citation_count": counts.get(item.id, 0), "page_count": item.page_count,
         "chunk_count": item.chunk_count}
        for item in sorted(documents, key=lambda document: counts.get(document.id, 0), reverse=True)
    ]}


@router.get("/research-gaps")
def research_gaps(collection_id: str, db: Session = Depends(get_db)) -> dict:
    _validate_collection(db, collection_id)
    unindexed = db.scalars(select(Document).where(
        Document.collection_id == collection_id, Document.status != "indexed"
    )).all()
    rare_terms = [item for item in topic_candidates(db, collection_id, 100) if item["document_count"] == 1][:20]
    return {
        "collection_id": collection_id,
        "indexing_gaps": [{"document_id": item.id, "document_name": item.name, "status": item.status}
                          for item in unindexed],
        "sparse_topic_candidates": rare_terms,
        "note": "Single-document vocabulary and unindexed files are review prompts, not evidence that a scientific question is unanswered.",
    }
