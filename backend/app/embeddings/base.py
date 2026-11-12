"""Embedding contract shared by providers."""

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Provider methods required by the indexer and query engine."""

    @property
    def identity(self) -> str: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...
