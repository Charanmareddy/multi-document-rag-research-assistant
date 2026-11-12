"""Assemble a report from a grounded research answer and its verified citations."""


def build_report(title: str, question: str, result: dict) -> dict:
    """Create a structured report representation without inventing new findings."""

    return {
        "title": title,
        "question": question,
        "executive_summary": result["answer"],
        "agreements": result.get("agreements", []),
        "contradictions": result.get("contradictions", []),
        "limitations": result.get("caveats", []),
        "references": result.get("citations", []),
        "retrieval_mode": result.get("retrieval_mode"),
        "timings_ms": result.get("timings_ms", {}),
    }
