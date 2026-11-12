"""Collection and safe PDF ingestion endpoints."""

import hashlib
import logging
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

import pymupdf
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.database.models import Collection, Document, DocumentChunk, IndexingJob, QueryHistory
from backend.app.database.session import get_db
from backend.app.vector_store.qdrant_store import QdrantConfigurationError, delete_document_vectors

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collections", tags=["collections"])
documents_router = APIRouter(prefix="/documents", tags=["documents"])
MAX_ARCHIVE_FILES = 500
MAX_UNCOMPRESSED_BYTES = 1_000_000_000


class CollectionCreate(BaseModel):
    """Collection creation payload."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


def _serialize_collection(item: Collection) -> dict:
    return {"id": item.id, "name": item.name, "description": item.description,
            "created_at": item.created_at, "documents": [_serialize_document(d) for d in item.documents]}


def _serialize_document(item: Document) -> dict:
    return {"id": item.id, "collection_id": item.collection_id, "name": item.name,
            "file_size": item.file_size, "page_count": item.page_count, "title": item.title,
            "author": item.author, "subject": item.subject, "created_on": item.created_on,
            "status": item.status, "chunk_count": item.chunk_count, "uploaded_at": item.uploaded_at}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_collection(payload: CollectionCreate, db: Session = Depends(get_db)) -> dict:
    item = Collection(name=payload.name.strip(), description=payload.description)
    if not item.name:
        raise HTTPException(422, "Collection name cannot be blank")
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A collection with this name already exists") from exc
    db.refresh(item)
    return _serialize_collection(item)


@router.get("")
def list_collections(db: Session = Depends(get_db)) -> list[dict]:
    return [_serialize_collection(c) for c in db.scalars(select(Collection).order_by(Collection.created_at.desc())).all()]


@router.get("/{collection_id}")
def get_collection(collection_id: str, db: Session = Depends(get_db)) -> dict:
    item = db.get(Collection, collection_id)
    if item is None:
        raise HTTPException(404, "Collection not found")
    return _serialize_collection(item)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(collection_id: str, db: Session = Depends(get_db)) -> None:
    item = db.get(Collection, collection_id)
    if item is None:
        raise HTTPException(404, "Collection not found")
    try:
        for document in item.documents:
            if db.query(DocumentChunk.id).filter(DocumentChunk.document_id == document.id).first():
                delete_document_vectors(document.id)
    except QdrantConfigurationError as exc:
        raise HTTPException(503, str(exc)) from exc
    db.query(DocumentChunk).filter(DocumentChunk.collection_id == collection_id).delete(synchronize_session=False)
    db.query(IndexingJob).filter(IndexingJob.collection_id == collection_id).delete(synchronize_session=False)
    db.query(QueryHistory).filter(QueryHistory.collection_id == collection_id).update(
        {QueryHistory.collection_id: None}, synchronize_session=False
    )
    for document in item.documents:
        Path(document.file_path).unlink(missing_ok=True)
    db.delete(item)
    db.commit()


@documents_router.get("")
def list_documents(collection_id: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = select(Document).order_by(Document.uploaded_at.desc())
    if collection_id:
        query = query.where(Document.collection_id == collection_id)
    return [_serialize_document(d) for d in db.scalars(query).all()]


@documents_router.get("/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db)) -> dict:
    item = db.get(Document, document_id)
    if item is None:
        raise HTTPException(404, "Document not found")
    return _serialize_document(item)


def _safe_filename(name: str) -> str:
    """Strip path segments and unsafe filesystem characters from a client filename."""
    leaf = Path(name.replace("\\", "/")).name
    leaf = re.sub(r"[^\w.() -]", "_", leaf).strip(" .")
    return leaf[:180] or "document.pdf"


async def _save_pdf(upload: UploadFile, collection_id: str, db: Session) -> dict:
    settings = get_settings()
    filename = _safe_filename(upload.filename or "document.pdf")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(415, f"Unsupported file type: {filename}")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    digest = hashlib.sha256()
    size = 0
    fd, temp_path = tempfile.mkstemp(prefix="upload-", suffix=".pdf", dir=settings.upload_dir)
    try:
        with os.fdopen(fd, "wb") as out:
            while block := await upload.read(1024 * 1024):
                size += len(block)
                if size > max_bytes:
                    raise HTTPException(413, f"{filename} exceeds the {settings.max_upload_mb} MB upload limit")
                digest.update(block)
                out.write(block)
        if not size:
            raise HTTPException(422, f"{filename} is empty")
        sha = digest.hexdigest()
        duplicate = db.scalar(select(Document).where(Document.collection_id == collection_id, Document.sha256 == sha))
        if duplicate:
            Path(temp_path).unlink(missing_ok=True)
            return {"document": _serialize_document(duplicate), "duplicate": True}
        try:
            pdf = pymupdf.open(temp_path)
            if pdf.is_encrypted:
                pdf.close()
                raise HTTPException(422, f"{filename} is password-protected")
            if pdf.page_count < 1:
                pdf.close()
                raise HTTPException(422, f"{filename} contains no pages")
            metadata = pdf.metadata or {}
            page_count = pdf.page_count
            pdf.close()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, f"{filename} is not a readable PDF: {exc}") from exc

        destination = settings.upload_dir / collection_id
        destination.mkdir(parents=True, exist_ok=True)
        document_id = str(uuid4())
        final_path = destination / f"{document_id}.pdf"
        shutil.move(temp_path, final_path)
        record = Document(id=document_id, collection_id=collection_id, name=filename, sha256=sha,
                          file_path=str(final_path), file_size=size, page_count=page_count,
                          title=metadata.get("title") or None, author=metadata.get("author") or None,
                          subject=metadata.get("subject") or None,
                          created_on=metadata.get("creationDate") or None, status="uploaded")
        db.add(record)
        db.commit()
        db.refresh(record)
        return {"document": _serialize_document(record), "duplicate": False}
    except Exception:
        Path(temp_path).unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


async def _require_collection(collection_id: str, db: Session) -> None:
    if db.get(Collection, collection_id) is None:
        raise HTTPException(404, "Collection not found")


@documents_router.post("/upload", status_code=201)
async def upload_pdfs(collection_id: str = Form(...), files: list[UploadFile] = File(...),
                      db: Session = Depends(get_db)) -> dict:
    await _require_collection(collection_id, db)
    if not files:
        raise HTTPException(422, "At least one PDF is required")
    results = []
    for upload in files:
        try:
            results.append(await _save_pdf(upload, collection_id, db))
        except HTTPException as exc:
            results.append({"filename": upload.filename, "error": exc.detail})
    return {"results": results}


@documents_router.post("/upload-zip", status_code=201)
async def upload_zip(collection_id: str = Form(...), file: UploadFile = File(...),
                     db: Session = Depends(get_db)) -> dict:
    await _require_collection(collection_id, db)
    archive_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip", dir=get_settings().upload_dir) as tmp:
            archive_path = Path(tmp.name)
            total = 0
            while block := await file.read(1024 * 1024):
                total += len(block)
                if total > get_settings().max_upload_mb * 1024 * 1024:
                    raise HTTPException(413, "ZIP file exceeds upload size limit")
                tmp.write(block)
        try:
            archive = zipfile.ZipFile(archive_path)
        except zipfile.BadZipFile as exc:
            raise HTTPException(422, "Uploaded file is not a valid ZIP archive") from exc
        with archive:
            members = [i for i in archive.infolist() if not i.is_dir() and i.filename.lower().endswith(".pdf")]
            if len(members) > MAX_ARCHIVE_FILES:
                raise HTTPException(413, f"ZIP contains more than {MAX_ARCHIVE_FILES} PDFs")
            uncompressed = sum(i.file_size for i in members)
            if uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise HTTPException(413, "ZIP expands beyond the 1 GB safety limit")
            results = []
            for info in members:
                # Reject path traversal and symlink entries; files are staged by basename only.
                member = PurePosixPath(info.filename.replace("\\", "/"))
                mode = (info.external_attr >> 16) & 0xFFFF
                if member.is_absolute() or ".." in member.parts or (mode and (mode & 0o170000) == 0o120000):
                    results.append({"filename": info.filename, "error": "Unsafe archive path"})
                    continue
                with archive.open(info) as source:
                    content = source.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
                if len(content) > get_settings().max_upload_mb * 1024 * 1024:
                    results.append({"filename": info.filename, "error": "PDF exceeds per-file size limit"})
                    continue
                from starlette.datastructures import UploadFile as StarletteUploadFile
                from io import BytesIO
                staged = StarletteUploadFile(filename=_safe_filename(member.name), file=BytesIO(content))
                try:
                    results.append(await _save_pdf(staged, collection_id, db))
                except HTTPException as exc:
                    results.append({"filename": info.filename, "error": exc.detail})
            return {"results": results, "pdf_count": len(members)}
    finally:
        if archive_path:
            archive_path.unlink(missing_ok=True)
        await file.close()


@documents_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Session = Depends(get_db)) -> None:
    item = db.get(Document, document_id)
    if item is None:
        raise HTTPException(404, "Document not found")
    if db.query(DocumentChunk.id).filter(DocumentChunk.document_id == document_id).first():
        try:
            delete_document_vectors(document_id)
        except QdrantConfigurationError as exc:
            raise HTTPException(503, str(exc)) from exc
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete(synchronize_session=False)
    Path(item.file_path).unlink(missing_ok=True)
    db.delete(item)
    db.commit()
