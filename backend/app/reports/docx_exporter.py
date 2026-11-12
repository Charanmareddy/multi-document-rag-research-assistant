"""DOCX export for structured research reports."""

from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt


def export_report_docx(report: dict, destination: Path) -> None:
    """Write a clean, reference-backed DOCX report."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    normal = document.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10)

    document.add_heading(report["title"], level=0)
    document.add_paragraph("Research question", style="Heading 2")
    document.add_paragraph(report["question"])
    document.add_heading("Executive summary", level=1)
    document.add_paragraph(report["executive_summary"])

    for key, heading in [("agreements", "Agreements across documents"),
                         ("contradictions", "Potential contradictions"),
                         ("limitations", "Caveats and limitations")]:
        document.add_heading(heading, level=1)
        values = report.get(key, [])
        if not values:
            document.add_paragraph("No findings returned.")
        for item in values:
            if isinstance(item, dict):
                refs = ", ".join(item.get("source_ids", []))
                document.add_paragraph(f"{item.get('finding', '')} [{refs}]", style="List Bullet")
            else:
                document.add_paragraph(str(item), style="List Bullet")

    document.add_heading("References and supporting excerpts", level=1)
    for citation in report.get("references", []):
        page = citation.get("page_number")
        location = f"page {page}" if page is not None else "document overview"
        paragraph = document.add_paragraph(style="List Number")
        paragraph.add_run(f"[{citation['source_id']}] {citation['document_name']} — {location}").bold = True
        if citation.get("section_title"):
            paragraph.add_run(f" — {citation['section_title']}")
        document.add_paragraph(citation.get("excerpt", ""))
    document.save(destination)
