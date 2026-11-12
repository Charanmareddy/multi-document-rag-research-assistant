"""Reciprocal rank fusion and document-level routing."""

from collections import defaultdict

from sqlalchemy.orm import Session

from backend.app.retrieval.bm25_retriever import bm25_search
from backend.app.retrieval.dense_retriever import dense_search
from backend.app.retrieval.models import Evidence, SearchFilters


def reciprocal_rank_fusion(*ranked_lists: list[Evidence], limit: int = 20,
                           constant: int = 60) -> list[Evidence]:
    """Fuse rankings without comparing incomparable raw dense/BM25 scores."""

    fused: dict[str, Evidence] = {}
    fusion_scores: defaultdict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, evidence in enumerate(ranked, start=1):
            fusion_scores[evidence.chunk_id] += 1.0 / (constant + rank)
            existing = fused.get(evidence.chunk_id)
            if existing:
                existing.dense_score = evidence.dense_score or existing.dense_score
                existing.bm25_score = evidence.bm25_score or existing.bm25_score
            else:
                fused[evidence.chunk_id] = evidence
    for chunk_id, evidence in fused.items():
        evidence.score = fusion_scores[chunk_id]
    return sorted(fused.values(), key=lambda item: item.score, reverse=True)[:limit]


def hybrid_search(db: Session, query: str, filters: SearchFilters, top_k: int = 20,
                  *, route_documents: bool = True) -> list[Evidence]:
    """Route to likely documents using overview text, then fuse dense and BM25 ranks."""

    routed_filters = filters
    if route_documents and not filters.document_ids:
        overview_hits = bm25_search(db, query, filters, top_k=8, level="document")
        selected_ids = list(dict.fromkeys(hit.document_id for hit in overview_hits))
        if selected_ids:
            routed_filters = SearchFilters(
                collection_id=filters.collection_id,
                document_ids=selected_ids,
                author=filters.author,
            )
    dense = dense_search(query, routed_filters, top_k=max(top_k, 20))
    lexical = bm25_search(db, query, routed_filters, top_k=max(top_k, 20))
    return reciprocal_rank_fusion(dense, lexical, limit=top_k)
