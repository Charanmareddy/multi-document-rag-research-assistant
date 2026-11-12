"""Bounded context assembly for grounded synthesis."""

from backend.app.retrieval.models import Evidence


def build_context(evidence: list[Evidence], *, max_sources: int = 10,
                  max_characters: int = 18000) -> tuple[str, dict[str, Evidence]]:
    """Label and bound retrieved evidence without merging away provenance."""

    source_map: dict[str, Evidence] = {}
    blocks: list[str] = []
    used = 0
    for item in evidence[:max_sources]:
        source_id = f"S{len(source_map) + 1}"
        page = f"page {item.page_number}" if item.page_number is not None else "document overview"
        heading = f"[{source_id}] {item.document_name}, {page}"
        if item.section_title:
            heading += f", section: {item.section_title}"
        body = item.text.strip()
        available = max_characters - used - len(heading) - 2
        if available <= 0:
            break
        body = body[:available]
        block = f"{heading}\n{body}"
        blocks.append(block)
        source_map[source_id] = item
        used += len(block) + 2
    return "\n\n".join(blocks), source_map
