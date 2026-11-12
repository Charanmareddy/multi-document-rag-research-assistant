"""Page-level PDF text extraction."""

from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    """Text and one-based page number from a PDF page."""

    page_number: int
    text: str


def extract_pdf_pages(path: Path) -> list[ExtractedPage]:
    """Extract text page-by-page and retain page provenance."""

    pages: list[ExtractedPage] = []
    with pymupdf.open(path) as pdf:
        if pdf.is_encrypted:
            raise ValueError("PDF is password-protected")
        for page_number, page in enumerate(pdf, start=1):
            text = "\n".join(line.rstrip() for line in page.get_text("text").splitlines()).strip()
            if text:
                pages.append(ExtractedPage(page_number=page_number, text=text))
    if not pages:
        raise ValueError("PDF contains no extractable text; scanned documents require OCR support")
    return pages
