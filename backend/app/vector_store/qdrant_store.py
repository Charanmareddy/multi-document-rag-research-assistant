"""Persistent Qdrant adapter for local or server deployments."""

from uuid import UUID

from backend.app.core.config import get_settings

COLLECTION_NAME = "research_chunks"


class QdrantConfigurationError(RuntimeError):
    """Raised when Qdrant is unavailable or index dimensions conflict."""


def create_client():
    """Create a Qdrant client from local path or server settings."""

    settings = get_settings()
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise QdrantConfigurationError("Install qdrant-client to enable vector indexing") from exc
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    settings.qdrant_path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(settings.qdrant_path))


def ensure_collection(client, dimension: int) -> None:
    from qdrant_client.http import models

    if client.collection_exists(COLLECTION_NAME):
        info = client.get_collection(COLLECTION_NAME)
        vectors = info.config.params.vectors
        existing_dimension = vectors.size if hasattr(vectors, "size") else None
        if existing_dimension and existing_dimension != dimension:
            raise QdrantConfigurationError(
                f"Qdrant collection uses {existing_dimension}-dimensional vectors; configured embeddings return {dimension}. Re-index explicitly with a fresh collection."
            )
        return
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
    )


def upsert_chunks(client, records: list[dict], vectors: list[list[float]]) -> None:
    from qdrant_client.http import models

    points = [
        models.PointStruct(
            id=str(UUID(record["id"])),
            vector=vector,
            payload={key: value for key, value in record.items() if key != "id"},
        )
        for record, vector in zip(records, vectors, strict=True)
    ]
    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)


def delete_document_points(client, document_id: str) -> None:
    from qdrant_client.http import models

    if not client.collection_exists(COLLECTION_NAME):
        return
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))])
        ),
        wait=True,
    )


def delete_document_vectors(document_id: str) -> None:
    """Delete all indexed points for one source document."""

    client = create_client()
    try:
        delete_document_points(client, document_id)
    finally:
        client.close()
