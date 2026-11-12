"""Background indexing job endpoints."""

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models import Collection, Document, IndexingJob
from backend.app.database.session import get_db
from backend.app.services.indexing import run_index_job

router = APIRouter(prefix="/indexing", tags=["indexing"])


class IndexRequest(BaseModel):
    """Select a collection and optional documents to index."""

    collection_id: str
    document_ids: list[str] | None = None


@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
def start_indexing(payload: IndexRequest, background_tasks: BackgroundTasks,
                   db: Session = Depends(get_db)) -> dict:
    if db.get(Collection, payload.collection_id) is None:
        raise HTTPException(404, "Collection not found")
    query = select(Document).where(
        Document.collection_id == payload.collection_id,
        Document.status.in_(["uploaded", "index_failed"]),
    )
    if payload.document_ids is not None:
        if not payload.document_ids:
            raise HTTPException(422, "document_ids must not be empty")
        query = query.where(Document.id.in_(payload.document_ids))
    documents = db.scalars(query.order_by(Document.uploaded_at)).all()
    if not documents:
        raise HTTPException(409, "No uploaded or failed documents are eligible for indexing")
    job = IndexingJob(id=str(uuid4()), collection_id=payload.collection_id,
                      status="queued", total_documents=len(documents))
    db.add(job)
    db.commit()
    ids = [doc.id for doc in documents]
    background_tasks.add_task(run_index_job, job.id, ids)
    return {"job_id": job.id, "collection_id": job.collection_id,
            "status": job.status, "total_documents": job.total_documents}


@router.get("/status/{job_id}")
def indexing_status(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = db.get(IndexingJob, job_id)
    if job is None:
        raise HTTPException(404, "Indexing job not found")
    return {"job_id": job.id, "collection_id": job.collection_id, "status": job.status,
            "total_documents": job.total_documents, "processed_documents": job.processed_documents,
            "failed_documents": job.failed_documents, "error": job.error,
            "created_at": job.created_at, "updated_at": job.updated_at}
