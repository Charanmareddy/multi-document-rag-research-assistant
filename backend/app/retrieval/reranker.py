"""Optional cross-encoder and Cohere rerank adapters."""

import logging
import time
from dataclasses import dataclass

import httpx

from backend.app.core.config import get_settings
from backend.app.retrieval.models import Evidence

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RerankOutcome:
    """Reranked evidence and transparent provider outcome."""

    results: list[Evidence]
    applied: bool
    latency_ms: float
    error: str | None = None


def rerank_evidence(query: str, evidence: list[Evidence], top_k: int, *, enabled: bool = True) -> RerankOutcome:
    """Rerank candidates if enabled; return original results after optional-provider errors."""

    settings = get_settings()
    method = settings.reranker.lower()
    started = time.perf_counter()
    if not enabled or method in {"", "none", "off"} or not evidence:
        return RerankOutcome(evidence[:top_k], False, 0.0)
    try:
        if method == "cohere":
            if not settings.cohere_api_key:
                raise RuntimeError("Set COHERE_API_KEY to enable Cohere reranking")
            response = httpx.post(
                "https://api.cohere.com/v2/rerank",
                headers={"Authorization": f"Bearer {settings.cohere_api_key}"},
                json={"model": settings.cohere_rerank_model, "query": query,
                      "documents": [item.text for item in evidence], "top_n": min(top_k, len(evidence))},
                timeout=30.0,
            )
            response.raise_for_status()
            ranked = response.json()["results"]
            results = []
            for item in ranked:
                result = evidence[int(item["index"])]
                result.score = float(item["relevance_score"])
                results.append(result)
        elif method == "local":
            from sentence_transformers import CrossEncoder

            model = CrossEncoder(settings.local_reranker_model)
            scores = model.predict([(query, item.text) for item in evidence])
            results = [item for _, item in sorted(zip(scores, evidence, strict=True), key=lambda pair: pair[0], reverse=True)]
            for score, item in zip(sorted(scores, reverse=True), results, strict=True):
                item.score = float(score)
            results = results[:top_k]
        else:
            raise RuntimeError(f"Unknown reranker: {method}")
        return RerankOutcome(results, True, (time.perf_counter() - started) * 1000)
    except Exception as exc:
        logger.exception("Reranking failed; keeping initial retrieval order")
        return RerankOutcome(evidence[:top_k], False, (time.perf_counter() - started) * 1000, str(exc))
