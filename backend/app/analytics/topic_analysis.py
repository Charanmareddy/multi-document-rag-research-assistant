"""Frequency and TF-IDF topic candidates based on indexed text."""

import math
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models import Document, DocumentChunk
from backend.app.retrieval.bm25_retriever import tokenize

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "by", "for", "from",
    "had", "has", "have", "if", "in", "into", "is", "it", "its", "may", "not", "of",
    "on", "or", "our", "than", "that", "the", "their", "there", "these", "this", "those",
    "to", "was", "were", "what", "when", "where", "which", "who", "will", "with", "we",
    "study", "paper", "results", "conclusion", "introduction", "methods", "data", "figure",
}


def topic_candidates(db: Session, collection_id: str, limit: int = 20) -> list[dict]:
    """Rank recurring distinctive terms; candidates are exploratory signals, not verified topics."""

    statement = (
        select(Document.id, Document.name, DocumentChunk.text)
        .join(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.collection_id == collection_id, DocumentChunk.level == "retrieval")
    )
    rows = db.execute(statement).all()
    per_document: dict[str, Counter] = {}
    names: dict[str, str] = {}
    for document_id, name, text in rows:
        names[document_id] = name
        terms = [token for token in tokenize(text) if len(token) > 2 and token not in STOP_WORDS and not token.isdigit()]
        per_document.setdefault(document_id, Counter()).update(terms)
    if not per_document:
        return []
    totals = Counter()
    doc_frequency = Counter()
    for counts in per_document.values():
        totals.update(counts)
        doc_frequency.update(counts.keys())
    number_documents = len(per_document)
    ranked = []
    for term, total_frequency in totals.items():
        df = doc_frequency[term]
        idf = math.log((number_documents + 1) / (df + 1)) + 1
        score = sum((count / sum(counts.values())) * idf for counts in per_document.values()
                    if (count := counts.get(term, 0)))
        ranked.append({"term": term, "score": round(score, 6), "document_count": df,
                       "document_names": [names[doc_id] for doc_id, counts in per_document.items() if term in counts],
                       "frequency": total_frequency})
    return sorted(ranked, key=lambda item: item["score"], reverse=True)[:limit]
