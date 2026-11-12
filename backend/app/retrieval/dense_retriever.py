"""Qdrant vector similarity retrieval."""

from backend.app.embeddings.providers import get_embedding_provider
from backend.app.retrieval.models import Evidence, SearchFilters
from backend.app.vector_store.qdrant_store import COLLECTION_NAME, create_client


def dense_search(query: str, filters: SearchFilters, top_k: int = 20) -> list[Evidence]:
    """Retrieve semantically similar retrieval-level chunks with metadata filters."""

    client = create_client()
    try:
        from qdrant_client.http import models

        if not client.collection_exists(COLLECTION_NAME):
            return []
        conditions = [
            models.FieldCondition(key="collection_id", match=models.MatchValue(value=filters.collection_id)),
            models.FieldCondition(key="level", match=models.MatchValue(value="retrieval")),
        ]
        if filters.document_ids:
            conditions.append(models.FieldCondition(
                key="document_id", match=models.MatchAny(any=filters.document_ids)
            ))
        if filters.author:
            conditions.append(models.FieldCondition(
                key="document_author", match=models.MatchValue(value=filters.author)
            ))
        vector = get_embedding_provider().embed_query(query)
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            query_filter=models.Filter(must=conditions),
            limit=top_k,
            with_payload=True,
        )
        evidence = []
        for point in response.points:
            payload = point.payload or {}
            evidence.append(Evidence(
                chunk_id=str(payload.get("chunk_id", point.id)),
                document_id=str(payload["document_id"]),
                document_name=str(payload["document_name"]),
                collection_id=str(payload["collection_id"]),
                text=str(payload["text"]),
                page_number=payload.get("page_number"),
                section_title=payload.get("section_title"),
                author=payload.get("document_author"),
                score=float(point.score),
                dense_score=float(point.score),
            ))
        return evidence
    finally:
        client.close()
