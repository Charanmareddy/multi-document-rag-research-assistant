"""Portable SQLAlchemy metadata models for collections and documents."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.session import Base


def utc_now() -> datetime:
    """Timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class Collection(Base):
    """A named group of source documents."""

    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    documents: Mapped[list["Document"]] = relationship(back_populates="collection", cascade="all, delete-orphan")


class Document(Base):
    """Uploaded document metadata and processing state."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("collection_id", "sha256", name="uq_document_collection_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    file_path: Mapped[str] = mapped_column(Text)
    file_size: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    author: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_on: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="uploaded", index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    collection: Mapped[Collection] = relationship(back_populates="documents")


class QueryHistory(Base):
    """Research question and outcome metadata for recent activity."""

    __tablename__ = "query_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    collection_id: Mapped[str | None] = mapped_column(ForeignKey("collections.id", ondelete="SET NULL"), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class QueryCitation(Base):
    """Attribution linking a saved research question to a source page."""

    __tablename__ = "query_citations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    query_id: Mapped[str] = mapped_column(ForeignKey("query_history.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    source_id: Mapped[str] = mapped_column(String(20))
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ResearchReport(Base):
    """Saved generated report and path to its DOCX export."""

    __tablename__ = "research_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    collection_id: Mapped[str | None] = mapped_column(ForeignKey("collections.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    question: Mapped[str] = mapped_column(Text)
    content_json: Mapped[str] = mapped_column(Text)
    docx_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DocumentChunk(Base):
    """Page-attributed chunk source of truth, including hierarchical parent chunks."""

    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_key", name="uq_chunk_document_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    chunk_key: Mapped[str] = mapped_column(String(120))
    chunk_index: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(30), index=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text: Mapped[str] = mapped_column(Text)


class EmbeddingIndex(Base):
    """Records the one embedding identity and vector shape used by a local index."""

    __tablename__ = "embedding_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    provider_identity: Mapped[str] = mapped_column(String(300))
    dimension: Mapped[int] = mapped_column(Integer)
    collection_name: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class IndexingJob(Base):
    """Batch indexing status and progress, safe to resume after failed documents."""

    __tablename__ = "indexing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    total_documents: Mapped[int] = mapped_column(Integer, default=0)
    processed_documents: Mapped[int] = mapped_column(Integer, default=0)
    failed_documents: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    elapsed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_ms: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    embedding_ms: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    vector_store_ms: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
