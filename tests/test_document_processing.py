"""PDF extraction and hierarchical chunking tests."""

from pathlib import Path

import pymupdf
import pytest

from backend.app.document_processing.chunking import build_hierarchical_chunks
from backend.app.document_processing.pdf_loader import extract_pdf_pages
from backend.app.embeddings.providers import EmbeddingConfigurationError, GeminiEmbeddingProvider
from backend.app.document_processing.pdf_loader import ExtractedPage


def create_pdf(path: Path, pages: list[str]) -> None:
    pdf = pymupdf.open()
    for text in pages:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    pdf.save(path)
    pdf.close()


def test_pdf_extraction_preserves_one_based_pages(tmp_path: Path) -> None:
    source = tmp_path / "sample.pdf"
    create_pdf(source, ["FIRST PAGE evidence", "SECOND PAGE findings"])

    pages = extract_pdf_pages(source)

    assert [page.page_number for page in pages] == [1, 2]
    assert "FIRST PAGE" in pages[0].text


def test_scanned_or_empty_pdf_reports_ocr_requirement(tmp_path: Path) -> None:
    source = tmp_path / "empty.pdf"
    pdf = pymupdf.open()
    pdf.new_page()
    pdf.save(source)
    pdf.close()

    with pytest.raises(ValueError, match="OCR"):
        extract_pdf_pages(source)


def test_chunk_hierarchy_keeps_source_pages() -> None:
    pages = [
        ExtractedPage(1, "INTRODUCTION\n" + "evidence " * 55),
        ExtractedPage(2, "METHODS\n" + "methods " * 65),
    ]

    chunks = build_hierarchical_chunks(pages, chunk_size=25, overlap=5)

    assert chunks[0].level == "document"
    assert any(chunk.level == "section" and chunk.page_number == 1 for chunk in chunks)
    assert any(chunk.level == "section" and chunk.page_number == 2 for chunk in chunks)
    assert {chunk.page_number for chunk in chunks if chunk.level == "retrieval"} == {1, 2}


def test_gemini_embedding_requires_key() -> None:
    with pytest.raises(EmbeddingConfigurationError, match="GOOGLE_API_KEY"):
        GeminiEmbeddingProvider("gemini-embedding-001", None)
