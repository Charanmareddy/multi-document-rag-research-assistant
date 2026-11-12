"""Evidence retrieval endpoints; answer generation is a later milestone."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.embeddings.providers import EmbeddingConfigurationError
from backend.app.retrieval.bm25_retriever import bm25_search
from backend.app.retrieval.dense_retriever import dense_search
from backend.app.retrieval.hybrid_retriever import hybrid_search
from backend.app.retrieval.models import SearchFilters
from backend.app.rag.citation_manager import InvalidCitationError
from backend.app.rag.query_engine import answer_question
from backend.app.vector_store.qdrant_store import QdrantConfigurationError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/research", tags=["research"])


class SearchRequest(BaseModel):
    """Collection-scoped evidence search request."""

    query: str = Field(min_length=2, max_length=4000)
    collection_id: str
    document_ids: list[str] = Field(default_factory=list, max_length=500)
    author: str | None = Field(default=None, max_length=500)
    mode: Literal["dense", "bm25", "hybrid"] = "hybrid"
    top_k: int = Field(default=10, ge=1, le=100)
    route_documents: bool = True


class ResearchQueryRequest(SearchRequest):
    """Grounded answer request with optional reranking."""

    rerank: bool = True


@router.post("/search")
def search_evidence(payload: SearchRequest, db: Session = Depends(get_db)) -> dict:
    """Return ranked source chunks without synthesizing an answer."""

    query = payload.query.strip()
    if len(query) < 2:
        raise HTTPException(422, "Query cannot be blank")
    filters = SearchFilters(collection_id=payload.collection_id,
                            document_ids=payload.document_ids, author=payload.author)
    try:
        if payload.mode == "bm25":
            results = bm25_search(db, query, filters, payload.top_k)
        elif payload.mode == "dense":
            results = dense_search(query, filters, payload.top_k)
        else:
            results = hybrid_search(db, query, filters, payload.top_k,
                                    route_documents=payload.route_documents)
    except (EmbeddingConfigurationError, QdrantConfigurationError) as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("Evidence retrieval failed")
        raise HTTPException(503, "Retrieval provider failed; check service configuration and logs") from exc
    return {"query": query, "mode": payload.mode, "results": [item.as_dict() for item in results]}


@router.post("/query")
def research_query(payload: ResearchQueryRequest, db: Session = Depends(get_db)) -> dict:
    """Answer a research question from retrieved, page-attributed evidence."""

    query = payload.query.strip()
    if len(query) < 2:
        raise HTTPException(422, "Query cannot be blank")
    filters = SearchFilters(collection_id=payload.collection_id,
                            document_ids=payload.document_ids, author=payload.author)
    try:
        return answer_question(db, query=query, filters=filters, mode=payload.mode,
                               top_k=payload.top_k, rerank=payload.rerank,
                               route_documents=payload.route_documents)
    except InvalidCitationError as exc:
        logger.warning("Rejected generated answer with invalid citations: %s", exc)
        raise HTTPException(502, "The model returned invalid source citations; retry the question") from exc
    except (EmbeddingConfigurationError, QdrantConfigurationError) as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("Research answer generation failed")
        raise HTTPException(503, "Research provider failed; check service configuration and logs") from exc
