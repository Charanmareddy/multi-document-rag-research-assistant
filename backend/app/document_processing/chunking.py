"""Hierarchical, page-preserving chunk construction."""

import re
from dataclasses import dataclass

from backend.app.document_processing.pdf_loader import ExtractedPage


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """Chunk text and source metadata before persistence or embedding."""

    text: str
    level: str
    page_number: int | None
    chunk_index: int
    section_title: str | None = None


_HEADING = re.compile(r"^(?:\d+(?:\.\d+)*\s+)?[A-Z][A-Z0-9 &,:;()/-]{3,100}$")


def _split_windows(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    output = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        output.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return output


def build_hierarchical_chunks(
    pages: list[ExtractedPage], *, chunk_size: int = 220, overlap: int = 40
) -> list[ChunkDraft]:
    """Build document, section, and retrieval chunks without losing page numbers.

    Sizes and overlap are measured in words. A document overview stores a bounded
    extract of the opening pages and is labelled as source text, not a generated summary.
    """

    if chunk_size < 20:
        raise ValueError("chunk_size must be at least 20 words")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    if not pages:
        return []

    full_text = "\n".join(page.text for page in pages)
    output: list[ChunkDraft] = []
    overview_words = full_text.split()[: min(500, chunk_size * 2)]
    output.append(ChunkDraft("Document opening excerpt: " + " ".join(overview_words), "document", None, 0))

    section_parts: list[tuple[str | None, int, str]] = []
    for page in pages:
        current_title: str | None = None
        current_lines: list[str] = []
        for line in page.text.splitlines():
            candidate = line.strip()
            if _HEADING.match(candidate) and len(candidate.split()) <= 12:
                if current_lines:
                    section_parts.append((current_title, page.page_number, "\n".join(current_lines)))
                current_title = candidate.title()
                current_lines = []
            else:
                current_lines.append(candidate)
        if current_lines:
            section_parts.append((current_title, page.page_number, "\n".join(current_lines)))

    for idx, (title, page_number, body) in enumerate(section_parts):
        words = body.split()
        if words:
            output.append(ChunkDraft(" ".join(words[: min(len(words), chunk_size * 3)]), "section", page_number, idx, title))

    retrieval_idx = 0
    for page in pages:
        for window in _split_windows(page.text, chunk_size, overlap):
            output.append(ChunkDraft(window, "retrieval", page.page_number, retrieval_idx))
            retrieval_idx += 1
    return output
