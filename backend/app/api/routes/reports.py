"""Report generation, history, and DOCX download endpoints."""

import json
import logging
from pathlib import Path
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.routes.research import ResearchQueryRequest
from backend.app.core.config import get_settings
from backend.app.database.models import Collection, QueryCitation, QueryHistory, ResearchReport
from backend.app.database.session import get_db
from backend.app.embeddings.providers import EmbeddingConfigurationError
from backend.app.rag.citation_manager import InvalidCitationError
from backend.app.rag.query_engine import answer_question
from backend.app.reports.docx_exporter import export_report_docx
from backend.app.reports.report_generator import build_report
from backend.app.retrieval.models import SearchFilters
from backend.app.vector_store.qdrant_store import QdrantConfigurationError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


class ReportRequest(ResearchQueryRequest):
    """Report generation request based on an evidence-grounded research query."""

    title: str | None = Field(default=None, max_length=300)


@router.post("/generate", status_code=201)
def generate_report(payload: ReportRequest, db: Session = Depends(get_db)) -> dict:
    if db.get(Collection, payload.collection_id) is None:
        raise HTTPException(404, "Collection not found")
    try:
        result = answer_question(
            db, query=payload.query, filters=SearchFilters(
                collection_id=payload.collection_id, document_ids=payload.document_ids, author=payload.author
            ), mode=payload.mode, top_k=payload.top_k, rerank=payload.rerank,
            route_documents=payload.route_documents,
        )
        if not result["citations"]:
            raise HTTPException(422, "No cited evidence was found; index documents before generating a report")
        title = (payload.title or payload.query).strip()[:300] or "Research report"
        content = build_report(title, payload.query, result)
        report_id = str(uuid4())
        output_path = Path("./data/reports").resolve() / f"{report_id}.docx"
        export_report_docx(content, output_path)
        row = ResearchReport(id=report_id, collection_id=payload.collection_id,
                             title=title, question=payload.query,
                             content_json=json.dumps(content, ensure_ascii=False), docx_path=str(output_path))
        db.add(row)
        history = QueryHistory(collection_id=payload.collection_id, question=payload.query, answer=result["answer"])
        db.add(history)
        db.flush()
        for citation in result["citations"]:
            db.add(QueryCitation(query_id=history.id, document_id=citation["document_id"],
                                 source_id=citation["source_id"], page_number=citation["page_number"]))
        try:
            db.commit()
        except Exception:
            db.rollback()
            output_path.unlink(missing_ok=True)
            raise
        return {"id": row.id, "collection_id": row.collection_id, "title": row.title,
                "question": row.question, "created_at": row.created_at,
                "content": content, "download_path": f"/api/v1/reports/{row.id}/download"}
    except HTTPException:
        raise
    except InvalidCitationError as exc:
        raise HTTPException(502, "The model returned invalid report citations; retry") from exc
    except (EmbeddingConfigurationError, QdrantConfigurationError) as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("Report generation failed")
        raise HTTPException(503, "Report generation provider failed; check configuration and logs") from exc


@router.get("")
def list_reports(collection_id: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = select(ResearchReport).order_by(ResearchReport.created_at.desc())
    if collection_id:
        query = query.where(ResearchReport.collection_id == collection_id)
    return [{"id": item.id, "collection_id": item.collection_id, "title": item.title,
             "question": item.question, "created_at": item.created_at} for item in db.scalars(query).all()]


@router.get("/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)) -> dict:
    item = db.get(ResearchReport, report_id)
    if item is None:
        raise HTTPException(404, "Report not found")
    return {"id": item.id, "collection_id": item.collection_id, "title": item.title,
            "question": item.question, "created_at": item.created_at,
            "content": json.loads(item.content_json)}


@router.get("/{report_id}/download")
def download_report(report_id: str, db: Session = Depends(get_db)) -> FileResponse:
    item = db.get(ResearchReport, report_id)
    if item is None:
        raise HTTPException(404, "Report not found")
    path = Path(item.docx_path or "")
    if not path.is_file():
        raise HTTPException(404, "DOCX export not found")
    safe_title = re.sub(r"[^A-Za-z0-9 _.-]", "_", item.title).strip(" .")[:80] or "Research Report"
    return FileResponse(path, filename=f"{safe_title}.docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
