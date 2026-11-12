"""Evaluation metric and review rubric tests."""

import pytest
from math import log2

from evaluation.rag_evaluation import (
    HUMAN_RUBRIC,
    citation_precision,
    citation_recall,
    validate_human_review,
)
from evaluation.retrieval_evaluation import (
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_retrieval_metrics() -> None:
    retrieved = ["a", "x", "b"]
    relevant = {"a", "b"}
    assert precision_at_k(retrieved, relevant, 3) == pytest.approx(2 / 3)
    assert recall_at_k(retrieved, relevant, 2) == pytest.approx(0.5)
    assert reciprocal_rank(retrieved, relevant) == 1.0
    assert ndcg_at_k(retrieved, relevant, 3) == pytest.approx((1 + 0.5) / (1 + 1 / log2(3)))


def test_citation_metrics_and_human_review_validation() -> None:
    expected = {"doc-a:1", "doc-b:3"}
    returned = {"doc-a:1", "doc-c:2"}
    assert citation_precision(returned, expected) == pytest.approx(0.5)
    assert citation_recall(returned, expected) == pytest.approx(0.5)
    assert set(validate_human_review({key: 4 for key in HUMAN_RUBRIC})) == set(HUMAN_RUBRIC)
    with pytest.raises(ValueError, match="1 to 5"):
        validate_human_review({key: 6 for key in HUMAN_RUBRIC})
