"""Validate model citation IDs against retrieved evidence."""

import re

from backend.app.llm.schemas import SynthesisOutput
from backend.app.retrieval.models import Evidence

SOURCE_PATTERN = re.compile(r"\bS\d+\b")


class InvalidCitationError(ValueError):
    """Raised when generated output references evidence that was not retrieved."""


def validate_and_render_citations(output: SynthesisOutput,
                                  source_map: dict[str, Evidence]) -> tuple[str, list[dict]]:
    """Reject unknown source labels and return citation objects for valid labels."""

    allowed = set(source_map)
    claimed = set(output.citation_ids)
    for finding in [*output.agreements, *output.contradictions]:
        if len({source_map[source].document_id for source in finding.source_ids if source in source_map}) < 2:
            raise InvalidCitationError("Cross-document findings must cite evidence from at least two documents")
        claimed.update(finding.source_ids)
    inline = set(SOURCE_PATTERN.findall(output.answer))
    claimed.update(inline)
    unknown = (claimed | inline) - allowed
    if unknown:
        raise InvalidCitationError(f"Generated answer referenced unknown source labels: {', '.join(sorted(unknown))}")
    if not claimed:
        raise InvalidCitationError("Generated answer did not cite any retrieved evidence")

    answer = output.answer.strip()
    missing_inline = [source_id for source_id in output.citation_ids if source_id not in inline]
    if missing_inline:
        answer = f"{answer} {' '.join(f'[{source_id}]' for source_id in missing_inline)}"
    citations = []
    for source_id in sorted(claimed, key=lambda value: int(value[1:])):
        evidence = source_map[source_id]
        citations.append({
            "source_id": source_id,
            "document_id": evidence.document_id,
            "document_name": evidence.document_name,
            "page_number": evidence.page_number,
            "section_title": evidence.section_title,
            "excerpt": evidence.text,
        })
    return answer, citations
