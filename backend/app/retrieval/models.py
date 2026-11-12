"""Shared retrieval data structures."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class SearchFilters:
    """Optional metadata constraints for retrieval."""

    collection_id: str
    document_ids: list[str] = field(default_factory=list)
    author: str | None = None


@dataclass(slots=True)
class Evidence:
    """Retrieved page-grounded chunk and ranking metadata."""

    chunk_id: str
    document_id: str
    document_name: str
    collection_id: str
    text: str
    page_number: int | None
    section_title: str | None
    author: str | None
    score: float
    dense_score: float | None = None
    bm25_score: float | None = None

    def as_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "collection_id": self.collection_id,
            "text": self.text,
            "page_number": self.page_number,
            "section_title": self.section_title,
            "author": self.author,
            "score": self.score,
            "dense_score": self.dense_score,
            "bm25_score": self.bm25_score,
        }
