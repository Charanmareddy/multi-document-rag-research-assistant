"""Citation metric helpers and human-review rubric validation."""


def citation_precision(returned_sources: set[str], expected_sources: set[str]) -> float:
    """Fraction of returned document/page citations that are expected."""

    return len(returned_sources & expected_sources) / max(len(returned_sources), 1)


def citation_recall(returned_sources: set[str], expected_sources: set[str]) -> float:
    """Fraction of expected document/page citations that were returned."""

    return len(returned_sources & expected_sources) / max(len(expected_sources), 1)


HUMAN_RUBRIC = (
    "faithfulness", "answer_relevance", "context_relevance",
    "agreement_detection", "contradiction_detection", "source_attribution",
)


def validate_human_review(scores: dict[str, int]) -> dict[str, int]:
    """Validate documented 1–5 human scores without turning them into model metrics."""

    missing = set(HUMAN_RUBRIC) - set(scores)
    extra = set(scores) - set(HUMAN_RUBRIC)
    if missing or extra:
        raise ValueError(f"Review fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
    if any(not isinstance(score, int) or not 1 <= score <= 5 for score in scores.values()):
        raise ValueError("Human rubric scores must be integers from 1 to 5")
    return scores
