"""Dependency-light BM25 ranking over stored retrieval chunks."""

import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models import Document, DocumentChunk
from backend.app.retrieval.models import Evidence, SearchFilters

TOKEN = re.compile(r"[\w]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Normalize text to case-folded word tokens."""

    return [token.casefold() for token in TOKEN.findall(text)]


def bm25_search(db: Session, query: str, filters: SearchFilters, top_k: int = 20,
                *, level: str = "retrieval") -> list[Evidence]:
    """Rank matching chunks with Okapi BM25, preserving page/source metadata."""

    tokens = tokenize(query)
    if not tokens:
        return []
    statement = (
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.collection_id == filters.collection_id, DocumentChunk.level == level)
    )
    if filters.document_ids:
        statement = statement.where(DocumentChunk.document_id.in_(filters.document_ids))
    if filters.author:
        statement = statement.where(Document.author.ilike(f"%{filters.author}%"))
    rows = db.execute(statement).all()
    if not rows:
        return []

    docs = [tokenize(chunk.text) for chunk, _ in rows]
    avg_length = sum(map(len, docs)) / len(docs) or 1.0
    doc_frequency: dict[str, int] = {}
    for terms in docs:
        for term in set(terms):
            doc_frequency[term] = doc_frequency.get(term, 0) + 1
    scores = []
    k1, b = 1.5, 0.75
    for (chunk, document), terms in zip(rows, docs, strict=True):
        frequencies: dict[str, int] = {}
        for term in terms:
            frequencies[term] = frequencies.get(term, 0) + 1
        score = 0.0
        for term in tokens:
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            df = doc_frequency.get(term, 0)
            inverse = math.log(1 + (len(rows) - df + 0.5) / (df + 0.5))
            denom = frequency + k1 * (1 - b + b * len(terms) / avg_length)
            score += inverse * frequency * (k1 + 1) / denom
        if score > 0:
            scores.append((score, chunk, document))
    scores.sort(key=lambda item: item[0], reverse=True)
    return [
        Evidence(
            chunk_id=chunk.id,
            document_id=document.id,
            document_name=document.name,
            collection_id=chunk.collection_id,
            text=chunk.text,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            author=document.author,
            score=score,
            bm25_score=score,
        )
        for score, chunk, document in scores[:top_k]
    ]
