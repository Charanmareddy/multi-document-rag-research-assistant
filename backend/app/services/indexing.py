"""Resumable, document-incremental PDF extraction and vector indexing."""

import logging
import time
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

from sqlalchemy import select

from backend.app.database.models import Document, DocumentChunk, EmbeddingIndex, IndexingJob, utc_now
from backend.app.database.session import SessionLocal
from backend.app.document_processing.chunking import build_hierarchical_chunks
from backend.app.document_processing.pdf_loader import extract_pdf_pages
from backend.app.embeddings.providers import get_embedding_provider
from backend.app.vector_store.qdrant_store import (
    COLLECTION_NAME,
    create_client,
    delete_document_points,
    ensure_collection,
    upsert_chunks,
)

logger = logging.getLogger(__name__)


def _set_job(job_id: str, **values) -> None:
    with SessionLocal() as db:
        job = db.get(IndexingJob, job_id)
        if job:
            for key, value in values.items():
                setattr(job, key, value)
            db.commit()


def _index_one(document: Document, provider, client, db) -> dict[str, float]:
    extraction_started = time.perf_counter()
    pages = extract_pdf_pages(Path(document.file_path))
    drafts = build_hierarchical_chunks(pages)
    extraction_ms = (time.perf_counter() - extraction_started) * 1000
    if not drafts:
        raise ValueError("No chunks were produced from this PDF")
    vectors: list[list[float]] = []
    batch_size = 64
    embedding_started = time.perf_counter()
    for start in range(0, len(drafts), batch_size):
        vectors.extend(provider.embed_documents([chunk.text for chunk in drafts[start:start + batch_size]]))
    embedding_ms = (time.perf_counter() - embedding_started) * 1000
    if len(vectors) != len(drafts) or not vectors or not vectors[0]:
        raise RuntimeError("Embedding provider returned an invalid vector batch")
    dimension = len(vectors[0])
    if any(len(vector) != dimension for vector in vectors):
        raise RuntimeError("Embedding provider returned inconsistent vector dimensions")

    profile = db.get(EmbeddingIndex, 1)
    if profile and (profile.provider_identity != provider.identity or profile.dimension != dimension):
        raise RuntimeError(
            f"Index uses {profile.provider_identity} ({profile.dimension} dimensions), but configuration is {provider.identity} ({dimension}). Re-index explicitly to change embedding models."
        )
    ensure_collection(client, dimension)

    records = []
    chunks = []
    for draft in drafts:
        point_id = str(uuid5(NAMESPACE_URL, f"{document.id}:{draft.level}:{draft.chunk_index}"))
        record = {
            "id": point_id,
            "document_id": document.id,
            "document_name": document.name,
            "collection_id": document.collection_id,
            "page_number": draft.page_number,
            "chunk_id": point_id,
            "chunk_index": draft.chunk_index,
            "level": draft.level,
            "section_title": draft.section_title,
            "source_file": document.name,
            "document_author": document.author,
            "text": draft.text,
        }
        records.append(record)
        chunks.append(DocumentChunk(
            id=point_id, document_id=document.id, collection_id=document.collection_id,
            chunk_key=f"{draft.level}:{draft.chunk_index}", chunk_index=draft.chunk_index,
            level=draft.level, page_number=draft.page_number,
            section_title=draft.section_title, text=draft.text,
        ))

    # Remove stale vectors first, then upsert deterministic IDs so retries are idempotent.
    vector_started = time.perf_counter()
    delete_document_points(client, document.id)
    upsert_chunks(client, records, vectors)
    vector_store_ms = (time.perf_counter() - vector_started) * 1000
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete(synchronize_session=False)
    db.add_all(chunks)
    document.page_count = len(pages)
    document.chunk_count = sum(chunk.level == "retrieval" for chunk in drafts)
    document.status = "indexed"
    if not profile:
        db.add(EmbeddingIndex(id=1, provider_identity=provider.identity, dimension=dimension, collection_name=COLLECTION_NAME))
    db.commit()
    return {"extraction_ms": extraction_ms, "embedding_ms": embedding_ms,
            "vector_store_ms": vector_store_ms}


def run_index_job(job_id: str, document_ids: list[str]) -> None:
    """Process queued documents independently so a failed PDF does not abort the batch."""

    job_started = time.perf_counter()
    with SessionLocal() as db:
        job = db.get(IndexingJob, job_id)
        if not job:
            return
        job.status = "running"
        job.started_at = utc_now()
        db.commit()

    try:
        provider = get_embedding_provider()
        client = create_client()
    except Exception as exc:
        logger.exception("Index job %s could not initialize providers", job_id)
        _set_job(job_id, status="failed", error=str(exc), finished_at=utc_now(),
                 elapsed_ms=(time.perf_counter() - job_started) * 1000)
        with SessionLocal() as db:
            for document in db.scalars(select(Document).where(Document.id.in_(document_ids))).all():
                document.status = "index_failed"
            db.commit()
        return

    failures = 0
    completed = 0
    error_messages = []
    totals = {"extraction_ms": 0.0, "embedding_ms": 0.0, "vector_store_ms": 0.0}
    try:
        for document_id in document_ids:
            try:
                with SessionLocal() as db:
                    document = db.get(Document, document_id)
                    if document is None:
                        continue
                    document.status = "processing"
                    db.commit()
                    timings = _index_one(document, provider, client, db)
                    for key, value in timings.items():
                        totals[key] += value
            except Exception as exc:
                failures += 1
                error_messages.append(f"{document_id}: {str(exc)[:400]}")
                logger.exception("Indexing failed for document %s", document_id)
                with SessionLocal() as db:
                    document = db.get(Document, document_id)
                    if document:
                        document.status = "index_failed"
                        db.commit()
            finally:
                completed += 1
                _set_job(job_id, processed_documents=completed, failed_documents=failures)
        _set_job(job_id, status="completed_with_errors" if failures else "completed",
                 finished_at=utc_now(), elapsed_ms=(time.perf_counter() - job_started) * 1000,
                 extraction_ms=totals["extraction_ms"], embedding_ms=totals["embedding_ms"],
                 vector_store_ms=totals["vector_store_ms"],
                 error="\n".join(error_messages)[:4000] or None)
    finally:
        client.close()
